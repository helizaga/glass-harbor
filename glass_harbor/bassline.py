"""Make the beat's bassline follow the acapella's chords.

Same key is not enough. A vocal was written over its own bassline, and a note that sat on a chord tone there can land
a half-step from the new beat's bass (Keep Workin' holds D# and slides through C and D while Janice STFU's vocal was
written over C# -> G# -> E). Autotuning the rapper is the wrong fix; mashup producers re-program the bass to the
acapella's roots. ``follow`` does that: the new bass keeps the beat's rhythm and pumping (the bass stem's own
envelope) and plays the vocal track's original root notes, read from that track's bass under the same lyrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from glass_harbor import audio as A

CQT_SR = 11025
CQT_HOP = 128
LOWEST = 19  # G0 (24.5 Hz), MIDI note of the first CQT bin: deep sub notes (G#0, A0) are real basslines
OCTAVES = 4
KICK_SKIP_S = 0.06  # the kick's click at the start of a beat reads as a random low note
HARSH = (1, 6)  # a flat ninth or a tritone above the bass: the intervals that sound "off pitch"


def _note_strengths(audio: np.ndarray) -> np.ndarray:
    """Per semitone (rows, from G0) energy of the low end at CQT_HOP resolution."""
    import librosa

    y = librosa.resample(A.mono(audio), orig_sr=A.SR, target_sr=CQT_SR)
    if y.size < 2048:
        y = np.pad(y, (0, 2048 - y.size))
    cqt = np.abs(librosa.cqt(y, sr=CQT_SR, hop_length=CQT_HOP, fmin=librosa.midi_to_hz(LOWEST),
                             n_bins=12 * OCTAVES * 3, bins_per_octave=36))
    return cqt.reshape(12 * OCTAVES, 3, -1).sum(axis=1)


def roots(bass: np.ndarray, windows: list[tuple[float, float]]) -> list[int | None]:
    """The bass note (MIDI) sounding in each (start, end) window in seconds, or None where the bass is silent.
    ``bass`` should be a bass stem; a full mix works for 808-led hip hop but the kick can fool it."""
    strengths = _note_strengths(bass)
    loudest = float(strengths.max()) + 1e-12
    out: list[int | None] = []
    for start, end in windows:
        a = int((start + min(KICK_SKIP_S, 0.4 * (end - start))) * CQT_SR / CQT_HOP)
        b = max(a + 1, int(end * CQT_SR / CQT_HOP))
        if a >= strengths.shape[1]:
            out.append(None)
            continue
        energy = strengths[:, a:b].mean(axis=1)
        # Harmonic sum: a note is supported by its octave, twelfth, and double octave, so the fundamental wins over
        # a loud second harmonic (the CQT reads deep fundamentals quieter than they sound).
        padded = np.concatenate([energy, np.zeros(25)])
        score = energy + 0.6 * padded[12:12 + energy.size] + 0.4 * padded[19:19 + energy.size] \
            + 0.3 * padded[24:24 + energy.size]
        k = int(np.argmax(score))
        out.append(LOWEST + k if energy.max() > 0.02 * loudest else None)
    return out


def sung(vocal: np.ndarray, windows: list[tuple[float, float]]) -> list[list[int]]:
    """Pitch classes of the confidently pitched vocal frames in each window (rap syllables mostly have none)."""
    from glass_harbor.harmony import _pitch_track

    if not windows:
        return []
    lo = max(0.0, min(w[0] for w in windows))
    hi = max(w[1] for w in windows)
    segment = vocal[int(lo * A.SR):int(hi * A.SR) + 1]
    if segment.shape[0] < A.SR // 10:
        return [[] for _ in windows]
    return pitch_classes(_pitch_track(segment), windows, offset_s=lo)


def pitch_classes(midi: np.ndarray, windows: list[tuple[float, float]], *, offset_s: float = 0.0) -> list[list[int]]:
    """Split a pitch track (``harmony._pitch_track`` frames starting at ``offset_s``) into the windows."""
    from glass_harbor.harmony import HOP, SR

    out = []
    for start, end in windows:
        frames = midi[max(0, int((start - offset_s) * SR / HOP)):max(0, int((end - offset_s) * SR / HOP))]
        out.append([int(round(m)) % 12 for m in frames if not np.isnan(m)])
    return out


def clash_rate(sung_pcs: list[list[int]], bass_notes: list[int | None]) -> tuple[float, int]:
    """Share of sung frames a flat ninth or tritone above the bass note under them, and the frame count."""
    frames = harsh = 0
    for pcs, root in zip(sung_pcs, bass_notes):
        if root is None:
            continue
        for pc in pcs:
            frames += 1
            harsh += (pc - root) % 12 in HARSH
    return (harsh / frames if frames else 0.0), frames


def half_beats(beat_times: list[float] | np.ndarray) -> list[tuple[float, float]]:
    """Windows of half a beat between consecutive beat boundaries (chord changes often anticipate the bar)."""
    out = []
    for a, b in zip(beat_times[:-1], beat_times[1:]):
        mid = (a + b) / 2
        out += [(a, mid), (mid, b)]
    return out


@dataclass
class Span:
    """One followed stretch: output sample range and the target bass note (MIDI) for each sub-window in it."""
    windows: list[tuple[int, int]]  # output samples, relative to the bass clip's start
    notes: list[int | None]


def follow(bass: np.ndarray, spans: list[Span], *, glide_s: float = 0.025, xfade_s: float = 0.01) -> np.ndarray:
    """Replace ``bass`` inside ``spans`` with a sub that plays the given notes in the original bass's rhythm.

    The new notes sit in the octave nearest the original bass line's own register, so the low end keeps its weight;
    a little saturation gives them harmonics small speakers can play. Each span is level-matched to the original."""
    n = bass.shape[0]
    original = _register(bass, spans)
    freq = np.zeros(n)
    use = np.zeros(n)
    for span in spans:
        for (a, b), note in zip(span.windows, span.notes):
            a, b = max(0, a), min(n, b)
            if b <= a or note is None:
                continue
            pc = note % 12
            midi = min((pc + 12 * octave for octave in range(1, 6)), key=lambda m: abs(m - original))
            freq[a:b] = 440.0 * 2 ** ((midi - 69) / 12)
            use[a:b] = 1.0
    if not use.any():
        return bass
    held = freq.copy()  # hold the last note through gaps so the phase and glide stay smooth
    nonzero = np.flatnonzero(held)
    held = held[nonzero][np.clip(np.searchsorted(nonzero, np.arange(n), side="right") - 1, 0, None)]
    k = max(1, int(glide_s * A.SR))
    held = np.convolve(np.pad(held, (k // 2, k - k // 2 - 1), mode="edge"), np.ones(k) / k, mode="valid")
    phase = 2 * np.pi * np.cumsum(held) / A.SR
    tone = np.tanh(1.6 * (np.sin(phase) + 0.18 * np.sin(2 * phase))) / np.tanh(1.6)
    window = max(1, int(0.008 * A.SR))
    envelope = np.sqrt(np.convolve(A.mono(bass) ** 2, np.ones(window) / window, mode="same"))
    sub = (tone * envelope * np.sqrt(2))[:, None] * np.ones((1, 2))
    ramp = np.convolve(use, np.ones(max(1, int(xfade_s * A.SR))) / max(1, int(xfade_s * A.SR)), mode="same")
    for span in spans:  # level-match each span on its own (verse and chorus bass levels differ)
        a = max(0, min(w[0] for w in span.windows))
        b = min(n, max(w[1] for w in span.windows))
        mask = use[a:b] > 0
        if mask.any():
            target = np.sqrt(np.mean(bass[a:b][mask] ** 2))
            current = np.sqrt(np.mean(sub[a:b][mask] ** 2)) + 1e-12
            sub[a:b] *= target / current
    return (bass * (1 - ramp[:, None]) + sub * ramp[:, None]).astype(np.float32)


def _register(bass: np.ndarray, spans: list[Span]) -> float:
    """Median MIDI note of the original bass inside the spans (where the new notes should sit)."""
    windows = [(a / A.SR, b / A.SR) for span in spans for a, b in span.windows]
    found = [r for r in roots(bass, windows[:: max(1, len(windows) // 64)]) if r is not None]
    return float(np.median(found)) if found else 40.0  # E1


def describe(notes: list[int | None]) -> str:
    names = "C C# D D# E F F# G G# A A# B".split()
    out, last = [], None
    for note in notes:
        name = names[note % 12] if note is not None else "-"
        if name != last:
            out.append(name)
        last = name
    return " ".join(out)


def source_bass(track_id: str) -> tuple[np.ndarray, str]:
    """The best low-end source for a track's original bassline: its bass stem, else instrumental, else the mix."""
    from glass_harbor import library

    stems = library.available_stems(track_id)
    for stem in ("bass", "instrumental"):
        if stem in stems:
            return library.load_audio(track_id, stem), stem
    return library.load_audio(track_id, "mix"), "mix"


def vocal_roots(clip: Any, bass_audio: np.ndarray) -> list[int | None]:
    """Original bass notes under a vocal clip, per half beat of the clip's source (pitch-shifted with the vocal)."""
    notes = roots(bass_audio, half_beats(clip.src_beat_times))
    return [None if n is None else n + clip.semitones for n in notes]
