import json

from conftest import write_fake_track

from glass_harbor import align
from glass_harbor.lyrics import load_lyrics, lyrics_path
from glass_harbor.lyrics_ref import reference_path


def _words(text, start, step=0.4):
    return [{"word": w, "start": round(start + i * step, 3), "end": round(start + i * step + 0.3, 3), "prob": 0.9}
            for i, w in enumerate(text.split())]


def _whisper():
    intro = _words("you see me let me tell you", 0.5)  # spoken, not in the published lyrics
    line = _words("every morning when I wake I hit my knees", 5.0, step=0.3)  # 8 of 9 words, a bit early
    return {"model": "test", "segments": [{"start": 0.5, "end": 2.9, "text": "you see me", "words": intro},
                                          {"start": 5.0, "end": 7.7, "text": "every morning", "words": line}]}


def _reference():
    return {"lines": [{"time": 5.0, "text": "Every mornin' when I wake, I hit my knees", "norm": "x"}]}


def _fake_align(vocal, lines, windows=None):
    return [{"index": i, "text": line["text"], "words": _words(line["text"], 5.12, step=0.3)}
            for i, line in enumerate(lines)]


def test_agreement_counts_the_published_words_whisper_heard_in_order():
    lines = [{"text": "Every mornin' when I wake, I hit my knees"}]
    heard = [{"words": _words("every mornin when I wake I hit my knees", 0)}]
    other = [{"words": _words("no looking back this time", 0)}]
    assert align.text_agreement(lines, heard) > 0.85  # "mornin'" vs "mornin" is the one miss
    assert align.text_agreement(lines, other) == 0.0


def test_merge_keeps_whisper_only_where_the_published_text_is_silent():
    merged = align.merge(_whisper(), _fake_align(None, _reference()["lines"]))
    texts = [seg["text"] for seg in merged["segments"]]
    assert texts[0].startswith("you see me") and texts[1] == "Every mornin' when I wake, I hit my knees"
    assert len(merged["segments"]) == 2  # Whisper's take on the line is gone, its intro stays
    assert merged["segments"][1]["words"][0]["start"] == 5.12 and merged["timing"] == "aligned"


def test_align_track_gates_on_agreement_and_keeps_whispers_output(workspace, monkeypatch):
    write_fake_track("rap", bpm=90, key="Am", bars=8)
    whisper = _whisper()
    lyrics_path("rap").write_text(json.dumps(whisper))
    calls = []
    monkeypatch.setattr(align, "align_lines",
                        lambda vocal, lines, windows: calls.append(windows) or _fake_align(vocal, lines))

    reference_path("rap").write_text(json.dumps({"lines": [{"time": 5.0, "text": "No looking back this time"}]}))
    assert align.align_track("rap", log=lambda m: None) is None  # another song's text: Whisper stays
    assert load_lyrics("rap") == whisper and not calls

    reference_path("rap").write_text(json.dumps(_reference()))
    merged = align.align_track("rap", log=lambda m: None)
    assert merged["timing"] == "aligned" and load_lyrics("rap") == merged
    assert json.loads(align.whisper_path("rap").read_text()) == whisper
    assert align.align_track("rap", log=lambda m: None)["segments"] == merged["segments"]  # re-run: from Whisper's
    assert len(calls) == 2


def test_auto_retimes_lyrics_that_are_not_aligned_yet(workspace, monkeypatch):
    from glass_harbor import auto

    write_fake_track("rap", bpm=90, key="Am", bars=8)
    lyrics_path("rap").write_text(json.dumps(_whisper()))
    reference_path("rap").write_text(json.dumps(_reference()))
    monkeypatch.setattr(align, "align_lines", _fake_align)
    auto._lyrics("rap", log=lambda m: None)
    assert load_lyrics("rap")["timing"] == "aligned"


def test_timing_offset_does_not_trust_an_alignment_it_cannot_check():
    aligned = [{"text": "x", "words": _words("no looking back", 3.0)}]
    assert align.timing_offset(aligned, _whisper()["segments"]) == float("inf")


def test_align_lines_skips_lines_the_window_or_aligner_cannot_fit(monkeypatch):
    import sys
    import types

    import numpy as np
    import torch

    class Span:
        def __init__(self, frame):
            self.start, self.end, self.score = frame, frame + 1, 0.5

    def aligner(emission, targets):
        if len(targets) > 4:  # stands in for torchaudio's "targets length is too long for CTC"
            raise RuntimeError("targets length is too long for CTC")
        return [[Span(i)] for i in range(len(targets))]

    bundle = types.SimpleNamespace(
        sample_rate=16000,
        get_model=lambda with_star: types.SimpleNamespace(
            eval=lambda: lambda wave: (torch.zeros(1, wave.shape[1] // 320, 29), None)),
        get_tokenizer=lambda: lambda words: [list(range(1, len(w) + 1)) for w in words],
        get_aligner=lambda: aligner)
    fake = types.ModuleType("torchaudio")
    fake.pipelines = types.SimpleNamespace(MMS_FA=bundle)
    monkeypatch.setitem(sys.modules, "torchaudio", fake)

    lines = [{"text": "hey you"}, {"text": "a line far too long for this aligner"}, {"text": "squeezed in"}]
    windows = [(0.0, 2.0), (2.0, 6.0), (6.0, 6.1)]  # the last window holds 5 frames for 11 letters
    out = align.align_lines(np.zeros((8 * 44100, 2), np.float32), lines, windows)
    assert [line["text"] for line in out] == ["hey you"]


def test_align_track_rejects_mostly_skipped_lines_and_records_the_rest(workspace, monkeypatch):
    write_fake_track("rap", bpm=90, key="Am", bars=8)
    whisper = _whisper()
    lyrics_path("rap").write_text(json.dumps(whisper))
    lines = _reference()["lines"] + [{"time": 9.0 + i, "text": f"spare line {i}"} for i in range(4)]
    reference_path("rap").write_text(json.dumps({"lines": lines}))

    def keep(indexes):
        return lambda vocal, lines, windows: [line for line in _fake_align(vocal, lines) if line["index"] in indexes]

    # The first line carries enough of what Whisper heard to pass the text gate; only 2 of 5 lines aligning means
    # the text and the recording disagree, so nothing is saved and auto can try again later.
    monkeypatch.setattr(align, "text_agreement", lambda lines, segments: 0.9)
    monkeypatch.setattr(align, "align_lines", keep({0, 1}))
    assert align.align_track("rap", log=lambda m: None) is None
    assert load_lyrics("rap") == whisper and not align.whisper_path("rap").exists()

    monkeypatch.setattr(align, "align_lines", keep({0, 1, 2, 3}))  # 4 of 5: kept, the gap recorded
    merged = align.align_track("rap", log=lambda m: None)
    assert merged["skipped_lines"] == [4] and merged["aligned_lines"] == 4
