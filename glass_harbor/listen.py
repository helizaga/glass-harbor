"""An AI listening pass with the model already on this machine (no extra download).

Whisper transcribes the finished mix, and each vocal clip's own lyrics are checked against what it hears at that
moment. It hears the vocal sections in slices shorter than its 30-second window: decoding a whole busy mix in one
pass dropped entire stretches (the first 42 seconds of GLOCK over Stay With Me read as nothing, yet the same audio
sliced read almost word for word). A clip that reads weak is heard once more on a window of its own before it
counts, since a cut in the middle of a verse loses words too. A clip whose words Whisper cannot make out over the beat is masked for a listener too. ``vocal_presence``
measures level in the 1-4 kHz band; this measures whether the words actually survive the beat, the reverb, and the
master. Results go to ``listen.json`` in the run folder; QA flags weak clips and ``glass-harbor auto`` lifts them.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any

import numpy as np

from glass_harbor import audio as A

MATCH_WINDOW_S = 0.6  # a heard word counts if it is the same word within this distance of where it should be
MIN_WORDS = 8  # clips with fewer expected words are too short to judge
WEAK_RECALL = 0.5
RELATIVE_DROP = 0.15
SLICE_S = 28.0  # under Whisper's 30 s window, so each slice is decoded in one pass
SLICE_OVERLAP_S = 1.0  # neighbouring slices overlap; a word in the overlap is taken from the earlier slice's half
SLICE_PAD_S = 1.0  # audio kept around each vocal section
MERGE_GAP_S = 2.0  # vocal sections closer than this are heard as one


def vocal_spans(res: Any, offset_s: float) -> list[tuple[float, float]]:
    """Output-time spans (seconds) that carry vocals, merged when they nearly touch."""
    spans = sorted((res.tempo.time_at(c.out_start_beat) + offset_s,
                    res.tempo.time_at(c.out_start_beat + c.src_beats * c.out_beats_per_src_beat) + offset_s)
                   for c in res.clips if c.stem == "vocals" and c.source != "bed" and c.chop is None and c.loop == 1)
    merged: list[tuple[float, float]] = []
    for a, b in spans:
        if merged and a <= merged[-1][1] + MERGE_GAP_S:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def hear(audio: np.ndarray, spans: list[tuple[float, float]], *, shift_s: float = 0.0, transcribe=None
         ) -> tuple[list[tuple[str, float]], str | None, str | None]:
    """(word, output time) for everything Whisper hears inside ``spans``, slice by slice. ``shift_s`` shortens each
    span's first slice, so a second reading of a long section cuts it at different places. Slices start at the
    vocal: one that opens on a long instrumental stretch can be skipped as silent."""
    import functools

    from glass_harbor.lyrics import _normalize, transcribe_audio

    transcribe = transcribe or functools.partial(transcribe_audio, no_speech_threshold=None)
    duration = audio.shape[0] / A.SR
    heard: list[tuple[str, float]] = []
    model = backend = None
    for a, b in spans:
        a, b = max(0.0, a - SLICE_PAD_S), min(duration, b + SLICE_PAD_S)
        t, first = a, True
        while t < b - 1e-6:
            length = SLICE_S - (shift_s % (SLICE_S / 2) if first else 0.0)
            end = min(b, t + length)
            keep_from = t if first else t + SLICE_OVERLAP_S / 2
            keep_to = end - SLICE_OVERLAP_S / 2 if end < b else end
            raw, model, backend = transcribe(audio[int(t * A.SR):int(end * A.SR)])
            for seg in raw:
                for w in seg["words"]:
                    word, at = _normalize(w["word"]), t + float(w["start"])
                    if word and keep_from <= at < keep_to:
                        heard.append((word, at))
            if end >= b:
                break
            t, first = end - SLICE_OVERLAP_S, False
    return heard, model, backend


def match_words(expected: list[tuple[str, float]], heard: list[tuple[str, float]], *,
                window: float = MATCH_WINDOW_S) -> int:
    """How many expected (word, time) pairs Whisper heard: the same word within ``window`` seconds, each heard word
    used once."""
    used = [False] * len(heard)
    found = 0
    for word, t in expected:
        best, best_gap = None, window
        for i, (other, u) in enumerate(heard):
            if not used[i] and other == word and abs(u - t) <= best_gap:
                best, best_gap = i, abs(u - t)
        if best is not None:
            used[best] = True
            found += 1
    return found


def _expected(res: Any, clip: Any, lyrics: dict[str, Any], offset_s: float) -> list[tuple[str, float]]:
    """The clip's lyric words with the output time each should sound at."""
    from glass_harbor.lyrics import _normalize

    src = np.array(clip.src_beat_times)
    out = np.array([res.tempo.time_at(clip.out_start_beat + i * clip.out_beats_per_src_beat)
                    for i in range(clip.src_beats + 1)]) + offset_s
    words = []
    for seg in lyrics["segments"]:
        for w in seg["words"]:
            mid = (w["start"] + w["end"]) / 2
            text = _normalize(w["word"])
            if src[0] <= mid < src[-1] and text:
                words.append((text, float(np.interp(w["start"], src, out))))
    return words


def match_spans(expected: list[tuple[str, float, float]], heard: list[tuple[str, float]], *,
                slack: float = 0.5) -> int:
    """Reference words only carry their line's span: a heard word counts anywhere inside it (plus ``slack``)."""
    used = [False] * len(heard)
    found = 0
    for word, start, end in expected:
        for i, (other, t) in enumerate(heard):
            if not used[i] and other == word and start - slack <= t <= end + slack:
                used[i] = True
                found += 1
                break
    return found


def _expected_reference(res: Any, clip: Any, reference: dict[str, Any], offset_s: float
                        ) -> list[tuple[str, float, float]]:
    from glass_harbor.lyrics_ref import expected_words

    src = np.array(clip.src_beat_times)
    out = np.array([res.tempo.time_at(clip.out_start_beat + i * clip.out_beats_per_src_beat)
                    for i in range(clip.src_beats + 1)]) + offset_s
    to_out = lambda t: float(np.interp(t, src, out))  # noqa: E731
    return [(w, to_out(a), to_out(b)) for w, a, b in expected_words(reference, src[0], src[-1])]


def _weak(judged: list[dict[str, Any]]) -> list[str]:
    """Weak = below the floor and clearly below this track's own average (sung, autotuned vocals read lower across
    the board; a clip is masked when it reads worse than the rest of the same song)."""
    total = sum(c["expected"] for c in judged)
    average = sum(c["heard"] for c in judged) / total if total else 0.0
    return [c["clip"] for c in judged if c["recall"] < WEAK_RECALL and (not total or c["recall"] < average - RELATIVE_DROP)]


def settle_weak(judged: list[dict[str, Any]], scorers: dict[str, Any], rehear) -> list[str]:
    """The weak clips once each has also been heard on a window of its own, keeping the better reading.

    A low score can come from the slicing, not the mix: the vocal sections are cut every SLICE_S seconds wherever
    that falls, and Whisper drops words around a cut in the middle of a verse. Over Starboy, two of 1 Umbrella's
    verses read 38% and 36% in the pass and 66% and 72% heard on their own, the same as the other verses; the
    auto fixes then pushed one verse 4 dB above the rest. ``rehear(start_s, end_s)`` hears one clip's window (its
    slices start at the clip's first word) and ``scorers[clip]`` scores what it heard."""
    reheard: set[str] = set()
    while True:
        todo = [c for c in judged if c["clip"] in _weak(judged) and c["clip"] not in reheard]
        if not todo:
            return _weak(judged)
        for item in todo:
            reheard.add(item["clip"])
            found = scorers[item["clip"]](rehear(item["start_s"], item["end_s"]))
            if found > item["heard"]:
                item.update(pass_recall=item["recall"], heard=found, recall=round(found / item["expected"], 2))


def listen_run(run_dir: Path, *, log=print, shift_s: float = 0.0) -> dict[str, Any]:
    """Transcribe ``run_dir``'s mix and score every vocal clip. Writes and returns listen.json. ``shift_s`` moves
    where the slices start, for an independent second reading of the same render."""
    from glass_harbor.lyrics import load_lyrics
    from glass_harbor.plan import resolve

    report = json.loads((run_dir / "render.json").read_text())
    if any(bound is not None for bound in (report.get("range") or {}).values()):
        raise ValueError("listen works on full renders, not bar-range previews")
    plan = json.loads((run_dir / "plan.json").read_text())
    res = resolve(plan)
    log(f"listening to {run_dir.name} (Whisper on the finished mix)")
    offset = float(report.get("timeline_offset_s", 0.0))
    audio = A.load(run_dir / report["files"]["wav"])
    heard, model, backend = hear(audio, vocal_spans(res, offset), shift_s=shift_s)
    clips = []
    scorers: dict[str, Any] = {}
    lyrics_cache: dict[str, Any] = {}
    for clip in res.clips:
        if clip.stem != "vocals" or clip.chop is not None or clip.loop != 1:
            continue
        if clip.track not in lyrics_cache:
            lyrics_cache[clip.track] = load_lyrics(clip.track)
        if not lyrics_cache[clip.track]:
            continue
        from glass_harbor.lyrics_ref import load_reference

        reference = load_reference(clip.track)
        if reference:  # the published words (Whisper's own transcript can share its mistakes with this pass)
            spans = _expected_reference(res, clip, reference, offset)
            if not spans:
                continue
            score = functools.partial(match_spans, spans)
            count, start, stop = len(spans), spans[0][1], spans[-1][2]
        else:
            expected = _expected(res, clip, lyrics_cache[clip.track], offset)
            if not expected:
                continue
            score = functools.partial(match_words, expected)
            count, start, stop = len(expected), expected[0][1], expected[-1][1]
        found = score(heard)
        scorers[clip.id] = score
        clips.append({"clip": clip.id, "source": clip.source, "expected": count, "heard": found,
                      "recall": round(found / count, 2), "words": "reference" if reference else "whisper",
                      "start_s": round(start, 2), "end_s": round(stop, 2)})
    # The beat's own vocal (call and response) is effects and shouts, not lyrics to follow: not judged.
    judged = [c for c in clips if c["expected"] >= MIN_WORDS and c["source"] != "bed"]
    weak = settle_weak(judged, scorers, lambda start, stop: hear(audio, [(start, stop)])[0])
    total = sum(c["expected"] for c in judged)
    result = {"model": model, "backend": backend, "clips": clips,
              "overall_recall": round(sum(c["heard"] for c in judged) / total, 2) if total else None, "weak": weak}
    (run_dir / "listen.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
