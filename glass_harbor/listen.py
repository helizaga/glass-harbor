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


def listen_run(run_dir: Path, *, log=print) -> dict[str, Any]:
    """Transcribe ``run_dir``'s mix and score every vocal clip. Writes and returns listen.json."""
    from glass_harbor.lyrics import _normalize, load_lyrics, transcribe_audio
    from glass_harbor.plan import resolve

    report = json.loads((run_dir / "render.json").read_text())
    if (report.get("range") or {}).get("start_bar"):
        raise ValueError("listen works on full renders, not bar-range previews")
    plan = json.loads((run_dir / "plan.json").read_text())
    res = resolve(plan)
    log(f"listening to {run_dir.name} (Whisper on the finished mix)")
    raw, model, backend = transcribe_audio(A.load(run_dir / report["files"]["wav"]))
    heard = [(_normalize(w["word"]), float(w["start"])) for seg in raw for w in seg["words"] if _normalize(w["word"])]
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
        expected = _expected(res, clip, lyrics_cache[clip.track], offset)
        if not expected:
            continue
        found = match_words(expected, heard)
        clips.append({"clip": clip.id, "source": clip.source, "expected": len(expected), "heard": found,
                      "recall": round(found / len(expected), 2),
                      "start_s": round(expected[0][1], 2), "end_s": round(expected[-1][1], 2)})
    # The beat's own vocal (call and response) is effects and shouts, not lyrics to follow: not judged.
    judged = [c for c in clips if c["expected"] >= MIN_WORDS and c["source"] != "bed"]
    total = sum(c["expected"] for c in judged)
    result = {"model": model, "backend": backend, "clips": clips,
              "overall_recall": round(sum(c["heard"] for c in judged) / total, 2) if total else None,
              "weak": [c["clip"] for c in judged if c["recall"] < WEAK_RECALL]}
    (run_dir / "listen.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
