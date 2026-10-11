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


# ---------------------------------------------------------------- FX made from the song's own audio

SOURCE_TYPES = ("snare_roll", "crash", "vocal_riser", "reverse_swell", "halftime")
ALL_TYPES = TYPES + SOURCE_TYPES


def vocal_riser(word: np.ndarray, seconds: float) -> np.ndarray:
    """One sung/rapped word stretched into a rising swell: smeared to fill the build, pitched up an octave over it,
    high-passed upward, getting louder, ending dead on the downbeat."""
    import pedalboard

    from glass_harbor.render import _fit_length, warp

    frames = int(round(seconds * A.SR))
    src_len = word.shape[0] / A.SR
    smeared = warp(word, np.array([0.0, src_len]), np.array([0.0, seconds]), 0.0, vocal=True)
    pitch = np.linspace(0.0, 12.0, smeared.shape[0])
    risen = pedalboard.time_stretch(np.ascontiguousarray(smeared.T), A.SR, stretch_factor=1.0,
                                    pitch_shift_in_semitones=pitch, high_quality=True).T
    risen = _fit_length(np.ascontiguousarray(risen, dtype=np.float32), frames)
    wet = pedalboard.Pedalboard([pedalboard.Reverb(room_size=0.8, wet_level=0.5, dry_level=0.7)])(risen.T, A.SR).T
    t = np.linspace(0.0, 1.0, frames)
    out = np.empty_like(wet)
    block = 1024
    hp = pedalboard.HighpassFilter(cutoff_frequency_hz=200.0)
    for start in range(0, frames, block):
        hp.cutoff_frequency_hz = float(200.0 * 10 ** (t[min(start, frames - 1)] * 1.0))
        out[start:start + block] = hp(wet[start:start + block].T, A.SR, reset=False).T
    out *= (10 ** ((-30 + 30 * t ** 1.4) / 20))[:, None]
    out /= max(1e-9, float(np.max(np.abs(out))))
    out[-int(0.004 * A.SR):] *= np.linspace(1, 0, int(0.004 * A.SR))[:, None]
    return (0.9 * out).astype(np.float32)


def reverse_swell(word: np.ndarray, seconds: float) -> np.ndarray:
    """Reverse reverb: the word's reverb tail played backwards, so it swells up into the word's onset."""
    import pedalboard

    frames = int(round(seconds * A.SR))
    reversed_word = np.ascontiguousarray(word[::-1])
    padded = np.pad(reversed_word, ((0, frames), (0, 0)))
    wet = pedalboard.Pedalboard([pedalboard.Reverb(room_size=0.92, damping=0.4, wet_level=1.0, dry_level=0.0,
                                                   width=1.0)])(padded.T, A.SR).T
    # Reversed back, the tail comes first and ends exactly where the word would start: keep that swell.
    swell = np.ascontiguousarray(wet[::-1])[:frames]
    swell *= np.linspace(0, 1, frames)[:, None] ** 1.5
    peak = float(np.max(np.abs(swell))) or 1.0
    return (0.8 * swell / peak).astype(np.float32)


def tape_stop(segment: np.ndarray) -> np.ndarray:
    """Varispeed slow-down to a stop over the segment's length (the classic hip hop tape stop / brake)."""
    frames = segment.shape[0]
    t = np.arange(frames) / frames
    position = (t - t ** 2 / 2) * frames  # rate falls linearly from 1 to 0
    from scipy.signal import butter, sosfiltfilt

    out = np.stack([np.interp(position, np.arange(frames), segment[:, c]) for c in range(segment.shape[1])], axis=1)
    out *= (np.sqrt(1 - t) * np.clip((1 - t) * 4, 0, 1))[:, None]  # energy falls with the speed; no end click
    # As the speed falls the pitch sinks below hearing; block that sub-audible energy so it can't thump.
    out = sosfiltfilt(butter(2, 30.0, btype="highpass", fs=A.SR, output="sos"), out, axis=0)
    return out.astype(np.float32)
