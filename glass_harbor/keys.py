"""Musical keys, Camelot notation, and template-based key estimation."""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

PITCH_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Krumhansl-Kessler probe-tone profiles.
_KK_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_KK_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
# Temperley (Kostka-Payne) profiles; more robust on pop harmony.
_TEMPERLEY_MAJOR = np.array([5.0, 2.0, 3.5, 2.0, 4.5, 4.0, 2.0, 4.5, 2.0, 3.5, 1.5, 4.0])
_TEMPERLEY_MINOR = np.array([5.0, 2.0, 3.5, 4.5, 2.0, 4.0, 2.0, 4.5, 3.5, 2.0, 1.5, 4.0])


@dataclass(frozen=True)
class Key:
    tonic: int  # pitch class 0-11
    mode: str  # "major" | "minor"

    def __post_init__(self) -> None:
        if self.mode not in ("major", "minor"):
            raise ValueError(f"mode must be major or minor, got {self.mode!r}")

    @property
    def name(self) -> str:
        return f"{PITCH_NAMES[self.tonic % 12]} {self.mode}"

    @property
    def camelot(self) -> str:
        major_tonic = self.tonic if self.mode == "major" else (self.tonic + 3) % 12
        number = ((major_tonic * 7) % 12 + 7) % 12 + 1
        return f"{number}{'B' if self.mode == 'major' else 'A'}"

    def shifted(self, semitones: int) -> "Key":
        return Key((self.tonic + semitones) % 12, self.mode)

    def to_dict(self) -> dict:
        return {"name": self.name, "tonic": self.tonic, "mode": self.mode, "camelot": self.camelot}


def parse_key(text: str) -> Key:
    """Accept 'A minor', 'Am', 'A min', 'F# major', 'Bb', '8A', '11B'."""
    value = text.strip()
    camelot = re.fullmatch(r"(1[0-2]|[1-9])\s*([ABab])", value)
    if camelot:
        number, letter = int(camelot.group(1)), camelot.group(2).upper()
        major_tonic = ((number - 8) * 7) % 12
        if letter == "B":
            return Key(major_tonic, "major")
        return Key((major_tonic - 3) % 12, "minor")
    match = re.fullmatch(r"([A-Ga-g])([#b♯♭]?)\s*(.*)", value)
    if not match:
        raise ValueError(f"Cannot parse key {text!r}")
    letter, accidental, rest = match.groups()
    tonic = PITCH_NAMES.index(letter.upper())
    if accidental in ("#", "♯"):
        tonic += 1
    elif accidental in ("b", "♭"):
        tonic -= 1
    tonic %= 12
    rest = rest.strip()
    if rest == "m" or rest.lower() in ("min", "minor", "-"):
        mode = "minor"
    elif rest in ("", "M") or rest.lower() in ("maj", "major"):
        mode = "major"
    else:
        raise ValueError(f"Cannot parse key mode in {text!r}")
    return Key(tonic, mode)


def camelot_parts(key: Key) -> tuple[int, str]:
    code = key.camelot
    return int(code[:-1]), code[-1]


def camelot_distance(a: Key, b: Key) -> int:
    """0 = same key; 1 = adjacent (±1 on the wheel or relative major/minor); higher = riskier."""
    na, la = camelot_parts(a)
    nb, lb = camelot_parts(b)
    diff = abs(na - nb) % 12
    return min(diff, 12 - diff) + (0 if la == lb else 1)


def harmonic_relation(a: Key, b: Key) -> str:
    distance = camelot_distance(a, b)
    if distance == 0:
        return "same key"
    na, la = camelot_parts(a)
    nb, lb = camelot_parts(b)
    if na == nb:
        return "relative major/minor"
    if distance == 1:
        return "adjacent (fifth)"
    if distance == 2 and la == lb:
        return "two steps (energy shift)"
    return "clash"


def _profile_scores(chroma: np.ndarray, major: np.ndarray, minor: np.ndarray) -> np.ndarray:
    """Return 24 correlations: index 0-11 major tonics, 12-23 minor tonics."""
    chroma = np.asarray(chroma, dtype=float)
    scores = np.zeros(24)
    with np.errstate(invalid="ignore", divide="ignore"):
        for tonic in range(12):
            scores[tonic] = np.corrcoef(chroma, np.roll(major, tonic))[0, 1]
            scores[12 + tonic] = np.corrcoef(chroma, np.roll(minor, tonic))[0, 1]
    return np.nan_to_num(scores)


def estimate_key_from_chroma(chroma: np.ndarray) -> tuple[Key, float, np.ndarray]:
    """Return (key, confidence 0-1, 24 scores) from a 12-bin mean chroma vector."""
    chroma = np.asarray(chroma, dtype=float)
    if chroma.shape != (12,) or not np.any(chroma > 0):
        return Key(0, "major"), 0.0, np.zeros(24)
    scores = 0.5 * _profile_scores(chroma, _KK_MAJOR, _KK_MINOR) + 0.5 * _profile_scores(
        chroma, _TEMPERLEY_MAJOR, _TEMPERLEY_MINOR
    )
    order = np.argsort(scores)[::-1]
    best = int(order[0])
    key = Key(best % 12, "major" if best < 12 else "minor")
    # Relative major/minor share pitch content, so measure margin against the best non-relative rival.
    relative = (key.tonic + 9) % 12 + 12 if key.mode == "major" else (key.tonic + 3) % 12
    rival = next(int(i) for i in order[1:] if int(i) != relative)
    margin = float(scores[best] - scores[rival])
    confidence = float(np.clip(margin / 0.25, 0.0, 1.0) * np.clip(scores[best], 0.0, 1.0))
    return key, confidence, scores


def chroma_similarity(a: np.ndarray, b: np.ndarray, shift: int = 0) -> float:
    """Cosine similarity between two 12-bin chroma vectors after shifting ``a`` up by ``shift`` semitones."""
    va = np.roll(np.asarray(a, dtype=float), shift)
    vb = np.asarray(b, dtype=float)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(va @ vb / denom) if denom > 0 else 0.0
