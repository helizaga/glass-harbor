"""Lyrics with word timings (local Whisper on Apple Silicon via mlx-whisper), mapped onto the beat grid.

Gives the planner what bar-level energy cannot: where lines start and end, which line is the hook, and exact word
positions for chops. Transcripts stay in the gitignored library; never copy lyrics into committed files.
"""

from __future__ import annotations

import functools

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from glass_harbor import audio as A
from glass_harbor import library
from glass_harbor.grid import Grid

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"
WHISPER_SR = 16000


def lyrics_path(track_id: str) -> Path:
    return library.track_dir(track_id) / "lyrics.json"


def load_lyrics(track_id: str) -> dict[str, Any] | None:
    path = lyrics_path(track_id)
    return json.loads(path.read_text()) if path.exists() else None


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9' ]+", "", text.lower()).strip()


def _refine_onsets(words: list[dict[str, Any]], vocal: np.ndarray) -> None:
    """Snap each word start to the nearest vocal energy rise within 80 ms (Whisper timings are coarse)."""
    hop = 128
    frames = A.mono(vocal)
    usable = frames.size // hop * hop
    if usable == 0:
        return
    env = np.sqrt(np.mean(frames[:usable].reshape(-1, hop) ** 2, axis=1))
    rise = np.maximum(0.0, np.diff(env, prepend=env[:1]))
    frame_s = hop / A.SR
    radius = int(0.08 / frame_s)
    for word in words:
        center = int(word["start"] / frame_s)
        lo, hi = max(0, center - radius), min(rise.size, center + radius + 1)
        if hi - lo < 3:
            continue
        peak = lo + int(np.argmax(rise[lo:hi]))
        if rise[peak] > 0:
            word["start"] = round(min(peak * frame_s, word["end"] - 0.02), 3)


FASTER_WHISPER_MODEL = "large-v3-turbo"


def whisper_backend() -> str | None:
    """mlx-whisper on Apple Silicon, faster-whisper (CTranslate2) on Windows/Linux, else None."""
    import importlib.util

    if importlib.util.find_spec("mlx_whisper"):
        return "mlx"
    if importlib.util.find_spec("faster_whisper"):
        return "faster"
    return None


def _segments_mlx(signal: np.ndarray, model: str, language: str | None,
                  no_speech_threshold: float | None = 0.6) -> list[dict[str, Any]]:
    import mlx_whisper

    result = mlx_whisper.transcribe(signal, path_or_hf_repo=model, word_timestamps=True, language=language,
                                    condition_on_previous_text=False, hallucination_silence_threshold=2.0,
                                    no_speech_threshold=no_speech_threshold, verbose=None)
    return [{"text": seg["text"], "words": [{"word": w["word"], "start": w["start"], "end": w["end"],
                                             "probability": w.get("probability", 0.0)} for w in seg.get("words", [])]}
            for seg in result.get("segments", [])]


@functools.lru_cache(maxsize=2)
def _faster_model(model: str) -> Any:
    """Loaded once per process: the listening pass transcribes a mix in many short slices."""
    from faster_whisper import WhisperModel

    try:
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        device = "cpu"
    return WhisperModel(model, device=device, compute_type="float16" if device == "cuda" else "int8")


def _segments_faster(signal: np.ndarray, model: str, language: str | None,
                     no_speech_threshold: float | None = 0.6) -> list[dict[str, Any]]:
    whisper = _faster_model(model)
    segments, _ = whisper.transcribe(signal, language=language, word_timestamps=True,
                                     condition_on_previous_text=False, hallucination_silence_threshold=2.0,
                                     no_speech_threshold=no_speech_threshold)
    return [{"text": seg.text, "words": [{"word": w.word, "start": w.start, "end": w.end,
                                          "probability": w.probability} for w in (seg.words or [])]}
            for seg in segments]


def transcribe_audio(audio: np.ndarray, *, model: str | None = None, language: str | None = "en",
                     backend: str | None = None, no_speech_threshold: float | None = 0.6
                     ) -> tuple[list[dict[str, Any]], str, str]:
    """Whisper with word timestamps on any audio at ``A.SR``. Returns (raw segments, model, backend).
    ``no_speech_threshold=None`` never skips a window as silent (vocals under a loud beat can look like music)."""
    import soxr

    backend = backend or whisper_backend()
    if backend is None:
        raise RuntimeError("lyrics need mlx-whisper (Apple Silicon) or faster-whisper: pip install -e '.[lyrics]'")
    signal = soxr.resample(A.mono(audio), A.SR, WHISPER_SR).astype(np.float32)
    if backend == "mlx":
        model = model or DEFAULT_MODEL
        return _segments_mlx(signal, model, language, no_speech_threshold), model, backend
    model = model or FASTER_WHISPER_MODEL
    return _segments_faster(signal, model, language, no_speech_threshold), model, backend


def transcribe(track_id: str, *, model: str | None = None, language: str | None = "en",
               backend: str | None = None) -> dict[str, Any]:
    stems = library.available_stems(track_id)
    stem = "vocals" if "vocals" in stems else "mix"
    vocal = library.load_audio(track_id, stem)
    raw, model, backend = transcribe_audio(vocal, model=model, language=language, backend=backend)
    segments = []
    for seg in raw:
        words = [{"word": w["word"].strip(), "start": round(float(w["start"]), 3), "end": round(float(w["end"]), 3),
                  "prob": round(float(w.get("probability") or 0.0), 3)} for w in seg["words"] if w["word"].strip()]
        if not words:
            continue
        segments.append({"start": words[0]["start"], "end": words[-1]["end"], "text": seg["text"].strip(),
                         "words": words})
    _refine_onsets([w for s in segments for w in s["words"]], vocal)
    for seg in segments:
        seg["start"] = seg["words"][0]["start"]
    data = {"model": model, "backend": backend, "stem": stem, "language": language, "segments": segments}
    lyrics_path(track_id).write_text(json.dumps(data, indent=1) + "\n")
    return data


def bar_lines(lyrics: dict[str, Any], grid: Grid) -> list[dict[str, Any]]:
    lines = []
    for seg in lyrics["segments"]:
        lines.append({
            "start_bar": round(grid.bar_at_time(seg["start"]), 2),
            "end_bar": round(grid.bar_at_time(seg["end"]), 2),
            "text": seg["text"],
        })
    return lines


def phrases_from_lyrics(lyrics: dict[str, Any], grid: Grid, *, gap_beats: float = 1.5) -> list[dict[str, int]]:
    """Vocal phrases = runs of lines separated by gaps of at least ``gap_beats``; bars rounded outward."""
    gap = gap_beats * grid.period
    phrases: list[tuple[float, float]] = []
    for seg in lyrics["segments"]:
        if phrases and seg["start"] - phrases[-1][1] < gap:
            phrases[-1] = (phrases[-1][0], seg["end"])
        else:
            phrases.append((seg["start"], seg["end"]))
    out = []
    for start, end in phrases:
        first = int(np.floor(grid.bar_at_time(start) + 0.05))
        last = int(np.ceil(grid.bar_at_time(end) - 0.05))
        out.append({"start_bar": max(1, first), "bars": max(1, last - first)})
    return out


def hooks(lyrics: dict[str, Any], grid: Grid, *, min_words: int = 2) -> list[dict[str, Any]]:
    """Lines (or 2-4 word n-grams) that repeat: the hook is usually the most repeated one."""
    lines = [(_normalize(s["text"]), s) for s in lyrics["segments"]]
    counts = Counter(text for text, _ in lines if len(text.split()) >= min_words)
    found = []
    for text, count in counts.most_common():
        if count < 2:
            break
        occurrences = [{"start_bar": round(grid.bar_at_time(s["start"]), 2), "end_bar": round(grid.bar_at_time(s["end"]), 2)}
                       for t, s in lines if t == text]
        found.append({"text": text, "count": count, "occurrences": occurrences})
    if not found:
        words = [_normalize(w["word"]) for s in lyrics["segments"] for w in s["words"]]
        grams = Counter(" ".join(words[i:i + n]) for n in (4, 3, 2) for i in range(len(words) - n + 1))
        for text, count in grams.most_common(5):
            if count >= 3:
                found.append({"text": text, "count": count, "occurrences": []})
    return found[:5]


def find_word(lyrics: dict[str, Any], word: str, occurrence: int = 1) -> dict[str, Any]:
    target = _normalize(word)
    matches = [w for s in lyrics["segments"] for w in s["words"] if _normalize(w["word"]) == target]
    if not matches:
        raise ValueError(f"word {word!r} not found in the transcript")
    if not 1 <= occurrence <= len(matches):
        raise ValueError(f"word {word!r} occurs {len(matches)} time(s); occurrence {occurrence} is out of range")
    return matches[occurrence - 1]


def update_analysis(track_id: str, lyrics: dict[str, Any]) -> dict[str, Any]:
    analysis = library.load_analysis(track_id)
    grid = Grid.from_dict(analysis["grid"])
    vocals = analysis.setdefault("stems", {}).setdefault("vocals", {})
    vocals["phrases"] = phrases_from_lyrics(lyrics, grid)
    vocals["phrases_source"] = "lyrics"
    analysis["hooks"] = [{"count": h["count"], "occurrences": h["occurrences"], "words": len(h["text"].split())}
                         for h in hooks(lyrics, grid)]
    library.save_analysis(track_id, analysis)
    return analysis
