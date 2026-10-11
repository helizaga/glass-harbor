"""Space-making between parts: spectral ducking (Trackspacer-style) and grid-locked pumping.

Spectral ducking turns the bed down only in the frequency bins where the vocal is actually competing with it,
moment to moment, and only in the bed's centre (mid) channel, so the beat keeps its width and low end while the
vocal cuts through. Pumping is the house "breathing": parts duck on every beat and recover before the next one.
"""

from __future__ import annotations

import numpy as np

from glass_harbor import audio as A

N_FFT = 2048
HOP = 512


def _stft(signal: np.ndarray):
    from scipy.signal import stft

    return stft(signal.astype(np.float32), fs=A.SR, nperseg=N_FFT, noverlap=N_FFT - HOP)


def _istft(spec: np.ndarray, length: int) -> np.ndarray:
    from scipy.signal import istft

    _, out = istft(spec, fs=A.SR, nperseg=N_FFT, noverlap=N_FFT - HOP)
    out = out[:length]
    return np.pad(out, (0, max(0, length - out.size))).astype(np.float32)


def _smooth_time(mag: np.ndarray, attack: float = 0.01, release: float = 0.15) -> np.ndarray:
    """Asymmetric one-pole smoothing along frames (fast up, slow down), per bin."""
    frame = HOP / A.SR
    up = 1 - np.exp(-frame / attack)
    down = 1 - np.exp(-frame / release)
    out = np.empty_like(mag)
    current = mag[:, 0].copy()
    for j in range(mag.shape[1]):
        target = mag[:, j]
        coeff = np.where(target > current, up, down)
        current = current + (target - current) * coeff
        out[:, j] = current
    return out


def spectral_duck(bed: np.ndarray, trigger: np.ndarray, *, max_db: float = 6.0, level_db: float = 1.0,
                  low_hz: float = 150.0, high_hz: float = 8000.0) -> np.ndarray:
    """Cut the bed's mid channel by up to ``max_db`` in bins where the trigger (vocal) competes with it: the full
    cut once the vocal is as loud as the bed in that bin, scaling to nothing when it is 12 dB quieter. The side
    channel and the low end are left alone. ``level_db`` adds a small broadband dip."""
    from scipy.ndimage import uniform_filter1d

    n = bed.shape[0]
    mid = (bed[:, 0] + bed[:, 1]) / 2
    side = (bed[:, 0] - bed[:, 1]) / 2
    freqs, _, mid_spec = _stft(mid)
    _, _, vox_spec = _stft(A.mono(trigger))
    bed_mag = uniform_filter1d(np.abs(mid_spec), size=9, axis=0)
    vox_mag = _smooth_time(uniform_filter1d(np.abs(vox_spec), size=9, axis=0))
    rel_db = 20 * np.log10((vox_mag + 1e-9) / (bed_mag + 1e-9))
    amount = np.clip((rel_db + 12.0) / 12.0, 0.0, 1.0)
    # Band window with soft edges: nothing below the kick/bass region, little in the cymbals.
    band = np.clip((np.log2(np.maximum(freqs, 1) / low_hz) + 0.5), 0, 1) * np.clip(np.log2(high_hz / np.maximum(freqs, 1)) + 0.5, 0, 1)
    gain = 10 ** (-max_db * amount * band[:, None] / 20)
    new_mid = _istft(mid_spec * gain, n)
    out = np.stack([new_mid + side, new_mid - side], axis=1)
    if level_db:
        from glass_harbor.render import _envelope_amount

        activity = _envelope_amount(A.mono(trigger))
        out = out * (10 ** (-level_db * activity / 20))[:, None]
    return out.astype(np.float32)


def pump_curve(beat_positions: np.ndarray, *, db: float = 4.0, release: float = 0.5,
               attack: float = 0.02) -> np.ndarray:
    """Gain (linear) per sample from fractional output beat positions: dip on each beat, recover over
    ``release`` beats (curved like a sidechain compressor), with a short attack so it never clicks."""
    phase = beat_positions - np.floor(beat_positions)
    shape = np.where(phase < release, (1 - phase / release) ** 2, 0.0)
    shape = np.where(phase < attack, shape * (phase / attack), shape)
    return (10 ** (-db * shape / 20)).astype(np.float32)
