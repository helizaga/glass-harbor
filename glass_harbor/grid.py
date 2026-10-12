"""Beat grids: turn tracker output into a bar-addressable grid that covers the whole track.

Bars are 1-indexed. Bar 1 is the first downbeat at or after time 0 on the (extrapolated) grid, which is how a DAW
or DJ deck numbers bars once the grid is set. Beats before bar 1 are addressable as negative beat offsets.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

STEADY_RESIDUAL_RATIO = 0.035  # rms residual / period below which a track is treated as fixed tempo


@dataclass
class Grid:
    beats: list[float]  # beat times in seconds covering [0, duration]
    beats_per_bar: int
    first_downbeat: int  # index into beats of bar 1
    mode: str  # "fixed" | "variable"
    bpm: float
    duration: float
    residual_ms: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def period(self) -> float:
        return 60.0 / self.bpm

    @property
    def bar_count(self) -> int:
        return max(0, (len(self.beats) - 1 - self.first_downbeat) // self.beats_per_bar)

    def bar_start_index(self, bar: int) -> int:
        return self.first_downbeat + (bar - 1) * self.beats_per_bar

    def beat_time(self, index: float) -> float:
        """Time of (possibly fractional or out-of-range) beat index, extrapolating at the edges."""
        beats = self.beats
        if not beats:
            return index * self.period
        if len(beats) == 1:
            return beats[0] + index * self.period
        if index < 0:
            local = beats[1] - beats[0]
            return beats[0] + index * local
        if index > len(beats) - 1:
            local = beats[-1] - beats[-2]
            return beats[-1] + (index - (len(beats) - 1)) * local
        lower = int(np.floor(index))
        upper = min(lower + 1, len(beats) - 1)
        frac = index - lower
        return beats[lower] + frac * (beats[upper] - beats[lower])

    def bar_time(self, bar: float) -> float:
        return self.beat_time(self.first_downbeat + (bar - 1) * self.beats_per_bar)

    def bar_at_time(self, seconds: float) -> float:
        """Fractional bar number at a given time (inverse of bar_time)."""
        beats = np.asarray(self.beats)
        idx = float(np.interp(seconds, beats, np.arange(len(beats)))) if len(beats) > 1 else seconds / self.period
        return 1.0 + (idx - self.first_downbeat) / self.beats_per_bar

    def local_bpm(self, start_index: int, count: int) -> float:
        t0 = self.beat_time(start_index)
        t1 = self.beat_time(start_index + count)
        return 60.0 * count / (t1 - t0) if t1 > t0 else self.bpm

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "bpm": round(self.bpm, 3),
            "beats_per_bar": self.beats_per_bar,
            "first_downbeat": self.first_downbeat,
            "bar_count": self.bar_count,
            "residual_ms": round(self.residual_ms, 2),
            "duration": round(self.duration, 4),
            "notes": self.notes,
            "beats": [round(b, 5) for b in self.beats],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Grid":
        return cls(
            beats=list(data["beats"]),
            beats_per_bar=int(data["beats_per_bar"]),
            first_downbeat=int(data["first_downbeat"]),
            mode=data["mode"],
            bpm=float(data["bpm"]),
            duration=float(data["duration"]),
            residual_ms=float(data.get("residual_ms", 0.0)),
            notes=list(data.get("notes", [])),
        )


def _robust_period(beats: np.ndarray) -> float:
    intervals = np.diff(beats)
    intervals = intervals[intervals > 0]
    if intervals.size == 0:
        return 0.5
    median = float(np.median(intervals))
    # Ignore missed/extra beats when estimating the period.
    usable = intervals[(intervals > 0.75 * median) & (intervals < 1.25 * median)]
    return float(np.median(usable)) if usable.size else median


def normalize_metrical_level(beats: np.ndarray) -> tuple[np.ndarray, bool]:
    """Trackers can flip between metrical levels inside one song (e.g. 126 bpm in the intro, 63 bpm in the verse).
    If a real share of intervals sits at the faster level, subdivide the slow stretches back down to it."""
    intervals = np.diff(beats)
    if intervals.size < 16:
        return beats, False
    fast = float(np.percentile(intervals, 20))
    at_fast = np.abs(intervals / fast - 1.0) < 0.12
    if at_fast.mean() < 0.15:
        return beats, False
    fast = float(np.median(intervals[at_fast]))
    out = [float(beats[0])]
    changed = False
    for start, end in zip(beats[:-1], beats[1:]):
        count = int(round((end - start) / fast))
        if count >= 2 and abs((end - start) / count / fast - 1.0) < 0.12:
            out.extend(start + (end - start) * np.arange(1, count) / count)
            changed = True
        out.append(float(end))
    return np.asarray(out), changed


def _beat_indices(beats: np.ndarray, period: float) -> np.ndarray:
    """Integer beat numbers, assigned interval by interval so a slightly wrong period cannot accumulate
    (tracker output is frame-quantized, e.g. beat_this reports on a 20 ms grid)."""
    steps = np.maximum(1, np.round(np.diff(beats) / period))
    return np.concatenate([[0.0], np.cumsum(steps)])


def _fit_line(beats: np.ndarray, period: float) -> tuple[float, float, np.ndarray, np.ndarray]:
    """Least-squares fit t = t0 + k * period over integer beat indices; returns (t0, period, indices, residuals)."""
    indices = _beat_indices(beats, period)
    keep = np.ones(beats.size, dtype=bool)
    t0, slope = beats[0], period
    for _ in range(4):
        A = np.stack([np.ones(keep.sum()), indices[keep]], axis=1)
        t0, slope = np.linalg.lstsq(A, beats[keep], rcond=None)[0]
        residuals = beats - (t0 + slope * indices)
        new_keep = np.abs(residuals) < 0.12 * slope
        if new_keep.sum() < max(8, 0.5 * beats.size) or np.array_equal(new_keep, keep):
            break
        keep = new_keep
    residuals = beats - (t0 + slope * indices)
    return float(t0), float(slope), indices, residuals[keep]


def _fast_pulse(beats: np.ndarray) -> float | None:
    """The fastest steady pulse among the tracker's intervals (the bar-level detail the tracker sometimes drops)."""
    intervals = np.diff(beats)
    if intervals.size < 16:
        return None
    fast = float(np.percentile(intervals, 20))
    close = intervals[np.abs(intervals / fast - 1.0) < 0.12]
    return float(np.median(close)) if close.size >= 8 else None


def _fit_majority(beats: np.ndarray, *, window: int = 32,
                  period_hint: float | None = None) -> tuple[float, float, float] | None:
    """Constant-tempo fit that trusts the steady majority of the track: electronic records are one fixed tempo, but
    trackers drift through breakdowns and beatless intros, and those stretches pull a plain fit off. The period comes
    from the median tempo of 32-beat windows; beats are numbered against that global grid (not one by one), so a
    drifting stretch shows up as outliers instead of shifting everything after it. Returns (t0, period, share of
    beats on the grid) or None when there are too few beats."""
    if beats.size < (16 if period_hint else 2 * window):
        return None
    if period_hint:
        period = period_hint
    else:
        spans = (beats[window:] - beats[:-window]) / window
        period = float(np.median(spans))
    # Over a few hundred beats a 0.05% period error drifts a whole beat, so refine the period to the one where the
    # most beats share a phase (a comb search within +-1.5% of the windowed estimate).
    # A hint from raw intervals is coarser (frame-quantized, skewed by syncopation): search it more widely.
    spread = 0.06 if period_hint else 0.015
    candidates = period * (1 + np.linspace(-spread, spread, 3001))
    batch = max(1, 2_000_000 // beats.size)  # bounded memory on hour-long recordings
    coherence = np.concatenate([np.abs(np.exp(2j * np.pi * beats[None, :] / candidates[i:i + batch, None]).mean(axis=1))
                                for i in range(0, candidates.size, batch)])
    period = float(candidates[int(np.argmax(coherence))])
    phases = np.angle(np.mean(np.exp(2j * np.pi * beats / period)))
    t0 = float(phases / (2 * np.pi) * period)
    on_grid = np.ones(beats.size, dtype=bool)
    for _ in range(4):
        k = np.round((beats - t0) / period)
        residuals = beats - (t0 + k * period)
        on_grid = np.abs(residuals) < 0.06 * period
        if on_grid.sum() < 8:
            return None
        t0, period = np.linalg.lstsq(np.stack([np.ones(on_grid.sum()), k[on_grid]], axis=1), beats[on_grid],
                                     rcond=None)[0]
    k = np.round((beats - t0) / period)
    share = float(np.mean(np.abs(beats - (t0 + k * period)) < 0.06 * period))
    return float(t0), float(period), share


START_TOLERANCE_S = 0.03
MAJORITY_SHARE = 0.65  # share of tracked beats on one constant grid to call the track fixed tempo (a real tempo change scores ~0.5; half-time sections and beatless breaks pull steady tracks down to ~0.8)


def _meter(beats: np.ndarray, downbeats: np.ndarray) -> int:
    if downbeats.size < 3 or beats.size < 8:
        return 4
    counts = []
    for start, end in zip(downbeats[:-1], downbeats[1:]):
        counts.append(int(np.sum((beats >= start - 0.05) & (beats < end - 0.05))))
    counts = [c for c in counts if 2 <= c <= 7]
    if not counts:
        return 4
    value = int(np.bincount(counts).argmax())
    return value if value in (3, 4) else 4


def _downbeat_phase(beat_times: np.ndarray, downbeats: np.ndarray, beats_per_bar: int) -> int:
    if downbeats.size == 0:
        return 0
    votes = np.zeros(beats_per_bar)
    for d in downbeats:
        idx = int(np.argmin(np.abs(beat_times - d)))
        if abs(beat_times[idx] - d) < 0.1:
            votes[idx % beats_per_bar] += 1
    return int(votes.argmax())


def hinted_fit(beats: np.ndarray | list[float]) -> tuple[float, float, float] | None:
    """Constant grid at the fastest steady pulse of raw tracker beats: (t0, period, share of beats on it)."""
    raw = np.asarray(sorted(beats), dtype=float)
    hint = _fast_pulse(raw)
    return _fit_majority(raw, period_hint=hint) if hint else None


def build_grid(
    beats: np.ndarray | list[float],
    downbeats: np.ndarray | list[float],
    duration: float,
    *,
    force_mode: str | None = None,
    fit: tuple[float, float] | None = None,
) -> Grid:
    """``fit`` = (t0, period) forces a fixed grid on that line (for a fit confirmed against the audio)."""
    beats = np.asarray(sorted(beats), dtype=float)
    downbeats = np.asarray(sorted(downbeats), dtype=float)
    notes: list[str] = []
    if beats.size < 4:
        raise ValueError("Too few beats detected to build a grid (need at least 4).")

    raw = beats.copy()
    beats, filled = normalize_metrical_level(beats)
    if filled:
        notes.append("beat tracker switched metrical level; normalized to the faster pulse")
    beats_per_bar = _meter(beats, downbeats)
    if beats_per_bar != 4:
        notes.append(f"detected {beats_per_bar}/4 meter")

    period = _robust_period(beats)
    t0, period, _, residuals = _fit_line(beats, period)
    residual_rms = float(np.sqrt(np.mean(residuals**2))) if residuals.size else 0.0
    steady = residual_rms / period < STEADY_RESIDUAL_RATIO
    if fit is not None:
        t0, period = fit
        steady = True
        residual_rms = 0.0
        notes.append("fixed tempo: the drum hits sit on one constant grid (the beat tracker drifted)")
    if not steady and force_mode != "variable":
        majority = _fit_majority(beats)
        if majority is None or majority[2] < MAJORITY_SHARE:
            # Trackers can lock onto a half-time pulse or syncopated hits through a drop, and filling the gaps in
            # then puts beats in the wrong places. Fit the raw beats to the fastest steady pulse instead: half-time
            # detections still land on its grid lines, and syncopated ones only count as misses.
            hint = _fast_pulse(raw)
            alternative = _fit_majority(raw, period_hint=hint) if hint else None
            if alternative is not None and (majority is None or alternative[2] > majority[2]):
                majority = alternative
        if majority is not None and majority[2] >= MAJORITY_SHARE:
            t0, period, share = majority
            k = np.round((beats - t0) / period)
            off = beats - (t0 + k * period)
            residual_rms = float(np.sqrt(np.mean(off[np.abs(off) < 0.06 * period] ** 2)))
            steady = True
            notes.append(f"fixed tempo: {share:.0%} of tracked beats sit on one grid (the tracker drifted elsewhere)")
    mode = force_mode or ("fixed" if steady else "variable")

    if mode == "fixed":
        # A track that starts on the beat fits its first beat a few ms before 0 s; keep it (at 0) so bar 1 stays bar 1.
        first_k = int(np.ceil((-START_TOLERANCE_S - t0) / period - 1e-9))
        last_k = int(np.floor((duration - t0) / period + 1e-9))
        grid_beats = np.maximum(t0 + period * np.arange(first_k, last_k + 1), 0.0)
        bpm = 60.0 / period
    else:
        notes.append("tempo drifts; warping follows detected beats")
        grid_beats = beats.copy()
        if beats.size >= 9:
            from scipy.signal import savgol_filter

            # Remove frame-quantization jitter while following real drift.
            grid_beats = savgol_filter(beats, 9, 2)
        head_period = float(np.median(np.diff(beats[: min(9, beats.size)])))
        tail_period = float(np.median(np.diff(beats[-min(9, beats.size):])))
        head = beats[0] - head_period * np.arange(int(beats[0] / head_period), 0, -1)
        tail = beats[-1] + tail_period * np.arange(1, int(max(0.0, duration - beats[-1]) / tail_period) + 1)
        grid_beats = np.concatenate([head, grid_beats, tail])
        grid_beats = grid_beats[(grid_beats >= -1e-6) & (grid_beats <= duration + 1e-6)]
        bpm = 60.0 / _robust_period(beats)

    phase = _downbeat_phase(grid_beats, downbeats, beats_per_bar)
    first_downbeat = phase
    return Grid(
        beats=[float(b) for b in grid_beats],
        beats_per_bar=beats_per_bar,
        first_downbeat=first_downbeat,
        mode=mode,
        bpm=float(bpm),
        duration=float(duration),
        residual_ms=residual_rms * 1000.0,
        notes=notes,
    )


def shift_downbeat(grid: Grid, beats: int) -> Grid:
    """Return a copy with bar 1 moved by ``beats`` (fixes trackers that land on the wrong beat of the bar)."""
    new_first = (grid.first_downbeat + beats) % grid.beats_per_bar
    return Grid(
        beats=grid.beats,
        beats_per_bar=grid.beats_per_bar,
        first_downbeat=new_first,
        mode=grid.mode,
        bpm=grid.bpm,
        duration=grid.duration,
        residual_ms=grid.residual_ms,
        notes=grid.notes + [f"downbeat shifted by {beats} beat(s)"],
    )
