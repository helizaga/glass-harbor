"""Track analysis: beat grid, key, loudness, per-bar energy, sections, and vocal phrases."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import tempfile
import warnings
from pathlib import Path
from typing import Any

import numpy as np

from glass_harbor import audio as A
from glass_harbor.grid import Grid, build_grid
from glass_harbor.keys import estimate_key_from_chroma

ANALYSIS_SR = 22050
HOP = 512


def beat_backends() -> list[str]:
    backends = []
    if importlib.util.find_spec("beat_this") and importlib.util.find_spec("torch"):
        backends.append("beat_this")
    backends.append("librosa")
    return backends


def torch_device() -> str:
    try:
        import torch
    except ImportError:
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def track_beats_beat_this(audio: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from beat_this.inference import Audio2Beats

        tracker = Audio2Beats(checkpoint_path="final0", device=torch_device(), dbn=False)
        beats, downbeats = tracker(A.mono(audio), A.SR)
    return np.asarray(beats, dtype=float), np.asarray(downbeats, dtype=float)


def _low_band_onsets(y: np.ndarray, hop: int) -> np.ndarray:
    import librosa

    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop))
    freqs = librosa.fft_frequencies(sr=ANALYSIS_SR, n_fft=2048)
    return librosa.onset.onset_strength(S=librosa.amplitude_to_db(S[freqs < 150]), sr=ANALYSIS_SR, hop_length=hop)


def track_beats_librosa(audio: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Fallback tracker: librosa tempo/beat tracking, re-phased onto the kick and corrected for onset lag."""
    import librosa

    y = librosa.resample(A.mono(audio), orig_sr=A.SR, target_sr=ANALYSIS_SR)
    _, beat_frames = librosa.beat.beat_track(y=y, sr=ANALYSIS_SR, hop_length=HOP, trim=False)
    beats = librosa.frames_to_time(beat_frames, sr=ANALYSIS_SR, hop_length=HOP)
    if beats.size < 8:
        return beats, beats[:1]
    fine_hop = 64
    low = _low_band_onsets(y, fine_hop)
    frame = fine_hop / ANALYSIS_SR
    period = float(np.median(np.diff(beats)))

    def kick_energy(times: np.ndarray) -> float:
        idx = np.clip(np.round(times / frame).astype(int), 0, low.size - 1)
        return float(low[idx].mean())

    # Trackers often lock onto off-beat hats; keep whichever phase the kick agrees with.
    if kick_energy(beats + period / 2) > 1.2 * kick_energy(beats):
        beats = beats + period / 2
    # Snap the grid to where low-band onsets actually peak (removes frame lag).
    radius = int(0.06 / frame)
    offsets = []
    for t in beats:
        c = int(round(t / frame))
        lo, hi = max(0, c - radius), min(low.size, c + radius + 1)
        if hi - lo > 2:
            offsets.append((lo + int(np.argmax(low[lo:hi]))) * frame - t)
    if offsets:
        beats = beats + float(np.median(offsets))
    beats = beats[beats >= 0]
    # Downbeat guess: the beat position (mod 4) with the most low-end energy right after the beat.
    band = librosa.stft(y, n_fft=1024, hop_length=fine_hop)
    freqs = librosa.fft_frequencies(sr=ANALYSIS_SR, n_fft=1024)
    power = (np.abs(band[freqs < 120]) ** 2).sum(axis=0)
    width = max(1, int(0.05 / frame))
    idx = np.clip(np.round(beats / frame).astype(int), 0, power.size - width)
    per_beat = np.array([power[i: i + width].sum() for i in idx])
    phase = int(np.argmax([per_beat[p::4].mean() for p in range(4)]))
    return beats, beats[phase::4]


def detect_beats(audio: np.ndarray, backend: str = "auto") -> tuple[np.ndarray, np.ndarray, str]:
    if backend == "auto":
        backend = beat_backends()[0]
    if backend == "beat_this":
        beats, downbeats = track_beats_beat_this(audio)
    elif backend == "librosa":
        beats, downbeats = track_beats_librosa(audio)
    else:
        raise ValueError(f"Unknown beat backend {backend!r}")
    return beats, downbeats, backend


def mean_chroma(audio: np.ndarray) -> np.ndarray:
    import librosa

    y = librosa.resample(A.mono(audio), orig_sr=A.SR, target_sr=ANALYSIS_SR)
    if not np.any(np.abs(y) > 1e-4):
        return np.zeros(12)
    harmonic = librosa.effects.harmonic(y, margin=2.0)
    chroma = librosa.feature.chroma_cqt(y=harmonic, sr=ANALYSIS_SR, hop_length=HOP * 2)
    energy = chroma.sum(axis=0)
    weights = energy / energy.sum() if energy.sum() > 0 else None
    vector = np.average(chroma, axis=1, weights=weights)
    total = vector.sum()
    return vector / total if total > 0 else vector


def _bar_edges(grid: Grid) -> np.ndarray:
    return np.array([grid.bar_time(bar) for bar in range(1, grid.bar_count + 2)])


def per_bar_db(audio: np.ndarray, grid: Grid) -> list[float]:
    signal = A.mono(audio)
    edges = _bar_edges(grid)
    levels = []
    for start, end in zip(edges[:-1], edges[1:]):
        chunk = signal[int(start * A.SR): int(end * A.SR)]
        rms = float(np.sqrt(np.mean(chunk**2))) if chunk.size else 0.0
        levels.append(round(A.gain_to_db(rms), 2))
    return levels


def low_band_db(audio: np.ndarray, grid: Grid, cutoff: float = 150.0) -> list[float]:
    """Per-bar level of kick + bass (below ``cutoff`` Hz)."""
    from scipy.signal import butter, sosfiltfilt

    sos = butter(4, cutoff, btype="lowpass", fs=A.SR, output="sos")
    return per_bar_db(sosfiltfilt(sos, A.mono(audio)).astype(np.float32)[:, None], grid)


def detect_drops(low_db: list[float], *, jump_db: float = 6.0, min_gap: int = 8) -> list[int]:
    """Bars where kick + bass come back hard after a lighter stretch (the classic EDM drop)."""
    levels = np.array(low_db)
    if levels.size < 8:
        return []
    median = float(np.median(levels))
    drops: list[int] = []
    for i in range(4, levels.size):
        before = float(levels[i - 4:i].mean())
        if levels[i] - before >= jump_db and levels[i] >= median - 3 and levels[i - 1] < levels[i] - 3:
            if not drops or i + 1 - drops[-1] >= min_gap:
                drops.append(i + 1)
    return drops


def _checkerboard(size: int) -> np.ndarray:
    half = size // 2
    sign = np.sign(np.arange(-half, half) + 0.5)
    kernel = np.outer(sign, sign)
    taper = np.exp(-0.5 * (np.linspace(-1.5, 1.5, size) ** 2))
    return kernel * np.outer(taper, taper)


def detect_sections(audio: np.ndarray, grid: Grid, bar_db: list[float]) -> list[dict[str, Any]]:
    """Phrase-level sections from bar-synchronous timbre/harmony novelty, snapped to 4-bar phrases where possible."""
    import librosa

    bars = grid.bar_count
    if bars < 8:
        return [{"start_bar": 1, "bars": max(bars, 1), "label": "A", "energy": "mid"}]
    y = librosa.resample(A.mono(audio), orig_sr=A.SR, target_sr=ANALYSIS_SR)
    chroma = librosa.feature.chroma_cqt(y=y, sr=ANALYSIS_SR, hop_length=HOP)
    mfcc = librosa.feature.mfcc(y=y, sr=ANALYSIS_SR, hop_length=HOP, n_mfcc=13)
    edges = _bar_edges(grid)
    frames = librosa.time_to_frames(edges, sr=ANALYSIS_SR, hop_length=HOP)
    frames = np.clip(frames, 0, chroma.shape[1] - 1)
    feats = []
    for f0, f1 in zip(frames[:-1], frames[1:]):
        f1 = max(f1, f0 + 1)
        feats.append(np.concatenate([chroma[:, f0:f1].mean(axis=1), mfcc[:, f0:f1].mean(axis=1)]))
    X = np.array(feats)
    X = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-9)
    X = np.concatenate([X, (np.array(bar_db)[:, None] - np.mean(bar_db)) / (np.std(bar_db) + 1e-9) * 2.0], axis=1)
    norms = np.linalg.norm(X, axis=1, keepdims=True) + 1e-9
    ssm = (X / norms) @ (X / norms).T

    kernel = _checkerboard(8)
    half = 4
    padded = np.pad(ssm, half, mode="edge")
    novelty = np.zeros(bars + 1)
    for b in range(1, bars):
        window = padded[b: b + 2 * half, b: b + 2 * half]
        novelty[b] = max(0.0, float(np.sum(window * kernel)))
    threshold = novelty.mean() + 0.5 * novelty.std()
    candidates = sorted(range(2, bars - 1), key=lambda b: -novelty[b])
    boundaries: list[int] = []
    for b in candidates:
        if novelty[b] < threshold:
            break
        # Prefer the nearest 4-bar phrase line when it is nearly as novel.
        phrase = 4 * round(b / 4)
        if phrase != b and 1 <= phrase < bars and novelty[phrase] >= 0.7 * novelty[b]:
            b = phrase
        if all(abs(b - other) >= 4 for other in boundaries):
            boundaries.append(b)
    starts = [0] + sorted(boundaries)
    ends = starts[1:] + [bars]

    levels = np.array(bar_db)
    lo, hi = np.percentile(levels, 33), np.percentile(levels, 66)
    sections: list[dict[str, Any]] = []
    centroids: list[np.ndarray] = []
    for s, e in zip(starts, ends):
        centroid = X[s:e].mean(axis=0)
        label = None
        for i, other in enumerate(centroids):
            sim = float(centroid @ other / (np.linalg.norm(centroid) * np.linalg.norm(other) + 1e-9))
            if sim > 0.9:
                label = chr(ord("A") + i)
                break
        if label is None:
            centroids.append(centroid)
            label = chr(ord("A") + min(len(centroids) - 1, 25))
        mean_db = float(levels[s:e].mean())
        energy = "high" if mean_db >= hi else "low" if mean_db <= lo else "mid"
        sections.append({"start_bar": s + 1, "bars": e - s, "label": label, "energy": energy,
                         "mean_db": round(mean_db, 1)})
    return sections


def detect_sections_allin1(path: Path, grid: Grid, bar_db: list[float]) -> list[dict[str, Any]]:
    """Functional sections (intro/verse/chorus/inst/bridge/outro) from allin1, snapped to our bar grid."""
    with tempfile.TemporaryDirectory(prefix="gh-allin1-") as tmp, warnings.catch_warnings(), \
            contextlib.redirect_stdout(io.StringIO()):
        warnings.simplefilter("ignore")
        import allin1_infer

        result = allin1_infer.analyze(str(path), device="cpu", demix_dir=f"{tmp}/demix", spec_dir=f"{tmp}/spec",
                                      multiprocess=False)
    levels = np.array(bar_db)
    lo, hi = (np.percentile(levels, 33), np.percentile(levels, 66)) if levels.size else (0, 0)
    sections = []
    for seg in result.segments:
        if seg.label in ("start", "end"):
            continue
        first = max(1, int(round(grid.bar_at_time(seg.start))))
        last = min(grid.bar_count + 1, int(round(grid.bar_at_time(seg.end))))
        if last <= first:
            continue
        if sections and sections[-1]["start_bar"] == first:
            sections.pop()
        mean_db = float(levels[first - 1: last - 1].mean()) if levels.size else 0.0
        sections.append({"start_bar": first, "bars": last - first, "label": seg.label,
                         "energy": "high" if mean_db >= hi else "low" if mean_db <= lo else "mid",
                         "mean_db": round(mean_db, 1)})
    return sections


def vocal_phrases(bar_db: list[float], *, min_bars: int = 2) -> list[dict[str, int]]:
    """Group bars where the vocal stem is clearly present into phrases (1-bar gaps are bridged)."""
    levels = np.array(bar_db)
    if levels.size == 0:
        return []
    threshold = max(-42.0, float(levels.max()) - 22.0)
    active = levels > threshold
    phrases = []
    start = None
    gap = 0
    for i, on in enumerate(list(active) + [False, False]):
        if on:
            if start is None:
                start = i
            gap = 0
        elif start is not None:
            gap += 1
            if gap > 1:
                end = i - gap + 1
                if end - start >= min_bars:
                    phrases.append({"start_bar": start + 1, "bars": end - start})
                start, gap = None, 0
    return phrases


def analyze_track(
    audio: np.ndarray,
    *,
    beat_backend: str = "auto",
    stems: dict[str, np.ndarray] | None = None,
    key_backend: str = "auto",
    sections_backend: str = "novelty",
    source_path: Path | None = None,
) -> dict[str, Any]:
    duration = audio.shape[0] / A.SR
    beats, downbeats, backend = detect_beats(audio, beat_backend)
    grid = build_grid(beats, downbeats, duration)
    stems = stems or {}

    harmonic_source = stems.get("instrumental", audio)
    chroma = mean_chroma(harmonic_source)
    template_key, template_confidence, _ = estimate_key_from_chroma(chroma)
    key_info: dict[str, Any] = {**template_key.to_dict(), "confidence": round(template_confidence, 3),
                                "backend": "template"}
    if key_backend in ("auto", "skey"):
        from glass_harbor import key_model

        if key_model.available():
            key, probability, top = key_model.estimate_key(harmonic_source)
            key_info = {**key.to_dict(), "confidence": round(probability, 3), "backend": "skey",
                        "alternatives": top,
                        "template": {"name": template_key.name, "camelot": template_key.camelot,
                                     "confidence": round(template_confidence, 3)}}
        elif key_backend == "skey":
            raise RuntimeError("S-KEY needs torch, torchaudio, nnAudio, einops (pip install -e '.[ml]')")
    key_info["source"] = "instrumental stem" if "instrumental" in stems else "full mix"

    bar_db = per_bar_db(audio, grid)
    low_db = low_band_db(stems.get("instrumental", audio), grid)
    if sections_backend == "allin1":
        if source_path is None:
            raise ValueError("allin1 sections need the source file path")
        sections = detect_sections_allin1(source_path, grid, bar_db)
    else:
        sections = detect_sections(audio, grid, bar_db)
    result: dict[str, Any] = {
        "version": 1,
        "duration": round(duration, 4),
        "bpm": round(grid.bpm, 3),
        "beat_backend": backend,
        "key": key_info,
        "loudness_lufs": round(A.integrated_lufs(audio), 2),
        "chroma": [round(float(v), 5) for v in chroma],
        "grid": grid.to_dict(),
        "detected": {"beats": [round(float(b), 4) for b in beats], "downbeats": [round(float(d), 4) for d in downbeats]},
        "bar_db": bar_db,
        "sections": sections,
        "sections_backend": sections_backend,
        "low_db": low_db,
        "drops": detect_drops(low_db),
        "stems": {},
    }
    for name, stem_audio in stems.items():
        stem_db = per_bar_db(stem_audio, grid)
        entry: dict[str, Any] = {"bar_db": stem_db}
        if name in ("vocals", "instrumental"):
            entry["chroma"] = [round(float(v), 5) for v in mean_chroma(stem_audio)]
        if name == "vocals":
            entry["phrases"] = vocal_phrases(stem_db)
        result["stems"][name] = entry
    return result


def analyze_library_track(track_id: str, *, backend: str = "auto", log=print,
                          sections: str | None = None) -> dict[str, Any]:
    """Analyze a library track with all its stems and save it (lyric phrases and hooks are kept)."""
    from glass_harbor import library
    from glass_harbor.lyrics import load_lyrics, update_analysis

    audio = library.load_audio(track_id)
    stems = {name: library.load_audio(track_id, name) for name in library.available_stems(track_id)}
    if sections is None:  # keep whatever section backend the track was analyzed with last time
        previous = library.load_analysis(track_id) if library.analysis_path(track_id).exists() else {}
        sections = previous.get("sections_backend", "novelty")
    log(f"analyzing {track_id} ({', '.join(stems) or 'no stems'}; sections: {sections})")
    analysis = analyze_track(audio, beat_backend=backend, stems=stems, sections_backend=sections,
                             source_path=library.audio_path(track_id))
    library.save_analysis(track_id, analysis)
    lyrics = load_lyrics(track_id)
    if lyrics is not None:
        analysis = update_analysis(track_id, lyrics)
    return analysis
