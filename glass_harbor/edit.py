"""A short edit for sending to a phone: the same master, cut at bar lines to about two and a half minutes.

The full render stays the version QA and the listening pass judge; the short edit is cut from its phone master.
It removes, in this order and only while the edit is still over the target:

- the beat-only run-up before the first vocal (keeping RUN_UP_BARS), and the tail after the last vocal (keeping
  TAIL_BARS, faded out);
- whole sections from one drop to the next whose vocals only repeat clips heard elsewhere: the build before the
  removed drop then leads into the next one, so the join lands drop to drop. Never the first drop's section.

Cuts are whole bars (moved back by a vocal pickup into the next drop, so the pickup stays) and never split a vocal
clip. Without enough to remove there is no short edit.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from glass_harbor import audio as A

TARGET_S = 150.0
MIN_SAVING_S = 20.0  # a short edit only when it is meaningfully shorter
RUN_UP_BARS = 4
TAIL_BARS = 4
XFADE_S = 0.015


def plan_short_edit(plan: dict[str, Any], res: Any, *, target_s: float = TARGET_S) -> dict[str, Any] | None:
    """Bars to keep. Returns {"start_bar", "end_bar", "cuts": [(from, to)], "segments": [(bar, bar)], "duration_s",
    "full_s"} or None."""
    bpb = res.beats_per_bar
    bar = lambda beat: 1 + beat / bpb  # noqa: E731
    vocal = sorted((bar(c.out_start_beat), bar(c.out_end_beat), c) for c in res.clips if c.stem == "vocals")
    if not vocal or not res.clips:
        return None
    end_all = max(bar(c.out_end_beat) for c in res.clips)
    seconds = lambda a, b: res.tempo.time_at((b - 1) * bpb) - res.tempo.time_at((a - 1) * bpb)  # noqa: E731
    full_s = seconds(1, end_all)
    if full_s <= target_s + MIN_SAVING_S / 2:
        return None
    first, last = vocal[0][0], max(e for _, e, _ in vocal)
    start = max(1, 1 + 4 * math.floor((first - RUN_UP_BARS - 1) / 4))
    end = min(end_all, 1 + 4 * math.ceil((last - 1) / 4 - 1e-9) + TAIL_BARS)
    total = seconds(start, end)

    def repeats(clip: Any, kept: list[Any]) -> bool:
        if clip.source == "bed":
            return True  # the beat's own shouts are effects, not content
        key = (clip.source, clip.spec.get("from_bar"), clip.spec.get("stem"))
        return any((k.source, k.spec.get("from_bar"), k.spec.get("stem")) == key for k in kept)

    drops = sorted(float(c["at_bar"]) for c in plan["clips"] if c.get("generate") == "impact")
    candidates = []
    for d0, d1 in zip(drops[1:], drops[2:]):
        lead = max((d1 - s for s, _, _ in vocal if d1 - 1 <= s < d1), default=0.0)  # a pickup into the next drop
        a, b = d0 - lead, d1 - lead
        if not start < a < b < end or any(s < x < e - 1e-6 for s, e, _ in vocal for x in (a, b)):
            continue
        inside = [c for s, e, c in vocal if a <= s and e <= b]
        kept = [c for s, e, c in vocal if not (a <= s and e <= b)]
        if all(repeats(c, kept) for c in inside):
            candidates.append((a, b))
    cuts = []
    for a, b in sorted(candidates, key=lambda ab: ab[0] - ab[1]):  # biggest first
        if total <= target_s:
            break
        cuts.append((a, b))
        total -= seconds(a, b)
    if full_s - total < MIN_SAVING_S:
        return None
    cuts.sort()
    edges = [start] + [x for cut in cuts for x in cut] + [end]
    segments = list(zip(edges[::2], edges[1::2]))
    return {"start_bar": start, "end_bar": end, "cuts": cuts, "segments": segments, "duration_s": round(total, 2),
            "full_s": round(full_s, 2)}


def splice(audio: np.ndarray, edit: dict[str, Any], res: Any, offset_s: float) -> np.ndarray:
    """Join the kept bars with short equal-power crossfades, fade in a hair and fade out over the last TAIL_BARS."""
    bpb = res.beats_per_bar
    at = lambda b: int(round((res.tempo.time_at((b - 1) * bpb) + offset_s) * A.SR))  # noqa: E731
    pieces = [audio[max(0, at(a)):min(audio.shape[0], at(b))].astype(np.float32) for a, b in edit["segments"]]
    fade = int(XFADE_S * A.SR)
    out = pieces[0]
    for piece in pieces[1:]:
        n = min(fade, out.shape[0], piece.shape[0])
        if n:
            t = np.linspace(0.0, np.pi / 2, n)[:, None]
            out[-n:] = out[-n:] * np.cos(t) + piece[:n] * np.sin(t)
        out = np.concatenate([out, piece[n:]])
    n = min(fade, out.shape[0])
    out[:n] *= np.linspace(0.0, 1.0, n)[:, None]
    tail = min(out.shape[0], at(edit["end_bar"]) - at(edit["end_bar"] - TAIL_BARS))
    if tail > 0:
        out[-tail:] *= np.cos(np.linspace(0.0, np.pi / 2, tail))[:, None] ** 2
    return out
