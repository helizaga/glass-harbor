"""Will this vocal sit on this beat? A one-minute check before the full mashup.

Key and tempo come from the matcher (``compat``). On top of that, the beat's own instrumental is measured for the
things that made GLOCK over SWARM sound too busy:

- vocal room: the share of the beat's energy in 1-4 kHz, where a vocal's intelligibility lives. Beds that fit
  their vocals measured 0.2-2% here; SWARM measured 13%.
- harshness: spectral flatness in that band (distorted, noisy synths read high: SWARM 0.039, others 0.009-0.024).
- out-of-key energy: the share of the beat's harmony outside the vocal's scale.

Sung vocals get stricter limits than rap. The beat is measured without its own vocal (a quick temporary
separation when it has no instrumental stem yet), so a featured singer on the beat doesn't count as clutter.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from glass_harbor import audio as A
from glass_harbor import library

SR = 22050
EXCERPT_S = 90.0
SUNG_SHARE = 0.1  # share of a vocal's active frames with a clear pitch above which it counts as sung

# (risky, poor) limits per vocal type
LIMITS = {
    "sung": {"vocal_room": (0.03, 0.07), "harshness": (0.03, 0.05), "out_of_key": (0.36, 0.42)},
    "rap": {"vocal_room": (0.05, 0.10), "harshness": (0.035, 0.06), "out_of_key": (0.40, 0.48)},
}


def _excerpt(audio: np.ndarray) -> np.ndarray:
    import librosa

    y = librosa.resample(A.mono(audio), orig_sr=A.SR, target_sr=SR)
    half = int(EXCERPT_S / 2 * SR)
    mid = y.size // 2
    return y[max(0, mid - half): mid + half]


def _beat_without_vocal(track_id: str, log) -> tuple[np.ndarray, str]:
    """The beat's instrumental: its stem when separated, else a fast temporary separation (nothing is saved)."""
    stems = library.available_stems(track_id)
    if "instrumental" in stems:
        return library.load_audio(track_id, "instrumental"), "instrumental stem"
    from glass_harbor.separate import PROFILES, _run_audio_separator

    log(f"quick separation of {track_id} (temporary, for the fit check)")
    with tempfile.TemporaryDirectory(prefix="gh-fit-") as tmp:
        outputs = _run_audio_separator(library.audio_path(track_id), Path(tmp), **PROFILES["fast"]["all"])
        parts = [A.load(outputs[name]) for name in ("drums", "bass", "other") if name in outputs]
    if not parts:
        return library.load_audio(track_id), "full mix"
    n = min(p.shape[0] for p in parts)
    return sum(p[:n] for p in parts), "fast temporary separation"


def beat_profile(audio: np.ndarray, tonic: int, mode: str) -> dict[str, float]:
    import librosa

    y = _excerpt(audio)
    power = np.abs(librosa.stft(y, n_fft=2048, hop_length=512)) ** 2
    freqs = librosa.fft_frequencies(sr=SR, n_fft=2048)
    band = (freqs >= 1000) & (freqs < 4000)
    vocal_room = float(np.median(power[band].sum(axis=0) / (power[freqs >= 40].sum(axis=0) + 1e-12)))
    harshness = float(np.median(librosa.feature.spectral_flatness(S=power[band])))
    harmonic = librosa.effects.harmonic(y, margin=3.0)
    chroma = librosa.feature.chroma_cqt(y=harmonic, sr=SR, hop_length=1024).mean(axis=1)
    chroma = chroma / (chroma.sum() + 1e-12)
    steps = (0, 2, 4, 5, 7, 9, 11) if mode == "major" else (0, 2, 3, 5, 7, 8, 10)
    scale = {(tonic + s) % 12 for s in steps}
    out_of_key = float(sum(chroma[i] for i in range(12) if i not in scale))
    return {"vocal_room": round(vocal_room, 4), "harshness": round(harshness, 4), "out_of_key": round(out_of_key, 3)}


def sung_share(track_id: str) -> float | None:
    """Share of the vocal's active frames (60 s from the middle) that hold a clear pitch."""
    from glass_harbor.harmony import _pitch_track

    if "vocals" not in library.available_stems(track_id):
        return None
    vocal = library.load_audio(track_id, "vocals")
    mid = vocal.shape[0] // 2
    segment = vocal[max(0, mid - 30 * A.SR): mid + 30 * A.SR]
    midi = _pitch_track(segment)
    hop = segment.shape[0] / max(1, midi.size)
    mono = A.mono(segment)
    rms = np.array([np.sqrt(np.mean(mono[int(i * hop):int((i + 1) * hop)] ** 2)) for i in range(midi.size)])
    active = rms > np.percentile(rms, 40)
    return round(float(np.mean(~np.isnan(midi[active]))), 3) if active.any() else None


def assess(vocal: str, beat: str, *, log=print) -> dict[str, Any]:
    from glass_harbor import compat
    from glass_harbor.keys import Key

    vox, bed = library.load_analysis(vocal), library.load_analysis(beat)
    fit = compat.score_pair(vocal, vox, beat, bed)[0]
    sung = sung_share(vocal)
    kind = "sung" if (sung or 0) >= SUNG_SHARE else "rap"
    key = Key(int(vox["key"]["tonic"]), vox["key"]["mode"]).shifted(fit.semitones)
    audio, measured_on = _beat_without_vocal(beat, log)
    profile = beat_profile(audio, key.tonic, key.mode)
    checks = []
    for name, value in profile.items():
        risky, poor = LIMITS[kind][name]
        level = "poor" if value > poor else "risky" if value > risky else "good"
        checks.append({"check": name, "value": value, "level": level, "limits": [risky, poor]})
    if abs(fit.stretch_pct) > 6:
        checks.append({"check": "tempo", "value": fit.stretch_pct, "level": "poor", "limits": [3, 6]})
    elif abs(fit.stretch_pct) > 3:
        checks.append({"check": "tempo", "value": fit.stretch_pct, "level": "risky", "limits": [3, 6]})
    if abs(fit.semitones) > 2 or fit.relation == "clash":
        checks.append({"check": "key", "value": fit.relation, "level": "poor" if kind == "sung" else "risky",
                       "limits": None})
    levels = [c["level"] for c in checks]
    verdict = "poor" if "poor" in levels else "risky" if "risky" in levels else "good"
    reasons = {
        "vocal_room": "the beat is crowded in the 1-4 kHz vocal range (busy synths/hats will mask the vocal)",
        "harshness": "the beat's vocal range is noisy or distorted (aggressive, gritty sound design)",
        "out_of_key": "a lot of the beat's harmony sits outside the vocal's key (dark/chromatic)",
        "tempo": "the vocal needs a big tempo change",
        "key": "the keys clash or need a large vocal pitch shift",
    }
    return {"vocal": vocal, "beat": beat, "vocal_type": kind, "sung_share": sung, "measured_on": measured_on,
            "fit": {"relation": fit.relation, "semitones": fit.semitones, "tempo_ratio": fit.tempo_ratio,
                    "stretch_pct": fit.stretch_pct, "score": fit.score},
            "checks": checks, "verdict": verdict,
            "reasons": [reasons[c["check"]] for c in checks if c["level"] != "good"]}
