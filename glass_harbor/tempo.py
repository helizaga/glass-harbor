"""Output tempo maps: constant tempo, step changes on bar lines (cuts/echo-outs), or linear ramps.

Beat 0 is bar 1 beat 1 of the output. Negative beats (pickups before bar 1) use the first tempo.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class TempoPoint:
    beat: float
    bpm: float
    ramp: bool  # True: tempo ramps linearly from the previous point to this one


class TempoMap:
    def __init__(self, points: list[TempoPoint]):
        if not points or points[0].beat != 0:
            raise ValueError("tempo map must start at bar 1")
        self.points = points
        # Cumulative seconds at each point.
        self._times = [0.0]
        for prev, point in zip(points, points[1:]):
            self._times.append(self._times[-1] + self._segment_seconds(prev, point, point.beat - prev.beat))

    @classmethod
    def from_plan(cls, plan: dict, beats_per_bar: int) -> "TempoMap":
        tempo = plan.get("tempo")
        if tempo is None:
            return cls([TempoPoint(0.0, float(plan["bpm"]), False)])
        points = [TempoPoint((float(p["bar"]) - 1) * beats_per_bar, float(p["bpm"]), bool(p.get("ramp", False)))
                  for p in tempo]
        return cls(points)

    @staticmethod
    def _segment_seconds(prev: TempoPoint, point: TempoPoint, beats: float) -> float:
        length = point.beat - prev.beat
        if not point.ramp or length <= 0 or point.bpm == prev.bpm:
            return 60.0 * beats / prev.bpm
        slope = (point.bpm - prev.bpm) / length
        return 60.0 / slope * math.log((prev.bpm + slope * beats) / prev.bpm)

    def bpm_at(self, beat: float) -> float:
        current = self.points[0]
        for point in self.points[1:]:
            if beat < point.beat:
                if point.ramp:
                    t = (beat - current.beat) / (point.beat - current.beat)
                    return current.bpm + t * (point.bpm - current.bpm)
                return current.bpm
            current = point
        return current.bpm

    def time_at(self, beat: float) -> float:
        if beat <= 0:
            return 60.0 * beat / self.points[0].bpm
        for i, point in enumerate(self.points[1:], start=1):
            if beat < point.beat:
                prev = self.points[i - 1]
                return self._times[i - 1] + self._segment_seconds(prev, point, beat - prev.beat)
        last = self.points[-1]
        return self._times[-1] + 60.0 * (beat - last.beat) / last.bpm

    def describe(self, beats_per_bar: int) -> str:
        parts = []
        for point in self.points:
            bar = point.beat / beats_per_bar + 1
            parts.append(f"bar {bar:g}: {'ramp to ' if point.ramp else ''}{point.bpm:g} bpm")
        return "; ".join(parts)


def validate_tempo(plan: dict) -> list[str]:
    """Return error messages for the plan's bpm/tempo fields."""
    errors = []
    has_bpm, has_tempo = "bpm" in plan, "tempo" in plan
    if has_bpm == has_tempo:
        return ["set exactly one of bpm (constant) or tempo (list of {bar, bpm, ramp?})"]
    if has_bpm:
        value = plan["bpm"]
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 50 <= value <= 220:
            errors.append("bpm must be a number between 50 and 220")
        return errors
    tempo = plan["tempo"]
    if not isinstance(tempo, list) or not tempo:
        return ["tempo must be a non-empty list of {bar, bpm, ramp?}"]
    last_bar = 0.0
    for i, point in enumerate(tempo):
        if not isinstance(point, dict):
            errors.append(f"tempo[{i}] must be an object")
            continue
        bar, bpm = point.get("bar"), point.get("bpm")
        if not isinstance(bar, (int, float)) or isinstance(bar, bool) or bar < 1:
            errors.append(f"tempo[{i}].bar must be >= 1")
            continue
        if not isinstance(bpm, (int, float)) or isinstance(bpm, bool) or not 50 <= bpm <= 220:
            errors.append(f"tempo[{i}].bpm must be between 50 and 220")
        if i == 0 and bar != 1:
            errors.append("tempo[0].bar must be 1")
        if i > 0 and bar <= last_bar:
            errors.append("tempo bars must be strictly ascending")
        if i == 0 and point.get("ramp"):
            errors.append("tempo[0] cannot ramp")
        last_bar = bar
    return errors
