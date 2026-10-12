"""Mashability / mixability scoring between tracks (AutoMashUpper-style: tempo fit + key fit + chroma fit)."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from glass_harbor.keys import Key, camelot_distance, chroma_similarity, estimate_key_from_chroma, harmonic_relation

TEMPO_RATIOS = (1.0, 2.0, 0.5)
MAX_SHIFT = 3


@dataclass
class Fit:
    a: str
    b: str
    target_bpm: float
    tempo_ratio: float  # target beats per source beat for track a
    stretch_pct: float  # how much a must be stretched to sit on b's tempo (signed)
    semitones: int  # pitch shift applied to a
    key_a: str
    key_b: str
    relation: str
    camelot_distance: int
    chroma_similarity: float
    score: float

    def to_dict(self) -> dict:
        return asdict(self)


def tempo_options(bpm_a: float, bpm_b: float) -> list[tuple[float, float]]:
    """(tempo_ratio, stretch_pct) for playing a at b's tempo, best first."""
    options = []
    for ratio in TEMPO_RATIOS:
        effective = bpm_a * ratio
        stretch = (bpm_b / effective - 1.0) * 100.0
        options.append((ratio, stretch))
    return sorted(options, key=lambda item: abs(item[1]))


def tempo_score(stretch_pct: float) -> float:
    magnitude = abs(stretch_pct)
    if magnitude <= 3:
        return 1.0
    if magnitude <= 8:
        return 1.0 - (magnitude - 3) * 0.08
    if magnitude <= 16:
        return 0.6 - (magnitude - 8) * 0.06
    return 0.0


PARALLEL_SCORE = 0.6  # same home note, other mode (E major over E minor): a mood change DJs mix on purpose


def key_score(distance: int, similarity: float, semitones: int, confidence: float, *, parallel: bool = False) -> float:
    by_wheel = {0: 1.0, 1: 0.85, 2: 0.45}.get(distance, 0.1)
    if parallel:
        by_wheel = max(by_wheel, PARALLEL_SCORE)
    blended = (0.5 + 0.2 * confidence) * by_wheel + (0.5 - 0.2 * confidence) * max(0.0, similarity)
    # Every semitone costs a little; past two, a shifted voice starts to sound unnatural, so it costs a lot more.
    return blended - 0.06 * abs(semitones) - 0.15 * max(0, abs(semitones) - 2)


def _key(analysis: dict) -> Key:
    return Key(int(analysis["key"]["tonic"]), analysis["key"]["mode"])


def _chroma(analysis: dict, stem: str | None) -> list[float]:
    if stem and stem in analysis.get("stems", {}) and "chroma" in analysis["stems"][stem]:
        return analysis["stems"][stem]["chroma"]
    return analysis["chroma"]


def tonality(analysis: dict, stem: str | None) -> float:
    """0-1: how clearly pitched a stem is. Rap vocals score low, sung hooks high; key fit matters less when low."""
    chroma = _chroma(analysis, stem)
    return estimate_key_from_chroma(chroma)[1] if any(chroma) else 0.0


def score_pair(a_id: str, a: dict, b_id: str, b: dict, *, a_stem: str | None = "vocals",
               b_stem: str | None = "instrumental", max_shift: int = MAX_SHIFT) -> list[Fit]:
    """All plausible ways to lay track a over track b at b's tempo, best first."""
    ratio, stretch = tempo_options(a["bpm"], b["bpm"])[0]
    t_score = tempo_score(stretch)
    key_a, key_b = _key(a), _key(b)
    confidence = min(float(a["key"].get("confidence", 0.5)), float(b["key"].get("confidence", 0.5)))
    chroma_a, chroma_b = _chroma(a, a_stem), _chroma(b, b_stem)
    key_weight = 0.3 + 0.35 * tonality(a, a_stem)
    fits = []
    for shift in range(-max_shift, max_shift + 1):
        shifted = key_a.shifted(shift)
        distance = camelot_distance(shifted, key_b)
        similarity = chroma_similarity(chroma_a, chroma_b, shift)
        k_score = key_score(distance, similarity, shift, confidence,
                            parallel=shifted.tonic == key_b.tonic and shifted.mode != key_b.mode)
        fits.append(Fit(
            a=a_id,
            b=b_id,
            target_bpm=round(float(b["bpm"]), 2),
            tempo_ratio=ratio,
            stretch_pct=round(stretch, 2),
            semitones=shift,
            key_a=f"{shifted.name} ({shifted.camelot})",
            key_b=f"{key_b.name} ({key_b.camelot})",
            relation=harmonic_relation(shifted, key_b),
            camelot_distance=distance,
            chroma_similarity=round(similarity, 3),
            score=round(max(0.0, key_weight * k_score + (1.0 - key_weight) * t_score), 3),
        ))
    return sorted(fits, key=lambda fit: -fit.score)


def transition_fit(a: dict, b: dict) -> dict:
    """How easy a DJ blend from a into b is, without pitch shifting."""
    ratio, stretch = tempo_options(b["bpm"], a["bpm"])[0]
    key_a, key_b = _key(a), _key(b)
    distance = camelot_distance(key_a, key_b)
    return {
        "tempo_ratio": ratio,
        "stretch_pct_for_b": round(stretch, 2),
        "relation": harmonic_relation(key_a, key_b),
        "camelot": f"{key_a.camelot} -> {key_b.camelot}",
        "camelot_distance": distance,
        "score": round(0.5 * {0: 1.0, 1: 0.9, 2: 0.6}.get(distance, 0.25) + 0.5 * tempo_score(stretch), 3),
    }
