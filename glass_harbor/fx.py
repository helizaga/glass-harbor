"""Generated transition FX (no samples needed): risers, downlifters, impacts.

Each generator returns stereo float32 of exactly the requested length so builds end on the drop's downbeat.
"""

from __future__ import annotations

import numpy as np

from glass_harbor import audio as A

TYPES = ("riser", "downlifter", "impact")


def _noise(frames: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal((frames, 2)).astype(np.float32)


def _sweep_filter(noise: np.ndarray, start_hz: float, end_hz: float) -> np.ndarray:
    """Band-pass noise whose centre glides exponentially from start_hz to end_hz (block-wise biquads)."""
    from scipy.signal import butter, sosfilt, sosfilt_zi

    frames = noise.shape[0]
    block = 1024
    out = np.empty_like(noise)
    zi = None
    count = int(np.ceil(frames / block))
    for i in range(count):
        t = i / max(1, count - 1)
        centre = start_hz * (end_hz / start_hz) ** t
        low, high = centre / 1.6, min(centre * 1.6, A.SR / 2 - 100)
        sos = butter(2, [low, high], btype="bandpass", fs=A.SR, output="sos")
        chunk = noise[i * block:(i + 1) * block]
        if zi is None:
            zi = np.stack([sosfilt_zi(sos)] * 2, axis=-1) * 0.0
        filtered, zi = sosfilt(sos, chunk, axis=0, zi=zi)
        out[i * block:(i + 1) * block] = filtered
    peak = float(np.max(np.abs(out))) or 1.0
    return (out / peak).astype(np.float32)


def riser(seconds: float, *, seed: int = 7) -> np.ndarray:
    frames = int(round(seconds * A.SR))
    body = _sweep_filter(_noise(frames, seed), 250.0, 9000.0)
    t = np.linspace(0.0, 1.0, frames)
    envelope = (10 ** ((-36 + 36 * t ** 1.6) / 20))[:, None]
    tone = np.sin(2 * np.pi * np.cumsum(220 * 4 ** t) / A.SR)[:, None] * 0.25 * t[:, None] ** 2
    out = (body * 0.8 + tone) * envelope
    out[-int(0.004 * A.SR):] *= np.linspace(1, 0, int(0.004 * A.SR))[:, None]  # stop dead on the downbeat
    return out.astype(np.float32)


def downlifter(seconds: float, *, seed: int = 11) -> np.ndarray:
    frames = int(round(seconds * A.SR))
    body = _sweep_filter(_noise(frames, seed), 8000.0, 200.0)
    t = np.linspace(0.0, 1.0, frames)
    envelope = (10 ** ((-48 * t ** 0.7) / 20))[:, None]
    return (body * envelope).astype(np.float32)


def impact(seconds: float) -> np.ndarray:
    frames = int(round(seconds * A.SR))
    t = np.arange(frames) / A.SR
    freq = 38 + 50 * np.exp(-t * 9)
    boom = np.sin(2 * np.pi * np.cumsum(freq) / A.SR) * np.exp(-t * 2.2)
    noise = np.random.default_rng(3).standard_normal(frames) * np.exp(-t * 14) * 0.35
    mono = boom + noise
    mono[: int(0.002 * A.SR)] *= np.linspace(0, 1, int(0.002 * A.SR))
    return np.repeat((0.9 * mono / max(1e-9, float(np.max(np.abs(mono)))))[:, None], 2, axis=1).astype(np.float32)


def generate(kind: str, seconds: float) -> np.ndarray:
    if kind == "riser":
        return riser(seconds)
    if kind == "downlifter":
        return downlifter(seconds)
    if kind == "impact":
        return impact(seconds)
    raise ValueError(f"unknown fx type {kind!r}; expected one of {', '.join(TYPES)}")
