"""Drum tools that work from the beat's own drum stem: find a snare and a crash, build snare rolls, and add punch.

Fills cut from the real kit sound like the record; the generated noise FX in ``fx.py`` are the fallback.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from glass_harbor import audio as A
from glass_harbor.grid import Grid


@dataclass
class Hit:
    start: float  # seconds in the source
    length: float
    score: float
    found: bool = True


def _band_env(signal: np.ndarray, low: float, high: float) -> np.ndarray:
    from scipy.signal import butter, sosfiltfilt

    btype = "bandpass" if low > 0 else "lowpass"
    sos = butter(2, [low, high] if low > 0 else high, btype=btype, fs=A.SR, output="sos")
    return np.abs(sosfiltfilt(sos, A.mono(signal))).astype(np.float32)


def _window_db(env: np.ndarray, start: float, length: float) -> float:
    a, b = int(start * A.SR), int((start + length) * A.SR)
    chunk = env[max(0, a):max(0, b)]
    return float(20 * np.log10(np.sqrt(np.mean(chunk ** 2)) + 1e-9)) if chunk.size else -120.0


def find_snare(drums: np.ndarray, grid: Grid) -> Hit | None:
    """The cleanest backbeat hit (beats 2 and 4): strong 200 Hz-5 kHz body, little kick under it, quiet before."""
    body = _band_env(drums, 200, 5000)
    low = _band_env(drums, 0, 100)
    beats = grid.beats
    best: Hit | None = None
    length = min(0.25, 0.75 * grid.period)
    for index in range(grid.first_downbeat + 1, len(beats) - 1, 2):  # beats 2 and 4 of each bar
        t = beats[index]
        if t < 0.05 or t + length > drums.shape[0] / A.SR:
            continue
        hit_db = _window_db(body, t, 0.06)
        kick_db = _window_db(low, t, 0.06)
        before_db = _window_db(body, t - 0.08, 0.07)
        score = hit_db - 0.5 * max(0.0, kick_db - hit_db + 6) - 0.5 * max(0.0, before_db - hit_db + 12)
        if best is None or score > best.score:
            best = Hit(start=max(0.0, t - 0.005), length=length, score=score)
    if best is None or best.score < -45:
        return None
    return best


def find_crash(drums: np.ndarray, grid: Grid) -> Hit | None:
    """A downbeat with a bright, long-decaying top end (a crash or a ride swell)."""
    top = _band_env(drums, 6000, 16000)
    best: Hit | None = None
    for bar in range(1, grid.bar_count):
        t = grid.bar_time(bar)
        if t + 2.0 > drums.shape[0] / A.SR:
            break
        onset = _window_db(top, t, 0.1)
        tail = _window_db(top, t + 0.8, 0.6)
        before = _window_db(top, t - 0.3, 0.25)
        score = onset + (tail - onset) * 0.5 - max(0.0, before - onset + 6)
        if onset - before > 6 and (best is None or score > best.score):
            best = Hit(start=max(0.0, t - 0.005), length=2.0, score=score)
    return best


def synth_crash(seconds: float = 2.5, seed: int = 5) -> np.ndarray:
    """Fallback crash: bright noise with metallic band peaks and a long decay."""
    from scipy.signal import butter, sosfilt

    frames = int(seconds * A.SR)
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal((frames, 2)).astype(np.float32)
    bright = sosfilt(butter(2, 4000, "highpass", fs=A.SR, output="sos"), noise, axis=0)
    metal = sum(sosfilt(butter(2, [f * 0.97, f * 1.03], "bandpass", fs=A.SR, output="sos"), noise, axis=0)
                for f in (5200, 7400, 9800))
    t = np.arange(frames) / A.SR
    env = np.exp(-t * 1.8)[:, None]
    out = (0.7 * bright + 1.5 * metal) * env
    return (0.8 * out / (np.max(np.abs(out)) + 1e-9)).astype(np.float32)


def _repitch(hit: np.ndarray, semitones: float) -> np.ndarray:
    if not semitones:
        return hit
    rate = 2 ** (semitones / 12)
    positions = np.arange(0, hit.shape[0] - 1, rate)
    return np.stack([np.interp(positions, np.arange(hit.shape[0]), hit[:, c]) for c in range(2)], axis=1).astype(np.float32)


def snare_roll(snare: np.ndarray, seconds: float, beat_seconds: float, *, rise_semitones: float = 4.0) -> np.ndarray:
    """Accelerating roll that ends on the next downbeat: 8ths, then 16ths, then 32nds, rising in level and pitch."""
    frames = int(round(seconds * A.SR))
    out = np.zeros((frames, 2), dtype=np.float32)
    beats = seconds / beat_seconds
    times: list[float] = []
    t = 0.0
    while t < beats - 1e-6:
        progress = t / beats
        step = 0.5 if progress < 0.5 else 0.25 if progress < 0.75 else 0.125
        times.append(t)
        t += step
    for i, beat in enumerate(times):
        progress = beat / beats
        start = int(round(beat * beat_seconds * A.SR))
        nxt = int(round(times[i + 1] * beat_seconds * A.SR)) if i + 1 < len(times) else frames
        hit = _repitch(snare, rise_semitones * progress)[: max(0, nxt - start)].copy()
        fade = min(hit.shape[0], int(0.004 * A.SR))
        if fade:
            hit[-fade:] *= np.linspace(1, 0, fade)[:, None]
        gain = 10 ** ((-14 + 14 * progress ** 1.5) / 20)
        out[start:start + hit.shape[0]] += hit * gain
    return out


def _follow(env: np.ndarray, attack: float, release: float, hop_s: float) -> np.ndarray:
    up, down = 1 - np.exp(-hop_s / attack), 1 - np.exp(-hop_s / release)
    out = np.empty_like(env)
    current = float(env[0])
    for i, value in enumerate(env):
        current += (value - current) * (up if value > current else down)
        out[i] = current
    return out


def punch(drums: np.ndarray, *, attack_db: float = 3.0, parallel: float = 0.3, crossover_hz: float = 900.0) -> np.ndarray:
    """Transient shaping (up to ``attack_db`` on hits) plus parallel compression, below ``crossover_hz`` only:
    kick and snare body get punch while hats and shakers (which sit on the vocal) are left as they were."""
    from scipy.signal import butter, sosfiltfilt

    low = sosfiltfilt(butter(4, crossover_hz, btype="lowpass", fs=A.SR, output="sos"), drums, axis=0).astype(np.float32)
    high = drums - low  # zero-phase split: low + high reconstructs the input exactly
    return (_punch_band(low, attack_db=attack_db, parallel=parallel) + high).astype(np.float32)


def _punch_band(drums: np.ndarray, *, attack_db: float, parallel: float) -> np.ndarray:
    import pedalboard

    hop = 32
    mono = np.abs(A.mono(drums))
    blocks = mono.size // hop
    if blocks < 8:
        return drums
    peaks = mono[: blocks * hop].reshape(blocks, hop).max(axis=1)
    hop_s = hop / A.SR
    fast = _follow(peaks, 0.0005, 0.03, hop_s)
    slow = _follow(peaks, 0.015, 0.03, hop_s)
    transient_db = np.clip(20 * np.log10((fast + 1e-9) / (slow + 1e-9)), 0, 12)
    gain_db = attack_db * transient_db / 12
    curve = np.interp(np.arange(drums.shape[0]), np.arange(blocks) * hop + hop / 2, gain_db)
    shaped = drums * (10 ** (curve / 20))[:, None]
    level = float(np.sqrt(np.mean(shaped ** 2))) + 1e-9
    comp = pedalboard.Compressor(threshold_db=20 * np.log10(level) - 6, ratio=8.0, attack_ms=1.0, release_ms=80.0)
    squashed = comp(shaped.T, A.SR).T
    squashed *= level / (float(np.sqrt(np.mean(squashed ** 2))) + 1e-9)
    out = shaped + parallel * squashed
    out *= float(np.sqrt(np.mean(drums ** 2))) / (float(np.sqrt(np.mean(out ** 2))) + 1e-9)
    return out.astype(np.float32)
