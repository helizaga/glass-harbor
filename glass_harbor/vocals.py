"""Acapella treatment that makes a separated vocal sit like a mixed record vocal.

- word-safe edges: clip boundaries move to gaps between words (lyrics) or to quiet points (energy), never mid-word
- rider: phrase-level gain riding to an even level, like an engineer riding the fader
- chain: EQ (mud cut, presence, air), de-esser, two-stage compression, light saturation, a plate reverb send, and
  tempo-synced delay throws on the last word of each line
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from glass_harbor import audio as A

CHAINS = ("rap", "hook", "dry", "none")
NOMINAL_DB = -20.0  # the chain runs at a fixed level so its thresholds mean the same thing on every acapella


@dataclass
class Edges:
    start: float  # source seconds where the vocal may start (inclusive)
    end: float  # source seconds where it must be silent again
    start_note: str = ""
    end_note: str = ""
    words_cut: int = 0


@dataclass
class ChainSettings:
    reverb_mix: float
    throw_mix: float
    throws: bool
    saturation: float = 0.12
    doubles: bool = False
    extras: dict[str, Any] = field(default_factory=dict)


PRESETS = {
    "rap": ChainSettings(reverb_mix=0.10, throw_mix=0.35, throws=True),
    "hook": ChainSettings(reverb_mix=0.18, throw_mix=0.45, throws=True, saturation=0.15, doubles=True),
    "dry": ChainSettings(reverb_mix=0.0, throw_mix=0.0, throws=False),
}


# ---------------------------------------------------------------- edges


def _junctions(words: list[dict[str, Any]]) -> list[tuple[float, float]]:
    """Points where a cut is safe, with the silence available there (seconds): just before a word, just after a
    word, or exactly where two touching words meet."""
    points: list[tuple[float, float]] = []
    for i, word in enumerate(words):
        prev_end = words[i - 1]["end"] if i else -1.0
        next_start = words[i + 1]["start"] if i + 1 < len(words) else float("inf")
        before, after = word["start"] - 0.02, word["end"] + 0.03
        if before >= prev_end:
            points.append((max(0.0, before), min(1.0, word["start"] - prev_end)))
        if after <= next_start:
            points.append((after, min(1.0, next_start - word["end"])))
        elif i + 1 < len(words):  # touching or overlapping timestamps: cut where they meet
            points.append(((word["end"] + next_start) / 2 if next_start < word["end"] else word["end"], 0.0))
    return points


def _inside(words: list[dict[str, Any]], t: float, margin: float = 0.03) -> dict[str, Any] | None:
    return next((w for w in words if w["start"] + margin < t < w["end"] - margin), None)


def _snap(boundary: float, junctions: list[tuple[float, float]], lo: float, hi: float) -> float | None:
    best, best_score = None, float("inf")
    for point, gap in junctions:
        if lo <= point <= hi:
            score = abs(point - boundary) - 0.5 * min(gap, 0.3)  # prefer nearby cuts with real silence
            if score < best_score:
                best, best_score = point, score
    return best


def word_safe_edges(start: float, end: float, words: list[dict[str, Any]] | None, beat: float,
                    vocal: np.ndarray | None = None) -> Edges:
    """Move [start, end) to the nearest junction between words so no word is cut (lyrics), or to the nearest quiet
    point (no lyrics). Rap words often touch, so cuts go *between* words rather than around one."""
    edges = Edges(start, end)
    if words:
        junctions = _junctions(words)
        word = _inside(words, start)
        if word is not None:
            snapped = _snap(start, junctions, start - beat, start + 0.5 * beat)
            if snapped is not None:
                edges.start = snapped
                edges.start_note = f"start moved to a word gap ({'before' if snapped < start else 'after'} '{word['word']}')"
        word = _inside(words, end)
        if word is not None:
            snapped = _snap(end, junctions, max(edges.start + beat, end - beat), end + 0.75 * beat)
            if snapped is not None:
                edges.end = snapped
                edges.end_note = f"end moved to a word gap ({'before' if snapped < end else 'after'} '{word['word']}')"
        edges.words_cut = int(_inside(words, edges.start) is not None) + int(_inside(words, edges.end) is not None)
        return edges
    if vocal is not None:  # no lyrics: snap each edge to the quietest point nearby
        env = _envelope_db(vocal)
        edges.start, edges.start_note = _quiet_point(env, start, start - 0.25 * beat, start + 0.25 * beat), "quiet point"
        edges.end, edges.end_note = _quiet_point(env, end, end - 0.5 * beat, end + 0.25 * beat), "quiet point"
    return edges


def _envelope_db(signal: np.ndarray, hop: int = 441) -> np.ndarray:
    mono = A.mono(signal)
    frames = mono.size // hop
    if frames == 0:
        return np.full(1, -120.0)
    rms = np.sqrt(np.mean(mono[: frames * hop].reshape(frames, hop) ** 2, axis=1))
    return 20 * np.log10(rms + 1e-9)


def _quiet_point(env: np.ndarray, at: float, lo: float, hi: float, hop_s: float = 0.01) -> float:
    a, b = max(0, int(lo / hop_s)), min(env.size, int(hi / hop_s) + 1)
    if b - a < 2 or env[min(env.size - 1, int(at / hop_s))] < np.max(env) - 35:
        return at  # already quiet at the boundary
    return float((a + int(np.argmin(env[a:b]))) * hop_s)


def mask(audio: np.ndarray, start: float, end: float, fade_in: float = 0.008, fade_out: float = 0.025) -> np.ndarray:
    """Silence outside [start, end) seconds (clip-local) with short fades."""
    out = audio.copy()
    n = out.shape[0]
    s0, s1 = max(0, int(start * A.SR)), min(n, int(end * A.SR))
    out[:s0] = 0.0
    out[s1:] = 0.0
    fi, fo = int(fade_in * A.SR), int(fade_out * A.SR)
    if s1 - s0 > fi + fo:
        out[s0:s0 + fi] *= np.linspace(0, 1, fi)[:, None]
        out[s1 - fo:s1] *= np.linspace(1, 0, fo)[:, None]
    return out


# ---------------------------------------------------------------- rider


def ride(vocal: np.ndarray, *, max_boost_db: float = 4.0, max_cut_db: float = 6.0,
         window: float = 0.4) -> tuple[np.ndarray, float]:
    """Even out phrase levels: per-window gain toward the median active level, smoothed, held through gaps.
    Returns (audio, largest correction in dB)."""
    hop = int(0.1 * A.SR)
    size = int(window * A.SR)
    mono = A.mono(vocal)
    if mono.size < size:
        return vocal, 0.0
    starts = np.arange(0, mono.size - size, hop)
    levels = np.array([20 * np.log10(np.sqrt(np.mean(mono[s:s + size] ** 2)) + 1e-9) for s in starts])
    active = levels > max(-50.0, float(np.max(levels)) - 18.0)  # voiced passages, not breaths or bleed
    if active.sum() < 4:
        return vocal, 0.0
    target = float(np.median(levels[active]))
    gains = np.zeros(levels.size)
    held = 0.0
    for i, (level, on) in enumerate(zip(levels, active)):
        if on:
            held = float(np.clip(target - level, -max_cut_db, max_boost_db))
        gains[i] = held
    # Smooth (about 300 ms) so the ride follows phrases, not syllables.
    kernel = np.hanning(7)
    smooth = np.convolve(gains, kernel / kernel.sum(), mode="same")
    curve = np.interp(np.arange(mono.size), starts + size / 2, smooth)
    return (vocal * (10 ** (curve / 20))[:, None]).astype(np.float32), float(np.max(np.abs(smooth)))


# ---------------------------------------------------------------- chain


def _active_rms_db(signal: np.ndarray) -> float:
    env = _envelope_db(signal)
    on = env[env > max(-60.0, float(np.max(env)) - 30.0)]
    return float(20 * np.log10(np.sqrt(np.mean((10 ** (on / 20)) ** 2)) + 1e-12)) if on.size else -120.0


def _deess(signal: np.ndarray, max_cut_db: float = 6.0) -> np.ndarray:
    """Dynamic cut of 5.5-9 kHz when sibilance outweighs the rest of the voice."""
    from scipy.signal import butter, sosfiltfilt

    sos = butter(2, [5500, 9000], btype="bandpass", fs=A.SR, output="sos")
    band = sosfiltfilt(sos, signal, axis=0).astype(np.float32)
    hop = 256
    n = signal.shape[0]
    frames = n // hop
    if frames == 0:
        return signal
    full = np.sqrt(np.mean(A.mono(signal)[: frames * hop].reshape(frames, hop) ** 2, axis=1)) + 1e-9
    sib = np.sqrt(np.mean(A.mono(band)[: frames * hop].reshape(frames, hop) ** 2, axis=1)) + 1e-9
    excess = 20 * np.log10(sib / full) + 6.0  # sibilance louder than about -6 dB re the whole voice
    cut_db = np.clip(excess, 0.0, max_cut_db)
    cut = 1 - 10 ** (-np.interp(np.arange(n), np.arange(frames) * hop + hop / 2, cut_db) / 20)
    return (signal - band * cut[:, None]).astype(np.float32)


def _double(x: np.ndarray, cents: float, delay_s: float, pan: float) -> np.ndarray:
    import pedalboard

    shifted = pedalboard.Pedalboard([pedalboard.PitchShift(semitones=cents / 100.0),
                                     pedalboard.Delay(delay_seconds=delay_s, feedback=0.0, mix=1.0)])(x.T, A.SR).T
    mono = A.mono(shifted)
    left, right = (1.0, 1.0 - pan) if pan > 0 else (1.0 + pan, 1.0)
    return np.stack([mono * left, mono * right], axis=1).astype(np.float32)


def add_layers(x: np.ndarray, *, doubles: bool, octave: bool) -> np.ndarray:
    """Chorus thickening: two detuned, slightly late, panned doubles (-9 dB) and an optional octave-down layer
    (-15 dB). Verses stay single and centred so the hooks feel bigger by contrast."""
    import pedalboard

    out = x.copy()
    if doubles:
        out += A.db_to_gain(-9.0) * (_double(x, +8.0, 0.018, 0.65) + _double(x, -8.0, 0.026, -0.65))
    if octave:
        low = pedalboard.Pedalboard([pedalboard.PitchShift(semitones=-12.0),
                                     pedalboard.LowpassFilter(cutoff_frequency_hz=3000.0)])(x.T, A.SR).T
        out += A.db_to_gain(-15.0) * low
    return out.astype(np.float32)


def tune(vocal: np.ndarray, key_tonic: int, key_mode: str, strength: float) -> tuple[np.ndarray, float]:
    """Light pitch correction: pull steady sung notes part of the way (``strength``) to the nearest note of the
    key; unpitched rap and transitions are left alone. Returns (audio, mean correction in cents)."""
    import librosa
    import pedalboard

    if strength <= 0:
        return vocal, 0.0
    sr = 22050
    y = librosa.resample(A.mono(vocal), orig_sr=A.SR, target_sr=sr)
    hop = 512
    f0, voiced, prob = librosa.pyin(y, fmin=70, fmax=900, sr=sr, frame_length=2048, hop_length=hop)
    steps = [0, 2, 3, 5, 7, 8, 10] if key_mode == "minor" else [0, 2, 4, 5, 7, 9, 11]
    scale = np.array([(key_tonic + s) % 12 for s in steps])
    correction = np.zeros(f0.size)
    for i, (freq, ok, p) in enumerate(zip(f0, voiced, prob)):
        if not ok or p < 0.6 or not np.isfinite(freq):
            continue
        midi = 69 + 12 * np.log2(freq / 440.0)
        candidates = np.array([round((midi - pc) / 12) * 12 + pc for pc in scale])
        target = candidates[np.argmin(np.abs(candidates - midi))]
        correction[i] = (target - midi) * strength
    if not np.any(correction):
        return vocal, 0.0
    kernel = np.ones(5) / 5
    correction = np.convolve(correction, kernel, mode="same")
    times = np.arange(f0.size) * hop / sr
    per_sample = np.interp(np.arange(vocal.shape[0]) / A.SR, times, correction)
    out = pedalboard.time_stretch(np.ascontiguousarray(vocal.T), A.SR, stretch_factor=1.0,
                                  pitch_shift_in_semitones=per_sample.astype(np.float64), high_quality=True,
                                  preserve_formants=True).T
    out = np.ascontiguousarray(out[: vocal.shape[0]], dtype=np.float32)
    if out.shape[0] < vocal.shape[0]:
        out = np.pad(out, ((0, vocal.shape[0] - out.shape[0]), (0, 0)))
    active = np.abs(correction) > 0
    return out, float(np.mean(np.abs(correction[active])) * 100) if active.any() else 0.0


def apply_chain(vocal: np.ndarray, preset: str, *, beat_seconds: float,
                throw_regions: list[tuple[float, float]] | None = None, split: bool = False,
                doubles: bool | None = None, octave: bool = False):
    """Process a (tail-padded) vocal. Level in = level out, so plan gains keep their meaning.
    With ``split=True`` returns (dry, wet) so the reverb/delay returns can be pumped separately."""
    import pedalboard

    if preset == "none":
        return (vocal, np.zeros_like(vocal)) if split else vocal
    settings = PRESETS[preset]
    level = _active_rms_db(vocal)
    if level <= -100:
        return (vocal, np.zeros_like(vocal)) if split else vocal
    trim = A.db_to_gain(NOMINAL_DB - level)
    x = vocal * trim

    eq = pedalboard.Pedalboard([
        pedalboard.HighpassFilter(cutoff_frequency_hz=90.0),
        pedalboard.PeakFilter(cutoff_frequency_hz=300.0, gain_db=-3.0, q=1.0),
        pedalboard.PeakFilter(cutoff_frequency_hz=4000.0, gain_db=2.5, q=0.8),
        pedalboard.HighShelfFilter(cutoff_frequency_hz=10000.0, gain_db=2.0, q=0.7),
    ])
    x = eq(x.T, A.SR).T
    x = _deess(x)
    dynamics = pedalboard.Pedalboard([
        pedalboard.Compressor(threshold_db=NOMINAL_DB + 2, ratio=4.0, attack_ms=3.0, release_ms=60.0),
        pedalboard.Compressor(threshold_db=NOMINAL_DB - 4, ratio=2.0, attack_ms=25.0, release_ms=250.0),
    ])
    x = dynamics(x.T, A.SR).T
    if settings.saturation:
        drive = 2.5
        wet = np.tanh(x * drive / A.db_to_gain(NOMINAL_DB + 10)) * A.db_to_gain(NOMINAL_DB + 10) / drive
        x = (1 - settings.saturation) * x + settings.saturation * wet
    x = x * A.db_to_gain(level - _active_rms_db(x))  # back to the input level
    use_doubles = settings.doubles if doubles is None else doubles
    if use_doubles or octave:
        x = add_layers(x, doubles=use_doubles, octave=octave)
        x = x * A.db_to_gain(level - _active_rms_db(x))  # thicker, not louder

    wet = np.zeros_like(x)
    send_filters = [pedalboard.HighpassFilter(cutoff_frequency_hz=250.0), pedalboard.LowpassFilter(cutoff_frequency_hz=9000.0)]
    if settings.reverb_mix:
        plate = pedalboard.Pedalboard([*send_filters, pedalboard.Delay(delay_seconds=0.025, feedback=0.0, mix=1.0),
                                       pedalboard.Reverb(room_size=0.35, damping=0.6, wet_level=1.0, dry_level=0.0,
                                                         width=1.0)])
        wet = wet + settings.reverb_mix * plate(x.T, A.SR).T
    if settings.throws and throw_regions:
        throw_in = np.zeros_like(x)
        for start, end in throw_regions:
            throw_in += mask(x, start, end, fade_in=0.005, fade_out=0.04)
        echo = pedalboard.Pedalboard([pedalboard.HighpassFilter(cutoff_frequency_hz=300.0),
                                      pedalboard.LowpassFilter(cutoff_frequency_hz=6000.0),
                                      pedalboard.Delay(delay_seconds=0.75 * beat_seconds, feedback=0.38, mix=1.0)])
        wet = wet + settings.throw_mix * echo(throw_in.T, A.SR).T
    dry = np.ascontiguousarray(x, dtype=np.float32)
    wet = np.ascontiguousarray(wet, dtype=np.float32)
    return (dry, wet) if split else dry + wet


def default_chain(stem: str, is_chop: bool) -> str:
    if stem != "vocals":
        return "none"
    return "dry" if is_chop else "rap"


def throw_regions_from_words(segments: list[dict[str, Any]], to_clip_time, window: tuple[float, float]) -> list[tuple[float, float]]:
    """Last word of each lyric line inside the clip, mapped to clip-local seconds."""
    regions = []
    for seg in segments:
        last = seg["words"][-1] if seg.get("words") else None
        if not last or not (window[0] <= last["start"] and last["end"] <= window[1]):
            continue
        a, b = to_clip_time(last["start"]), to_clip_time(last["end"])
        if b > a:
            regions.append((a, b + 0.03))
    return regions


def describe_edges(edges: Edges, original: tuple[float, float]) -> dict[str, Any]:
    return {
        "start_shift_ms": round((edges.start - original[0]) * 1000, 1),
        "end_shift_ms": round((edges.end - original[1]) * 1000, 1),
        "notes": [n for n in (edges.start_note, edges.end_note) if n],
        "words_cut": edges.words_cut,
    }


def beats_needed(shift_seconds: float, beat: float) -> int:
    return max(0, int(math.ceil(shift_seconds / beat - 1e-9)))
