"""An AI listening pass with the model already on this machine (no extra download).

Whisper transcribes the finished mix, and each vocal clip's own lyrics are checked against what it hears at that
moment. A clip whose words Whisper cannot make out over the beat is masked for a listener too. ``vocal_presence``
measures level in the 1-4 kHz band; this measures whether the words actually survive the beat, the reverb, and the
master. Results go to ``listen.json`` in the run folder; QA flags weak clips and ``glass-harbor auto`` lifts them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from glass_harbor import audio as A

MATCH_WINDOW_S = 0.6  # a heard word counts if it is the same word within this distance of where it should be
MIN_WORDS = 8  # clips with fewer expected words are too short to judge
WEAK_RECALL = 0.5
RELATIVE_DROP = 0.15


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


def listen_run(run_dir: Path, *, log=print, shift_s: float = 0.0) -> dict[str, Any]:
    """Transcribe ``run_dir``'s mix and score every vocal clip. Writes and returns listen.json. ``shift_s`` of
    silence in front moves Whisper's 30-second windows, for an independent second reading of the same render."""
    from glass_harbor.lyrics import _normalize, load_lyrics, transcribe_audio
    from glass_harbor.plan import resolve

    report = json.loads((run_dir / "render.json").read_text())
    if any(bound is not None for bound in (report.get("range") or {}).values()):
        raise ValueError("listen works on full renders, not bar-range previews")
    plan = json.loads((run_dir / "plan.json").read_text())
    res = resolve(plan)
    log(f"listening to {run_dir.name} (Whisper on the finished mix)")
    audio = A.load(run_dir / report["files"]["wav"])
    if shift_s > 0:
        audio = np.concatenate([np.zeros((int(shift_s * A.SR), audio.shape[1]), dtype=audio.dtype), audio])
    raw, model, backend = transcribe_audio(audio)
    heard = [(_normalize(w["word"]), float(w["start"]) - shift_s) for seg in raw for w in seg["words"]
             if _normalize(w["word"])]
    offset = float(report.get("timeline_offset_s", 0.0))
    clips = []
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
            found, count, start, stop = match_spans(spans, heard), len(spans), spans[0][1], spans[-1][2]
        else:
            expected = _expected(res, clip, lyrics_cache[clip.track], offset)
            if not expected:
                continue
            found, count, start, stop = match_words(expected, heard), len(expected), expected[0][1], expected[-1][1]
        clips.append({"clip": clip.id, "source": clip.source, "expected": count, "heard": found,
                      "recall": round(found / count, 2), "words": "reference" if reference else "whisper",
                      "start_s": round(start, 2), "end_s": round(stop, 2)})
    # The beat's own vocal (call and response) is effects and shouts, not lyrics to follow: not judged.
    judged = [c for c in clips if c["expected"] >= MIN_WORDS and c["source"] != "bed"]
    total = sum(c["expected"] for c in judged)
    result = {"model": model, "backend": backend, "clips": clips,
              "overall_recall": round(sum(c["heard"] for c in judged) / total, 2) if total else None,
              # Weak = below the floor and clearly below this track's own average (sung, autotuned vocals read lower
              # across the board; a clip is masked when it reads worse than the rest of the same song).
              "weak": [c["clip"] for c in judged if c["recall"] < WEAK_RECALL
                       and (not total or c["recall"] < sum(c["heard"] for c in judged) / total - RELATIVE_DROP)]}
    (run_dir / "listen.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
