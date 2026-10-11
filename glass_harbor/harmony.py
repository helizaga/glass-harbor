"""Vocal-vs-beat harmony: chord-aware pitch correction and a pitch-clash measure.

A mashup's acapella was written over different chords. Even in the same key, a held note can land a semitone off
the new beat's chord at that moment and sound off pitch. ``harmonize`` moves only those held, clashing notes to the
nearest note the beat is actually playing (Melodyne-style), leaving rap, ad-libs, and on-chord notes untouched.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from glass_harbor import audio as A

SR = 22050
HOP = 512


@dataclass
class Note:
    start: int  # frame
    end: int
    midi: float


def _pitch_track(vocal: np.ndarray):
    import librosa

    y = librosa.resample(A.mono(vocal), orig_sr=A.SR, target_sr=SR)
    f0, voiced, prob = librosa.pyin(y, fmin=70, fmax=900, sr=SR, frame_length=2048, hop_length=HOP)
    midi = np.where(voiced & (prob > 0.7) & np.isfinite(f0), 69 + 12 * np.log2(np.nan_to_num(f0, nan=440.0) / 440), np.nan)
    return midi


def _chroma(bed: np.ndarray, frames: int) -> np.ndarray:
    import librosa

    y = librosa.resample(A.mono(bed), orig_sr=A.SR, target_sr=SR)
    if not np.any(np.abs(y) > 1e-5):
        return np.zeros((12, frames))
    chroma = librosa.feature.chroma_cqt(y=librosa.effects.harmonic(y, margin=3.0), sr=SR, hop_length=HOP)
    chroma = chroma[:, :frames]
    if chroma.shape[1] < frames:
        chroma = np.pad(chroma, ((0, 0), (0, frames - chroma.shape[1])))
    return chroma / (chroma.max(axis=0, keepdims=True) + 1e-9)


def notes(midi: np.ndarray, *, min_frames: int = 6) -> list[Note]:
    """Held notes: runs of confident pitch that stay within half a semitone (about 140 ms or longer)."""
    found = []
    start = None
    for i in range(midi.size + 1):
        value = midi[i] if i < midi.size else np.nan
        if start is not None and (np.isnan(value) or abs(value - np.nanmedian(midi[start:i])) > 0.5):
            if i - start >= min_frames:
                found.append(Note(start, i, float(np.nanmedian(midi[start:i]))))
            start = None
        if start is None and not np.isnan(value):
            start = i
    return found


def _clash(pc: int, chroma: np.ndarray) -> float:
    return float(max(chroma[(pc + 1) % 12], chroma[(pc - 1) % 12]) * (1 - chroma[pc]))


def harmonize(vocal: np.ndarray, bed: np.ndarray, *, max_shift: int = 2, strength: float = 1.0
              ) -> tuple[np.ndarray, list[dict]]:
    """Retune held vocal notes that clash with the bed's chord at that moment to the nearest strong bed note.
    ``vocal`` and ``bed`` must be time-aligned. Returns (audio, list of corrections)."""
    import pedalboard

    midi = _pitch_track(vocal)
    chroma = _chroma(bed, midi.size)
    shift = np.zeros(midi.size)
    fixes = []
    for note in notes(midi):
        held = chroma[:, note.start:note.end].mean(axis=1)
        held = held / (held.max() + 1e-9)
        pc = int(round(note.midi)) % 12
        if held[pc] >= 0.5 or _clash(pc, held) < 0.3:
            continue
        options = [d for d in range(-max_shift, max_shift + 1) if d and held[(pc + d) % 12] >= 0.7]
        if not options:
            continue
        step = min(options, key=lambda d: (abs(d), -held[(pc + d) % 12]))
        target = round(note.midi) + step
        shift[note.start:note.end] = (target - midi[note.start:note.end]) * strength
        fixes.append({"time_s": round(note.start * HOP / SR, 2), "length_s": round((note.end - note.start) * HOP / SR, 2),
                      "from": int(round(note.midi)), "to": int(target)})
    if not fixes:
        return vocal, []
    shift = np.nan_to_num(shift)
    ramp = np.hanning(5) / np.hanning(5).sum()  # glide in and out of corrections (~50 ms)
    shift = np.convolve(shift, ramp, mode="same")
    per_sample = np.interp(np.arange(vocal.shape[0]) / A.SR, np.arange(shift.size) * HOP / SR, shift)
    out = pedalboard.time_stretch(np.ascontiguousarray(vocal.T), A.SR, stretch_factor=1.0,
                                  pitch_shift_in_semitones=per_sample.astype(np.float64), high_quality=True,
                                  preserve_formants=True).T
    out = np.ascontiguousarray(out[: vocal.shape[0]], dtype=np.float32)
    if out.shape[0] < vocal.shape[0]:
        out = np.pad(out, ((0, vocal.shape[0] - out.shape[0]), (0, 0)))
    return out, fixes


def clash_by_bar(vocal: np.ndarray, bed: np.ndarray, bar_spans: list[tuple[int, tuple[int, int]]]) -> list[dict]:
    """Per bar with held sung notes: how much they rub against the bed's harmony (0 = on chord, 1 = semitone clash)."""
    midi = _pitch_track(vocal)
    chroma = _chroma(bed, midi.size)
    out = []
    for bar, (s0, s1) in bar_spans:
        a, b = int(s0 / A.SR * SR / HOP), int(s1 / A.SR * SR / HOP)
        held = [n for n in notes(midi[a:b])]
        if not held:
            continue
        frames = sum(n.end - n.start for n in held)
        score = sum(_clash(int(round(n.midi)) % 12, chroma[:, a + n.start:a + n.end].mean(axis=1)
                           / (chroma[:, a + n.start:a + n.end].mean(axis=1).max() + 1e-9)) * (n.end - n.start)
                    for n in held) / frames
        out.append({"bar": bar, "clash": round(float(score), 2), "sung_s": round(frames * HOP / SR, 2)})
    return out
