"""Draft moves for mashups that the chorus-on-drop arranger (``scaffold.smart_arrangement``) does not cover.

- ``song_order``: rap songs built on short chants rather than long choruses keep their own order. The first verse
  lands on the beat's first full section, the intro and chants before it ride the build, and when the beat breaks
  down the vocal stops at a line ending and picks up again on the next drop.
- ``own_intro_bars``: beats that already open with a beatless DJ intro don't get a second one.
- ``add_reprise``: a back half left without vocals gets the end of the first verse again on its biggest section.
- ``add_bed_answers``: the beat's own vocal shouts answer the acapella where it is silent.
- ``add_halftime_switch``: on drum & bass beds, one verse run rides a half-time beat built from the record's own
  kit, then the full beat slams back.

Every move writes a plan note, so the agent and the user can see (and undo) what the draft decided.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from glass_harbor import library

VOCAL_HIGHPASS_HZ = 100.0


MAX_CLIP_BARS = 12  # vocal bars per clip at most (long verses are split at line starts)
BREATH_BARS = 0.1  # a gap between lines long enough to cut at (about 270 ms at 90 bpm)
BAR_TOLERANCE = 0.05  # a line starting a few ms before a bar line (a pickup, or 25.9999 for 26) belongs to that bar


def _floor(bar: float) -> int:
    return max(1, math.floor(bar + BAR_TOLERANCE))


def _ceil(bar: float) -> int:
    return max(1, math.ceil(bar - BAR_TOLERANCE))


def _lines(lyrics: dict[str, Any], grid) -> list[dict[str, Any]]:
    from glass_harbor.lyrics import _normalize

    out = []
    for seg in lyrics["segments"]:
        out.append({"start": grid.bar_at_time(seg["start"]), "end": grid.bar_at_time(seg["end"]),
                    "words": len(seg["words"]), "text": _normalize(seg["text"])})
    return out


def _split_at_lines(a: int, b: int, starts: list[int], limit: int | None = None) -> list[tuple[int, int]]:
    """Split [a, b) at line starts into pieces of at most ``limit`` bars, cutting at the last line start that
    still fits; a single line longer than the limit stays whole."""
    limit = limit or MAX_CLIP_BARS
    cuts = sorted({c for c in starts if a < c < b})
    pieces, start, previous = [], a, None
    for cut in cuts + [b]:
        if cut - start > limit and previous is not None and previous > start:
            pieces.append((start, previous))
            start = previous
        previous = cut
    pieces.append((start, b))
    return [(x, y) for x, y in pieces if y > x]


def _hook_texts(lines: list[dict[str, Any]], *, min_count: int = 2) -> set[str]:
    """Short repeated lines (chants and tags count, not just full choruses)."""
    counts: dict[str, int] = {}
    for line in lines:
        if 2 <= line["words"] <= 8:
            counts[line["text"]] = counts.get(line["text"], 0) + 1
    return {text for text, n in counts.items() if n >= min_count}


def full_start(beat: dict[str, Any]) -> int | None:
    """First bar where the beat is properly full: an allin1 chorus/drop section, else the first sustained run of
    loud bars (8 bars at most 2.5 dB under the median), else the first detected drop."""
    sections = beat.get("sections", [])
    for section in sections:
        if section.get("label") in ("chorus", "drop") and section["start_bar"] >= 9:
            return int(section["start_bar"])
    levels = beat.get("bar_db") or []
    if levels:
        median = float(np.median(levels))
        for bar in range(9, len(levels) - 8):
            if all(v >= median - 2.5 for v in levels[bar - 1: bar + 7]):
                return bar
    drops = [d for d in beat.get("drops", []) if d >= 9]
    return drops[0] if drops else None


def breakdowns(beat: dict[str, Any], after: int) -> list[tuple[int, int]]:
    """(first bar, first bar after) of each low stretch of at least 8 bars after ``after`` (the beat thins out:
    the vocal should pause there and come back on the drop)."""
    levels = beat.get("bar_db") or []
    if not levels:
        return []
    median = float(np.median(levels))
    out = []
    bar = after
    while bar <= len(levels):
        if levels[bar - 1] <= median - 6.0:
            end = bar
            while end <= len(levels) and levels[end - 1] <= median - 6.0:
                end += 1
            if end - bar >= 8:
                out.append((bar, end))
            bar = end
        else:
            bar += 1
    return out


def song_order(vocals: str, beat: dict[str, Any], ratio: float, lyrics: dict[str, Any] | None
               ) -> tuple[list[dict[str, Any]], list[int], list[str]] | None:
    """Vocal clips in the song's own order, split into rap and chant/hook clips at line boundaries.
    Returns (clips, drop bars to build, notes) or None without lyrics or a full section to aim for."""
    from glass_harbor.grid import Grid

    if not lyrics or not lyrics.get("segments") or ratio not in (0.5, 1.0, 2.0):
        return None
    vox = library.load_analysis(vocals)
    grid = Grid.from_dict(vox["grid"])
    lines = _lines(lyrics, grid)
    target = full_start(beat)
    if target is None or not lines:
        return None
    hooks = _hook_texts(lines)
    from glass_harbor.lyrics_ref import load_reference, repeated_spans

    reference = load_reference(vocals)
    # Published lyrics show which lines really repeat (Whisper often mishears a sung chorus the second time).
    ref_hooks = [(grid.bar_at_time(a), grid.bar_at_time(b)) for a, b in repeated_spans(reference)] if reference else []

    def is_hook(line: dict[str, Any]) -> bool:
        mid = (line["start"] + line["end"]) / 2
        return line["text"] in hooks or any(a <= mid < b for a, b in ref_hooks)

    # The first proper verse line (6+ words) after something to open with, else the first line.
    verse = next((ln for ln in lines if ln["words"] >= 6 and ln["start"] >= lines[0]["start"] + 1), lines[0])
    anchor = _floor(verse["start"])
    first = _floor(lines[0]["start"])
    offset = target - anchor * ratio  # output bar of vocal bar v: offset + v * ratio
    if offset + first * ratio < 9:  # keep 8 bars of beat before the first word
        first = math.ceil((9 - offset) / ratio)
    last_bar = len(beat.get("bar_db") or []) or grid.bar_count
    pauses = breakdowns(beat, target)
    drops = sorted(d for d in beat.get("drops", []) if d > target)

    clips: list[dict[str, Any]] = []
    notes = [f"song order: verse 1 (vocal bar {anchor}) lands on the beat's first full section (bar {target})"]
    builds: list[int] = []
    out_of = lambda v: offset + v * ratio  # noqa: E731
    v = first
    end_v = _ceil(lines[-1]["end"])
    while v < end_v:
        pause = next(((a, b) for a, b in pauses if a > out_of(v)), None)
        stop_v = end_v
        if pause is not None and out_of(end_v) > pause[0]:
            # Stop at the last line that ends before the breakdown; resume at the next drop after it.
            # Stop after a line followed by a breath (BREATH_BARS of silence), so no word is cut. If the last
            # breath before the breakdown leaves more than 8 bars of drop empty, let the flow run up to 8 bars into
            # the breakdown (an a cappella moment) and stop at a breath there.
            breaths = [ln for i, ln in enumerate(lines) if v <= ln["start"] and out_of(_ceil(ln["end"])) <= pause[0] + 8
                       and (i + 1 == len(lines) or lines[i + 1]["start"] - ln["end"] >= BREATH_BARS
                            and lines[i + 1]["start"] >= _ceil(ln["end"]) - BAR_TOLERANCE)]
            before = [ln for ln in breaths if out_of(_ceil(ln["end"])) <= pause[0]]
            after = [ln for ln in breaths if out_of(_ceil(ln["end"])) > pause[0]]
            if before and (pause[0] - out_of(_ceil(before[-1]["end"])) <= 8 or not after):
                stop_v = _ceil(before[-1]["end"])
            elif after:
                stop_v = _ceil(after[0]["end"])
            else:
                stop_v = v
        chunk = [ln for ln in lines if v <= ln["start"] < stop_v]
        # Runs of lines by role: chants/hooks (with the one- or two-word ad-libs that trail them, and the intro
        # before verse 1) get the hook chain, everything else is verse.
        roles = []
        for ln in chunk:
            hooky = is_hook(ln) or ln["start"] < anchor and v == first \
                or (ln["words"] <= 2 and bool(roles) and roles[-1][1])
            if roles and roles[-1][1] == hooky:
                roles[-1][0].append(ln)
            else:
                roles.append(([ln], hooky))
        for i, (run, hooky) in enumerate(roles):
            a = v if i == 0 else _floor(run[0]["start"])
            b = stop_v if i + 1 == len(roles) else _floor(roles[i + 1][0][0]["start"])
            if b <= a:
                continue
            # Long runs split at line starts into pieces of at most MAX_CLIP_BARS, so a beat shorter than the
            # song keeps as much as fits (ending on a whole line) instead of losing the whole run.
            pieces = _split_at_lines(a, b, [_floor(ln["start"]) for ln in run[1:]])
            for pa, pb in pieces:
                if pb <= pa:
                    continue
                clips.append({"id": f"{'hook' if hooky else 'verse'}{len(clips) + 1}", "source": "vox",
                              "stem": "vocals", "from_bar": int(pa), "bars": int(pb - pa), "at_bar": out_of(pa),
                              **({"chain": "hook"} if hooky else {}),
                              "automation": {"highpass_hz": [[0, VOCAL_HIGHPASS_HZ]]}})
        if stop_v >= end_v or pause is None:
            break
        resume = next((d for d in drops if d >= pause[1]), pause[1])
        nxt = next((ln for ln in lines if ln["start"] >= stop_v), None)
        if nxt is None or resume + 8 > last_bar:
            break
        v = _floor(nxt["start"])
        offset = resume - v * ratio
        builds.append(resume)
        notes.append(f"vocal pauses for the breakdown at bar {pause[0]} and comes back on the bar-{resume} drop")
        build = _chant_build(lyrics, lines, hooks, resume)
        if build:
            clips.append(build)
            notes.append(f"the chant is chopped into a build over bars {resume - 8}-{resume - 1}")
    kept = []
    for clip in clips:
        scale = ratio if "from_bar" in clip else 1
        if clip["at_bar"] + clip.get("bars", 0) * scale <= last_bar + 1:
            kept.append(clip)
        elif "from_bar" in clip:
            # Keep the part that fits, cut at the last line start inside it (never mid-line).
            room = (last_bar + 1 - clip["at_bar"]) / scale
            starts = [_floor(ln["start"]) for ln in lines
                      if clip["from_bar"] < _floor(ln["start"]) <= clip["from_bar"] + room]
            if starts:
                kept.append({**clip, "bars": int(starts[-1] - clip["from_bar"])})
    if len(kept) < len(clips):
        notes.append(f"the beat ends before the song: the draft keeps {len(kept)} of {len(clips)} vocal pieces "
                     "(extend the beat or pick a longer one to use the rest)")
    clips = kept
    for clip in clips:
        clip["at_bar"] = round(clip["at_bar"], 4)
    if not clips:
        return None
    return clips, builds, notes


CHANT_BUILD = ["a-------b-------", "................", "a-------b-------", "................",
               "a-------b-------", "a-------b-------", "a---a---b---b---", "a-a-a-a-b-b-b-b-"]


def _chant_build(lyrics: dict[str, Any], lines: list[dict[str, Any]], hooks: set[str], drop: int
                 ) -> dict[str, Any] | None:
    """An 8-bar chop build into ``drop`` from the chant's first two words, accelerating into the one."""
    from glass_harbor.lyrics import _normalize

    chant = next((ln["text"] for ln in lines if ln["text"] in hooks), None)
    if not chant or drop < 9:
        return None
    words = chant.split()[:2]
    if len(words) == 1:
        words = words * 2
    every = [_normalize(w["word"]) for seg in lyrics["segments"] for w in seg["words"]]
    occurrence = {}
    for word in set(words):
        index = next((i for i, text in enumerate(every) if text == word), None)
        if index is None:
            return None
        occurrence[word] = sum(1 for text in every[: index + 1] if text == word)
    return {"id": f"chant-build-{drop}", "source": "vox", "stem": "vocals", "at_bar": drop - 8, "bars": 8,
            "gain_db": 1.0, "fx": {"echo": {"beats": 0.75, "feedback": 0.3, "mix": 0.2}},
            "automation": {"highpass_hz": [[0, 200]]},
            "chop": {"slices": {"a": {"word": words[0], "occurrence": occurrence[words[0]]},
                                "b": {"word": words[1], "occurrence": occurrence[words[1]]}},
                     "pattern": CHANT_BUILD}}


def own_intro_bars(beat: dict[str, Any]) -> int:
    """Bars of beatless intro the record opens with (no kick or bass), rounded down to 8s."""
    low = beat.get("low_db") or []
    if len(low) < 16:
        return 0
    median = float(np.median(low))
    bars = 0
    while bars < len(low) and low[bars] < median - 10:
        bars += 1
    return (bars // 8) * 8


def _vocal_spans(plan: dict[str, Any]) -> list[tuple[float, float, dict[str, Any]]]:
    from glass_harbor.plan import resolve

    res = resolve(plan)
    bpb = res.beats_per_bar
    return [(1 + c.out_start_beat / bpb, 1 + c.out_end_beat / bpb, plan["clips"][c.index])
            for c in res.clips if c.stem == "vocals"]


def add_reprise(plan: dict[str, Any], beat: dict[str, Any], *, min_share: float = 0.5) -> dict[str, Any]:
    """If the back 40% of the beat has vocals on less than ``min_share`` of its bars, bring the end of the first
    verse (8 vocal bars) back at the start of the longest vocal-free stretch there (on a drop when one is in it)."""
    total = len(beat.get("bar_db") or [])
    spans = _vocal_spans(plan)
    if not total or not spans:
        return plan
    back = int(total * 0.6)
    voiced = {b for s, e, _ in spans for b in range(int(math.floor(s)), int(math.ceil(e)))}
    share = sum(1 for b in range(back, total + 1) if b in voiced) / max(1, total + 1 - back)
    verses = [c for _, _, c in spans if c.get("chain") != "hook" and "from_bar" in c and c["bars"] >= 8]
    if share >= min_share or not verses:
        return plan
    gaps, start = [], None
    for bar in range(back, total + 2):
        if bar not in voiced and bar <= total and start is None:
            start = bar
        elif (bar in voiced or bar > total) and start is not None:
            gaps.append((start, bar))
            start = None
    gaps = [(a, b) for a, b in gaps if b - a >= 16]
    if not gaps:
        return plan
    a, b = max(gaps, key=lambda g: g[1] - g[0])
    drops = [d for d in beat.get("drops", []) if a <= d < b - 8]
    at = drops[0] if drops else a + (-(a - 1) % 4)  # a drop, else the next phrase line
    verse = verses[0]
    ratio = float((plan["sources"]["vox"].get("tempo_ratio") or 1))
    length = 8 if ratio >= 1 else 16
    if at + length * ratio > b:
        return plan
    plan["clips"].append({"id": "verse-reprise", "source": "vox", "stem": "vocals",
                          "from_bar": verse["from_bar"] + verse["bars"] - length, "bars": length, "at_bar": at,
                          "automation": {"highpass_hz": [[0, VOCAL_HIGHPASS_HZ]]}})
    plan.setdefault("notes", []).append(
        f"reprise: the back of the track had vocals on {share:.0%} of its bars; the last {length} bars of "
        f"{verse['id']} come back at bar {at}")
    return plan


def add_bed_answers(plan: dict[str, Any], bed: str, *, max_shouts: int = 6) -> dict[str, Any]:
    """Place the beat's own short vocal shouts (lines of up to 4 words) where they already sit in the beat, wherever
    the acapella is silent around them: call and response, already in time with the beat."""
    from glass_harbor.grid import Grid
    from glass_harbor.lyrics import load_lyrics
    from glass_harbor.plan import resolve

    lyrics = load_lyrics(bed)
    if not lyrics or "vocals" not in library.available_stems(bed):
        return plan
    grid = Grid.from_dict(library.load_analysis(bed)["grid"])
    res = resolve(plan)
    bpb = res.beats_per_bar
    bed_clips = [c for c in res.clips if c.source == "bed" and c.stem in ("drums", "instrumental", "mix")
                 and c.loop == 1 and c.out_beats_per_src_beat == 1]
    busy = [(s - 1, e + 1) for s, e, _ in _vocal_spans(plan)]
    busy += [(c["at_bar"] - 1, c["at_bar"] + c["bars"] + 1) for c in plan["clips"] if c.get("chop")]
    placed: list[str] = []
    for seg in lyrics["segments"]:
        if len(seg["words"]) > 4 or len(placed) >= max_shouts:
            continue
        start, end = grid.bar_at_time(seg["start"]), grid.bar_at_time(seg["end"])
        from_bar = _floor(start)
        bars = max(1, _ceil(end) - from_bar)
        for clip in bed_clips:
            src_from = clip.spec["from_bar"]
            if not (src_from <= from_bar and from_bar + bars <= src_from + clip.spec["bars"]):
                continue
            at = 1 + clip.anchor_beat / bpb + (from_bar - src_from)
            if any(a < at + bars and at < b for a, b in busy):
                continue
            plan["clips"].append({"id": f"bed-shout-{at:g}", "source": "bed", "stem": "vocals", "from_bar": from_bar,
                                  "bars": bars, "at_bar": at, "chain": "hook"})
            busy.append((at - 1, at + bars + 1))
            placed.append(f"{at:g}")
            break
    if placed:
        plan.setdefault("notes", []).append(
            f"the beat's own vocal answers the acapella at bar(s) {', '.join(placed)} (call and response)")
    return plan


HALFTIME_MIN_BPM = 160.0


def add_halftime_switch(plan: dict[str, Any], *, min_bars: int = 12, max_bars: int = 24) -> dict[str, Any]:
    """Drum & bass beds: the second run of verses (12-24 bars, between the first verse and the next breakdown)
    rides a half-time beat played on the record's own kit, with the bed's drums muted; the last bar strips the
    bass and melody, a snare roll from the real kit leads in, and the full beat slams back with an impact."""
    from glass_harbor.plan import resolve
    from glass_harbor.scaffold import _lane_override

    if float(plan.get("bpm", 0)) < HALFTIME_MIN_BPM:
        return plan
    res = resolve(plan)
    bpb = res.beats_per_bar
    drums = [c for c in res.clips if c.source == "bed" and c.stem == "drums" and c.loop == 1]
    vocals = sorted(((1 + c.out_start_beat / bpb, 1 + c.out_end_beat / bpb, c) for c in res.clips
                     if c.stem == "vocals" and c.chop is None), key=lambda v: v[0])
    verses = [v for v in vocals if v[2].spec.get("chain") != "hook"]
    if len(verses) < 2 or not drums:
        return plan
    start = math.ceil(verses[1][0] - 0.25)
    end = start
    for s, e, clip in vocals:  # extend through the following verse and chant clips while they run back to back
        if s < start - 0.5:
            continue
        if s > end + 1 or math.ceil(e - 0.25) - start > max_bars:
            break
        end = math.ceil(e - 0.25)
    if end - start < min_bars:
        return plan
    host = next((c for c in drums if 1 + c.anchor_beat / bpb <= start and end <= 1 + c.out_end_beat / bpb), None)
    if host is None:
        return plan
    anchor = 1 + host.anchor_beat / bpb
    _lane_override(plan["clips"][host.index].setdefault("automation", {}), "arrange_db", start - anchor,
                   end - anchor, -60.0)
    for clip in res.clips:
        if clip.source == "bed" and clip.stem in ("bass", "other") and clip.loop == 1 \
                and 1 + clip.anchor_beat / bpb <= end - 1 < 1 + clip.out_end_beat / bpb:
            off = end - 1 - (1 + clip.anchor_beat / bpb)
            _lane_override(plan["clips"][clip.index].setdefault("automation", {}), "arrange_db", off, off + 1, -60.0)
    plan["clips"] += [
        {"id": f"halftime-{start}", "generate": "halftime", "source": "bed", "at_bar": start, "bars": end - start - 2,
         "gain_db": -3.0, "duck": {"under": "vocals", "db": 6.0}},
        {"id": f"roll-{end}", "generate": "snare_roll", "source": "bed", "at_bar": end - 2, "bars": 2, "gain_db": -3.0,
         "duck": {"under": "vocals", "db": 8.0}},
        {"id": f"impact-{end}", "generate": "impact", "at_bar": end, "bars": 2, "gain_db": -6.0},
    ]
    plan.setdefault("notes", []).append(
        f"half-time switch: bars {start}-{end - 1} ride a half-time beat from the record's own kit (drums muted), "
        f"bass and melody out on bar {end - 1}, snare roll and impact back into the full beat at {end}")
    return plan
