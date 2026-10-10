"""Starting-point plans for mashups, two-track transitions, and multi-track sets.

These encode DJ conventions so the agent starts from something musical and then edits by ear/QA:
- phrase lines every 4/8/16 bars; transitions start on section boundaries
- EDM (>= 115 bpm) blends are long (16 bars) with a hard bass swap at the midpoint
- hip hop blends are short (8 bars); big tempo gaps use an echo-out and a tempo step instead of a blend
- half/double-time pairing (70 <-> 140) instead of extreme stretching
- the incoming track keeps its own tempo after a blend via an 8-bar tempo ramp
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from glass_harbor import compat, library
from glass_harbor.compat import tempo_options
from glass_harbor.feedback import taste_default

EDM_MIN_BPM = 115.0
BLEND_MAX_STRETCH = 6.0
STYLES = ("auto", "blend", "cut", "echo", "filter")


def _phrase_floor(bar: int, size: int = 4) -> int:
    return max(1, ((bar - 1) // size) * size + 1)


def _sections(analysis: dict) -> list[dict]:
    return analysis.get("sections") or [{"start_bar": 1, "bars": analysis["grid"]["bar_count"], "energy": "mid"}]


def _bar_count(analysis: dict) -> int:
    return int(analysis["grid"]["bar_count"])


def drop_bar(analysis: dict) -> int:
    """First high-energy section (where a cut/echo transition should land), else bar 1."""
    for section in _sections(analysis):
        if section.get("energy") == "high" and section["start_bar"] > 1:
            return _phrase_floor(section["start_bar"])
    return 1


def outro_bar(analysis: dict, room: int) -> int:
    """Latest section boundary that leaves ``room`` bars of audio (the DJ-friendly mix-out point)."""
    bars = _bar_count(analysis)
    starts = [s["start_bar"] for s in _sections(analysis) if s["start_bar"] + room <= bars + 1]
    candidates = [s for s in starts if s > bars * 0.5]
    if candidates:
        return _phrase_floor(candidates[-1])
    return _phrase_floor(max(1, bars - room + 1))


def _is_edm(bpm: float) -> bool:
    return bpm >= EDM_MIN_BPM


def choose_style(prev_bpm: float, next_bpm: float, requested: str = "auto") -> str:
    if requested != "auto":
        return requested
    gap = abs(next_bpm / prev_bpm - 1.0) * 100.0
    if gap <= BLEND_MAX_STRETCH:
        return "blend"
    return "echo"


@dataclass
class _Track:
    source: str
    track: str
    analysis: dict
    ratio: float = 1.0
    entry: int = 1  # source bar where the track becomes audible
    exit: int = 1  # source bar where its out-transition starts
    out_start: float = 1.0  # output bar of ``entry``
    automation: dict[str, list[list[float]]] = field(default_factory=dict)

    @property
    def native_bpm(self) -> float:
        return float(self.analysis["bpm"]) * self.ratio


def _add_points(track: _Track, param: str, points: list[list[float]]) -> None:
    merged = track.automation.setdefault(param, [])
    for point in points:
        point = [round(point[0], 4), round(point[1], 2)]
        if merged and point[0] < merged[-1][0]:
            continue
        if merged and point[0] == merged[-1][0]:
            merged[-1] = point
        else:
            merged.append(point)


def _blend_length(bpm_a: float, bpm_b: float) -> int:
    key = "edm_blend_bars" if _is_edm(bpm_a) and _is_edm(bpm_b) else "hiphop_blend_bars"
    return int(taste_default(key))


def _add_tempo(tempo: list[dict[str, Any]], point: dict[str, Any]) -> None:
    """Append a tempo point, dropping earlier-scheduled points it would overlap (keeps bars ascending)."""
    while len(tempo) > 1 and tempo[-1]["bar"] >= point["bar"]:
        tempo.pop()
    if point["bar"] > tempo[-1]["bar"]:
        tempo.append(point)


def _ratio_for(prev_bpm: float, bpm: float) -> float:
    return tempo_options(bpm, prev_bpm)[0][0]


def build_set(track_ids: list[str], *, styles: list[str] | None = None, play_bars: int = 32,
              blend_bars: int | None = None, first_entry: int | None = None, first_exit: int | None = None,
              title: str = "", outro_bars: int = 16) -> dict[str, Any]:
    if len(track_ids) < 2:
        raise ValueError("A set needs at least two tracks.")
    styles = styles or ["auto"] * (len(track_ids) - 1)
    if len(styles) != len(track_ids) - 1 or any(s not in STYLES for s in styles):
        raise ValueError(f"Give one style per transition from: {', '.join(STYLES)}")

    tracks: list[_Track] = []
    for i, track_id in enumerate(track_ids):
        analysis = library.load_analysis(track_id)
        tracks.append(_Track(source=f"t{i + 1}", track=track_id, analysis=analysis))
    for prev, cur in zip(tracks, tracks[1:]):
        cur.ratio = _ratio_for(prev.native_bpm, float(cur.analysis["bpm"]))

    chosen = [choose_style(a.native_bpm, b.native_bpm, s) for a, b, s in zip(tracks, tracks[1:], styles)]
    lengths = [blend_bars or _blend_length(a.native_bpm, b.native_bpm)
               if style == "blend" else 0 for a, b, style in zip(tracks, tracks[1:], chosen)]

    tempo: list[dict[str, Any]] = [{"bar": 1, "bpm": round(tracks[0].native_bpm, 2)}]
    notes: list[str] = []
    first = tracks[0]
    first.entry = first_entry or 1
    first.out_start = 1.0
    for i, (a, b) in enumerate(zip(tracks, tracks[1:])):
        style, length = chosen[i], lengths[i]
        bars_a = _bar_count(a.analysis)
        # Where a hands over (source bars of a).
        if i == 0 and first_exit:
            a.exit = first_exit
        else:
            target = a.entry + int(round(play_bars / a.ratio))
            boundaries = [s["start_bar"] for s in _sections(a.analysis)
                          if abs(s["start_bar"] - target) <= 8 and s["start_bar"] > a.entry + 4]
            a.exit = _phrase_floor(min(boundaries, key=lambda bar: abs(bar - target)) if boundaries else target)
        room = int(math.ceil(length / a.ratio)) if style == "blend" else 0
        if a.exit + room > bars_a + 1:
            a.exit = _phrase_floor(max(a.entry + 4, bars_a + 1 - room))
        out_exit = a.out_start + (a.exit - a.entry) * a.ratio
        b.entry = 1 if style == "blend" else drop_bar(b.analysis)
        b.out_start = out_exit
        offset = (a.exit - a.entry) * a.ratio  # where a's out-transition starts, in a's clip bars

        if style == "blend":
            half = length / 2
            _add_points(a, "eq_low_db", [[offset + half - 0.0625, 0], [offset + half, -40]])
            _add_points(a, "highpass_hz", [[offset + half, 20], [offset + length, 700]])
            _add_points(a, "gain_db", [[offset + length * 0.75, 0], [offset + length, -40]])
            _add_points(b, "eq_low_db", [[0, -40], [half - 0.0625, -40], [half, 0]])
            _add_points(b, "gain_db", [[0, -10], [length / 4, 0]])
            if abs(b.native_bpm - a.native_bpm) > 0.05:
                _add_tempo(tempo, {"bar": out_exit + length, "bpm": round(a.native_bpm, 2)})
                _add_tempo(tempo, {"bar": out_exit + length + 8, "bpm": round(b.native_bpm, 2), "ramp": True})
            notes.append(f"{a.track} -> {b.track}: {length}-bar blend with bass swap at output bar "
                         f"{out_exit + half:g}")
        else:
            if style == "filter":
                _add_points(a, "lowpass_hz", [[offset - 4, 20000], [offset, 350]])
            if abs(b.native_bpm - a.native_bpm) > 0.05:
                _add_tempo(tempo, {"bar": out_exit, "bpm": round(b.native_bpm, 2)})
            notes.append(f"{a.track} -> {b.track}: {style} at output bar {out_exit:g}"
                         f" ({a.native_bpm:.0f} -> {b.native_bpm:.0f} bpm), {b.track} enters at its bar {b.entry}")

    clips: list[dict[str, Any]] = []
    for i, track in enumerate(tracks):
        is_last = i == len(tracks) - 1
        style_out = None if is_last else chosen[i]
        if is_last:
            end = min(_bar_count(track.analysis) + 1, track.entry + int(round((play_bars + outro_bars) / track.ratio)))
            length = end - track.entry
            out_len = length * track.ratio
            _add_points(track, "gain_db", [[out_len - 8, 0], [out_len, -40]])
        elif style_out == "blend":
            length = track.exit - track.entry + int(math.ceil(lengths[i] / track.ratio))
        elif style_out == "echo":
            length = track.exit - track.entry - 1
        else:
            length = track.exit - track.entry
        clip: dict[str, Any] = {
            "id": track.source,
            "source": track.source,
            "stem": "mix",
            "from_bar": track.entry,
            "bars": length,
            "at_bar": track.out_start,
        }
        if track.automation:
            clip["automation"] = track.automation
        clips.append(clip)
        if style_out == "echo":
            clips.append({
                "id": f"{track.source}-echo",
                "source": track.source,
                "stem": "mix",
                "from_bar": track.exit - 1,
                "bars": 1,
                "at_bar": track.out_start + (track.exit - 1 - track.entry) * track.ratio,
                "automation": {"highpass_hz": [[0, 20], [1, 400]]},
                "fx": {"echo": {"beats": 0.75, "feedback": 0.55, "mix": 0.45}},
                "tail_beats": 8,
            })

    sources = {}
    for track in tracks:
        entry: dict[str, Any] = {"track": track.track}
        if track.ratio != 1:
            entry["tempo_ratio"] = track.ratio
        sources[track.source] = entry
    plan: dict[str, Any] = {
        "version": 1,
        "title": title or " -> ".join(t.track for t in tracks),
        "kind": "set" if len(tracks) > 2 else "transition",
        "beats_per_bar": 4,
    }
    plan.update({"tempo": tempo} if len(tempo) > 1 else {"bpm": tempo[0]["bpm"]})
    plan.update({
        "sources": sources,
        "clips": clips,
        "master": {"lufs": float(taste_default("master_lufs")), "ceiling_db": -1.0},
        "notes": notes,
    })
    return plan


def build_transition(a: str, b: str, *, style: str = "auto", pre_bars: int = 16, blend_bars: int | None = None,
                     title: str = "") -> dict[str, Any]:
    analysis_a = library.load_analysis(a)
    bpm_b = float(library.load_analysis(b)["bpm"])
    ratio_b = _ratio_for(float(analysis_a["bpm"]), bpm_b)
    chosen = choose_style(float(analysis_a["bpm"]), bpm_b * ratio_b, style)
    length = blend_bars or _blend_length(float(analysis_a["bpm"]), bpm_b * ratio_b)
    exit_bar = outro_bar(analysis_a, length if chosen == "blend" else 0)
    entry = max(1, exit_bar - pre_bars)
    plan = build_set([a, b], styles=[chosen], play_bars=pre_bars, blend_bars=blend_bars, first_entry=entry,
                     first_exit=exit_bar, title=title, outro_bars=0)
    plan["kind"] = "transition"
    return plan


def build_mashup(vocals: str, bed: str, *, semitones: int | None = None, intro_bars: int = 8,
                 outro_bars: int = 8, max_vocal_bars: int = 48, title: str = "") -> dict[str, Any]:
    vox = library.load_analysis(vocals)
    beat = library.load_analysis(bed)
    if "vocals" not in library.available_stems(vocals):
        raise ValueError(f"{vocals} has no vocals stem yet: glass-harbor track separate {vocals} --stems vocals")
    bed_stem = "instrumental" if "instrumental" in library.available_stems(bed) else "mix"
    fit = compat.score_pair(vocals, vox, bed, beat)[0]
    shift = fit.semitones if semitones is None else semitones
    ratio = fit.tempo_ratio
    phrases = vox["stems"]["vocals"].get("phrases", [])
    if not phrases:
        raise ValueError(f"No vocal phrases detected in {vocals}; check the vocals stem.")

    clips: list[dict[str, Any]] = []
    at_bar = 1 + intro_bars
    used = 0
    last_end = None
    for phrase in phrases:
        start = _phrase_floor(phrase["start_bar"])
        length = int(math.ceil((phrase["start_bar"] + phrase["bars"] - start) / 4.0) * 4)
        length = min(length, 16)
        if last_end is not None and start < last_end:
            continue
        if last_end is not None and start - last_end >= 4:
            at_bar += 4  # let the beat breathe between separated vocal sections
        out_len = int(length * ratio)
        if used + out_len > max_vocal_bars:
            break
        clips.append({
            "id": f"vox{len(clips) + 1}",
            "source": "vox",
            "stem": "vocals",
            "from_bar": start,
            "bars": length,
            "at_bar": at_bar,
            "automation": {"highpass_hz": [[0, float(taste_default("vocal_highpass_hz"))]]},
        })
        at_bar += out_len
        used += out_len
        last_end = start + length

    total_bars = at_bar - 1 + outro_bars
    bed_bars = _bar_count(beat)
    bed_clips: list[dict[str, Any]] = []
    if bed_bars >= total_bars:
        bed_clips.append({"id": "bed", "source": "bed", "stem": bed_stem, "from_bar": 1, "bars": total_bars,
                          "at_bar": 1, "automation": {"gain_db": [[total_bars - outro_bars, 0], [total_bars, -40]]},
                          "duck": {"under": "vocals", "db": float(taste_default("duck_db"))}})
    else:
        # Loop the bed's strongest 8-bar phrase to cover the vocals.
        loud = max(_sections(beat), key=lambda s: s.get("mean_db", -99))
        loop_from = _phrase_floor(loud["start_bar"])
        loop_len = 8 if loop_from + 8 <= bed_bars + 1 else 4
        intro_len = min(bed_bars, max(4, (bed_bars // 4) * 4))
        bed_clips.append({"id": "bed", "source": "bed", "stem": bed_stem, "from_bar": 1, "bars": intro_len,
                          "at_bar": 1, "duck": {"under": "vocals", "db": float(taste_default("duck_db"))}})
        remaining = total_bars - intro_len
        loops = int(math.ceil(remaining / loop_len))
        bed_clips.append({"id": "bed-loop", "source": "bed", "stem": bed_stem, "from_bar": loop_from,
                          "bars": loop_len, "loop": loops, "at_bar": 1 + intro_len,
                          "automation": {"gain_db": [[loops * loop_len - outro_bars, 0], [loops * loop_len, -40]]},
                          "duck": {"under": "vocals", "db": float(taste_default("duck_db"))}})

    vox_source: dict[str, Any] = {"track": vocals, "semitones": shift}
    if ratio != 1:
        vox_source["tempo_ratio"] = ratio
    return {
        "version": 1,
        "title": title or f"{vocals} x {bed}",
        "kind": "mashup",
        "bpm": round(float(beat["bpm"]), 2),
        "beats_per_bar": 4,
        "sources": {"vox": vox_source, "bed": {"track": bed}},
        "clips": bed_clips + clips,
        "master": {"lufs": float(taste_default("master_lufs")), "ceiling_db": -1.0},
        "notes": [
            f"fit: {fit.relation}, {fit.key_a} over {fit.key_b}, {fit.stretch_pct:+.1f}% stretch on vocals, "
            f"score {fit.score}",
            "vocal phrases were placed back to back from the source; reorder or swap for the strongest hook",
        ],
    }


def _merge_points(existing: list[list[float]] | None, start: float, end: float,
                  new: list[list[float]]) -> list[list[float]]:
    kept = [p for p in (existing or []) if p[0] < start or p[0] > end]
    return sorted(kept + new, key=lambda p: p[0])


def add_drop(plan: dict[str, Any], at_bar: float, *, build_bars: float = 8, clip_ids: list[str] | None = None,
             riser: bool = True, impact: bool = True, silence_beats: float = 1.0) -> dict[str, Any]:
    """Build -> silence -> drop at ``at_bar``: high-pass sweep on the beds, a beat of silence, a generated riser
    that ends on the downbeat, and an impact on the one."""
    from glass_harbor.plan import resolve

    res = resolve(plan)
    if not res.ok:
        raise ValueError("fix plan errors before adding a drop")
    bpb = res.beats_per_bar
    start_bar = at_bar - build_bars
    if start_bar < 1:
        raise ValueError("the build would start before bar 1")
    start_beat, drop_beat = (start_bar - 1) * bpb, (at_bar - 1) * bpb
    targets = [c for c in res.clips if c.stem not in ("vocals", "fx") and c.out_start_beat < drop_beat
               and c.out_end_beat > start_beat and (clip_ids is None or c.id in clip_ids)]
    if not targets:
        raise ValueError("no bed clip plays during the build; pass --clips")
    gap = silence_beats / bpb
    for target in targets:
        spec = plan["clips"][target.index]
        anchor_bar = spec["at_bar"]
        s0, e0 = start_bar - anchor_bar, at_bar - anchor_bar
        automation = spec.setdefault("automation", {})
        automation["highpass_hz"] = _merge_points(automation.get("highpass_hz"), s0, e0, [
            [round(s0, 4), 20], [round(e0 - gap, 4), 700], [round(e0 - 0.002, 4), 700], [round(e0, 4), 20]])
        if silence_beats:
            automation["gain_db"] = _merge_points(automation.get("gain_db"), e0 - gap - 0.01, e0, [
                [round(e0 - gap - 0.003, 4), 0], [round(e0 - gap, 4), -60], [round(e0 - 0.002, 4), -60],
                [round(e0, 4), 0]])
    if riser:
        plan["clips"].append({"id": f"riser-{at_bar:g}", "generate": "riser", "at_bar": start_bar,
                              "bars": build_bars - gap if silence_beats else build_bars, "gain_db": -9})
    if impact:
        plan["clips"].append({"id": f"impact-{at_bar:g}", "generate": "impact", "at_bar": at_bar, "bars": 2,
                              "gain_db": -5})
    plan.setdefault("notes", []).append(
        f"drop at bar {at_bar:g}: {build_bars:g}-bar build on {', '.join(t.id for t in targets)}"
        f"{', riser' if riser else ''}{', impact' if impact else ''}, {silence_beats:g} beat(s) of silence")
    return plan
