"""Starting-point plans for mashups, two-track transitions, and multi-track sets.

These encode DJ conventions so the agent starts from something musical and then edits by ear/QA:
- phrase lines every 4/8/16 bars; transitions start on section boundaries
- EDM (>= 115 bpm) blends are long (16 bars) with a hard bass swap at the midpoint
- hip hop blends are short (8 bars); big tempo gaps use an echo-out and a tempo step instead of a blend
- half/double-time pairing (70 <-> 140) instead of extreme stretching
- the incoming track keeps its own tempo after a blend via an 8-bar tempo ramp
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from glass_harbor import compat, library
from glass_harbor.compat import tempo_options
from glass_harbor.feedback import taste_default

EDM_MIN_BPM = 115.0
FILL_DUCK = {"under": "vocals", "db": 8.0}  # fills never mask the vocal
BLEND_MAX_STRETCH = 6.0
STYLES = ("auto", "blend", "cut", "echo", "filter", "stems")


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
               if style in ("blend", "stems") else 0 for a, b, style in zip(tracks, tracks[1:], chosen)]
    for a, b, style in zip(tracks, tracks[1:], chosen):
        if style == "stems":
            need = {a.track: {"bass", "other", "vocals"}, b.track: {"drums", "bass", "other"}}
            for track_id, stems in need.items():
                missing = stems - set(library.available_stems(track_id))
                if missing:
                    raise ValueError(f"stem-swap needs {', '.join(sorted(missing))} for {track_id}")
            if b.ratio != 1:
                raise ValueError("stem-swap needs the two tracks at the same metrical level (no half/double time)")

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
        room = int(math.ceil(length / a.ratio)) if style in ("blend", "stems") else 0
        if a.exit + room > bars_a + 1:
            a.exit = _phrase_floor(max(a.entry + 4, bars_a + 1 - room))
        out_exit = a.out_start + (a.exit - a.entry) * a.ratio
        b.entry = 1 if style == "blend" else drop_bar(b.analysis)
        b.out_start = out_exit
        offset = (a.exit - a.entry) * a.ratio  # where a's out-transition starts, in a's clip bars

        if style == "stems":
            if abs(b.native_bpm - a.native_bpm) > 0.05:
                _add_tempo(tempo, {"bar": out_exit + length, "bpm": round(a.native_bpm, 2)})
                _add_tempo(tempo, {"bar": out_exit + length + 8, "bpm": round(b.native_bpm, 2), "ramp": True})
            notes.append(f"{a.track} -> {b.track}: {length}-bar stem swap from output bar {out_exit:g} (drums, then "
                         f"bass at {out_exit + length / 2:g}, then melody at {out_exit + 3 * length / 4:g})")
        elif style == "blend":
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
        style_in = chosen[i - 1] if i else None
        lead = lengths[i - 1] if style_in == "stems" else 0
        if lead:
            # The incoming track's first bars are played as stems (see below); the full mix starts after them.
            length -= lead
        clip: dict[str, Any] = {
            "id": track.source,
            "source": track.source,
            "stem": "mix",
            "from_bar": track.entry + lead,
            "bars": length,
            "at_bar": track.out_start + lead,
        }
        if track.automation:
            clip["automation"] = track.automation
        clips.append(clip)
        if style_out == "stems":
            nxt = tracks[i + 1]
            swap = lengths[i]
            at = track.out_start + (track.exit - track.entry) * track.ratio
            plan_out = [("vocals", 0, swap / 2), ("bass", 0, swap / 2), ("other", 0, 3 * swap / 4)]
            plan_in = [("drums", 0, swap), ("bass", swap / 2, swap), ("other", 3 * swap / 4, swap)]
            for stem, a0, a1 in plan_out:
                clips.append({"id": f"{track.source}-{stem}-out", "source": track.source, "stem": stem,
                              "from_bar": track.exit + a0, "bars": a1 - a0, "at_bar": at + a0, "fade_out_beats": 1,
                              **({"chain": "none", "word_safe": False} if stem == "vocals" else {})})
            for stem, a0, a1 in plan_in:
                clips.append({"id": f"{nxt.source}-{stem}-in", "source": nxt.source, "stem": stem,
                              "from_bar": nxt.entry + a0, "bars": a1 - a0, "at_bar": at + a0})
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
    exit_bar = outro_bar(analysis_a, length if chosen in ("blend", "stems") else 0)
    entry = max(1, exit_bar - pre_bars)
    # The incoming track plays its blend, then at least 8 bars alone before the closing fade.
    outro = length + 8 if chosen in ("blend", "stems") else 0
    plan = build_set([a, b], styles=[chosen], play_bars=pre_bars, blend_bars=blend_bars, first_entry=entry,
                     first_exit=exit_bar, title=title, outro_bars=outro)
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

    smart = smart_arrangement(vocals, bed, vox, beat, ratio, library.load_meta(vocals).get("title", vocals))
    clips: list[dict[str, Any]] = []
    at_bar = 1 + intro_bars
    used = 0
    last_end = None
    for phrase in ([] if smart else phrases):
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

    drop_builds: list[tuple[int, float]] = []
    if smart:
        clips, drop_builds, smart_notes = smart
        at_bar = max(c["at_bar"] + c["bars"] * (ratio if "chop" not in c else 1) for c in clips)
    total_bars = at_bar - 1 + outro_bars
    bed_bars = _bar_count(beat)
    if smart:
        total_bars = bed_bars  # the draft follows the beat's own structure end to end
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

    hook_starts = [o["start_bar"] for h in vox.get("hooks", []) for o in h.get("occurrences", [])]
    for clip in clips:
        if "from_bar" in clip and "chain" not in clip and any(
                clip["from_bar"] <= bar < clip["from_bar"] + clip["bars"] for bar in hook_starts):
            clip["chain"] = "hook"

    vox_source: dict[str, Any] = {"track": vocals, "semitones": shift}
    if ratio != 1:
        vox_source["tempo_ratio"] = ratio
    edm = _is_edm(float(beat["bpm"]))
    plan = {
        "version": 1,
        "title": title or f"{vocals} x {bed}",
        "kind": "mashup",
        "bpm": round(float(beat["bpm"]), 2),
        "beats_per_bar": 4,
        "sources": {"vox": vox_source, "bed": {"track": bed}},
        "clips": bed_clips + clips,
        # Master against the bed's own release so the mashup sits next to it in a set.
        "master": {"reference": bed, "ceiling_db": -1.0},
        "notes": [
            f"fit: {fit.relation}, {fit.key_a} over {fit.key_b}, {fit.stretch_pct:+.1f}% stretch on vocals, "
            f"score {fit.score}",
            "vocal phrases were placed back to back from the source; reorder or swap for the strongest hook",
        ],
    }
    if smart:
        plan["notes"] = [plan["notes"][0], *smart_notes]
    if edm:
        plan["groove"] = {"pump_fx": {"db": 5.0, "release": 0.6}}
    if {"drums", "bass", "other"} <= set(library.available_stems(bed)) and len(bed_clips) == 1:
        plan = arrange_bed_stems(plan, pump={"db": 3.0, "release": 0.5} if edm else None,
                                 drum_clip_db=3.0 if edm else 0.0)
    has_drums = "drums" in library.available_stems(bed)
    for bar, spotlight in drop_builds:
        try:
            # A title-line spotlight owns the break: no snare roll under it, and the riser ends where it starts.
            plan = add_drop(plan, bar, build_bars=8, roll=has_drums and not spotlight)
        except ValueError:
            continue  # no room for a build here (too close to the start)
        if spotlight:
            for clip in plan["clips"]:
                if clip.get("id") == f"riser-{bar:g}":
                    clip["bars"] = round(max(1.0, bar - spotlight - clip["at_bar"]), 4)
    plan = add_fills(plan)
    edges = int(taste_default("dj_edge_bars"))
    if edges:
        plan = add_dj_edges(plan, intro_bars=edges, outro_bars=edges)
    plan, _ = follow_vocal_roots(plan)
    return plan


def _merge_points(existing: list[list[float]] | None, start: float, end: float,
                  new: list[list[float]]) -> list[list[float]]:
    kept = [p for p in (existing or []) if p[0] < start or p[0] > end]
    return sorted(kept + new, key=lambda p: p[0])


def add_drop(plan: dict[str, Any], at_bar: float, *, build_bars: float = 8, clip_ids: list[str] | None = None,
             riser: bool | str = True, impact: bool = True, silence_beats: float = 1.0,
             roll: bool = False) -> dict[str, Any]:
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
    riser_bars = build_bars - gap if silence_beats else build_bars
    if isinstance(riser, str) and riser.startswith("vocal:"):
        word = riser.split(":", 1)[1]
        vox = next((c for c in res.clips if c.stem == "vocals"), None)
        if vox is None:
            raise ValueError("a vocal riser needs a vocal source in the plan")
        plan["clips"].append({"id": f"vocal-riser-{at_bar:g}", "generate": "vocal_riser", "source": vox.source,
                              "word": word, "at_bar": start_bar, "bars": riser_bars, "gain_db": -9, "duck": FILL_DUCK})
    elif riser:
        plan["clips"].append({"id": f"riser-{at_bar:g}", "generate": "riser", "at_bar": start_bar,
                              "bars": riser_bars, "gain_db": -9, "duck": FILL_DUCK})
    if roll:
        drum_source = targets[0].source
        roll_bars = min(2.0, build_bars)
        plan["clips"].append({"id": f"roll-{at_bar:g}", "generate": "snare_roll", "source": drum_source,
                              "at_bar": at_bar - roll_bars, "bars": roll_bars - gap if silence_beats else roll_bars,
                              "gain_db": -4, "duck": FILL_DUCK})
    if impact:
        plan["clips"].append({"id": f"impact-{at_bar:g}", "generate": "impact", "at_bar": at_bar, "bars": 2,
                              "gain_db": -5})
    plan.setdefault("notes", []).append(
        f"drop at bar {at_bar:g}: {build_bars:g}-bar build on {', '.join(t.id for t in targets)}"
        f"{(', vocal riser' if isinstance(riser, str) else ', riser') if riser else ''}{', snare roll' if roll else ''}"
        f"{', impact' if impact else ''}, "
        f"{silence_beats:g} beat(s) of silence")
    return plan


def _levels_to_points(levels: list[float], bpb: int, ramp_beats: float = 0.125) -> list[list[float]]:
    """Per-beat target levels -> automation points (bar offsets) with short ramps at each change."""
    points = [[0.0, levels[0]]]
    for k in range(1, len(levels)):
        if levels[k] != levels[k - 1]:
            points.append([round((k - ramp_beats) / bpb, 4), levels[k - 1]])
            points.append([round(k / bpb, 4), levels[k]])
    return points


def arrange_bed_stems(plan: dict[str, Any], *, bed_clip_id: str | None = None, verse_other_db: float = -60.0,
                      drums_only_bars: float = 1, pump: dict[str, float] | None = None,
                      duck_drums_db: float = 4.0, drum_clip_db: float = 0.0) -> dict[str, Any]:
    """Replace one bed clip with drums / bass / other clips and arrange them around the vocal: verses over drums +
    bass (the melodic layer stripped by ``verse_other_db``), choruses over the full beat, and a drums-only bar
    before each chorus. Ducking moves to the melodic layer; optional grid pumping on it too."""
    from glass_harbor.plan import resolve

    res = resolve(plan)
    if not res.ok:
        raise ValueError("fix plan errors before arranging stems")
    bpb = res.beats_per_bar
    beds = [c for c in res.clips if c.stem in ("instrumental", "mix") and (bed_clip_id is None or c.id == bed_clip_id)]
    if not beds:
        raise ValueError("no instrumental/mix bed clip to arrange")
    bed = beds[0]
    missing = {"drums", "bass", "other"} - set(library.available_stems(bed.track))
    if missing:
        raise ValueError(f"{bed.track} needs {', '.join(sorted(missing))} stems: glass-harbor track separate "
                         f"{bed.track} --stems drums,bass,other")
    spec = plan["clips"][bed.index]
    beats = int(round(bed.out_end_beat - bed.anchor_beat))
    other = [0.0] * beats
    bass = [0.0] * beats
    hooks, verses = [], []
    # A drop always hits with the full beat: a vocal entering on an impact is treated like a hook.
    impacts = [c.anchor_beat for c in res.clips if c.spec.get("generate") == "impact"]
    for clip in res.clips:
        if clip.stem != "vocals" or clip.chop is not None:
            continue
        span = (clip.out_start_beat - bed.anchor_beat, clip.out_end_beat - bed.anchor_beat)
        on_drop = any(abs(clip.anchor_beat - at) <= 1 for at in impacts)
        (hooks if clip.spec.get("chain") == "hook" or on_drop else verses).append(span)
    for a, b in verses:
        for k in range(max(0, int(np.floor(a))), min(beats, int(np.ceil(b)))):
            other[k] = verse_other_db
    for a, _ in hooks:
        start = int(round(a))
        for k in range(max(0, start - int(drums_only_bars * bpb)), min(beats, start)):
            if not any(h0 <= k < h1 for h0, h1 in hooks):
                other[k] = bass[k] = -60.0
    clips = []
    for stem in ("drums", "bass", "other"):
        clip = json.loads(json.dumps(spec))
        clip["id"] = f"{spec.get('id', 'bed')}-{stem}"
        clip["stem"] = stem
        clip.pop("duck", None)
        automation = clip.setdefault("automation", {})
        if stem == "bass" and any(bass):
            automation["arrange_db"] = _levels_to_points(bass, bpb)
        if stem == "drums":
            clip["punch"] = {"attack_db": 3.0, "parallel": 0.2}
            if drum_clip_db:
                clip["clip_db"] = drum_clip_db  # loud genres: clip the drums so the master gets club-loud
        if stem == "other":
            # Width contrast: narrower under verses, wider on hooks and drops.
            widths = [0.7 if level < 0 else 1.25 for level in other]
            automation["width"] = _levels_to_points(widths, bpb)
        if stem == "drums" and duck_drums_db:
            # Hats, shakers, and snare share the vocal's presence range (percussive house especially); duck only
            # where they actually compete, so the kick and the groove keep their punch.
            clip["duck"] = {"under": "vocals", "db": duck_drums_db}
        if stem == "other":
            if any(other):
                automation["arrange_db"] = _levels_to_points(other, bpb)
            clip["duck"] = spec.get("duck") or {"under": "vocals", "db": float(taste_default("duck_db"))}
            if pump:
                clip["pump"] = pump
        if not automation:
            clip.pop("automation")
        clips.append(clip)
    plan["clips"][bed.index:bed.index + 1] = clips
    plan.setdefault("notes", []).append(
        f"stem arrangement on {spec.get('id', 'bed')}: verses over drums + bass (melodic layer {verse_other_db:g} dB), "
        f"full beat under hooks, {drums_only_bars:g} drums-only bar before each hook"
        + (", melodic layer pumps on the beat" if pump else ""))
    return plan


def _source_times(clip, out_beats: list[float]) -> list[float] | None:
    """Source times of a clip at the given output beats (one loop period folded in), or None if outside it."""
    span = clip.src_beats * clip.out_beats_per_src_beat
    out = []
    for beat in out_beats:
        k = (beat - clip.out_start_beat) / clip.out_beats_per_src_beat
        if not -1e-6 <= beat - clip.out_start_beat <= span * clip.loop + 1e-6:
            return None
        k = k % clip.src_beats if k < clip.src_beats * clip.loop - 1e-6 else clip.src_beats
        out.append(float(np.interp(k, np.arange(clip.src_beats + 1), clip.src_beat_times)))
    return out


def follow_vocal_roots(plan: dict[str, Any], *, clip_ids: list[str] | None = None, min_rate: float = 0.08
                       ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Decide where the bed's bass should follow the vocal's chords and set ``follow_roots`` on its bass clips.

    For each vocal clip, compares the sung notes against the bass the vocal was written over and against the bed's
    bass under it. A clip qualifies when at least ``min_rate`` of its sung notes sit a half-step or tritone off the
    bed's bass and clearly more than over its own bass. ``clip_ids`` forces the choice. Returns (plan, per-clip
    findings)."""
    from glass_harbor import bassline
    from glass_harbor.plan import resolve

    res = resolve(plan)
    if not res.ok:
        raise ValueError("fix plan errors before following the vocal's chords")
    vocals = [c for c in res.clips if c.stem == "vocals" and c.chop is None and c.loop == 1]
    basses = [c for c in res.clips if c.stem == "bass"]
    beds = basses or [c for c in res.clips if c.stem in ("instrumental", "mix")]
    sources: dict[str, tuple[np.ndarray, str]] = {}

    def low_end(track: str) -> tuple[np.ndarray, str]:
        if track not in sources:
            sources[track] = bassline.source_bass(track)
        return sources[track]

    findings = []
    for v in vocals:
        if not beds:
            break
        windows = bassline.half_beats(v.src_beat_times)
        vocal_audio = library.load_audio(v.track, "vocals")
        sung = bassline.sung(vocal_audio, windows)
        own_audio, own_stem = low_end(v.track)
        own = [None if n is None else n + v.semitones for n in bassline.roots(own_audio, windows)]
        out_beats = [v.out_start_beat + i * v.out_beats_per_src_beat for i in range(v.src_beats + 1)]
        bed = next((b for b in beds if _source_times(b, out_beats) is not None), None)
        if bed is None:
            continue
        bed_audio, _ = low_end(bed.track)
        bed_notes = [None if n is None else n + bed.semitones
                     for n in bassline.roots(bed_audio, bassline.half_beats(_source_times(bed, out_beats)))]
        own_rate, frames = bassline.clash_rate(sung, own)
        bed_rate, _ = bassline.clash_rate(sung, bed_notes)
        chosen = (v.id in clip_ids) if clip_ids is not None else (
            frames >= 30 and bed_rate >= min_rate and bed_rate - own_rate >= 0.05)
        findings.append({"clip": v.id, "sung_frames": frames, "over_own_bass_pct": round(100 * own_rate, 1),
                         "over_bed_bass_pct": round(100 * bed_rate, 1), "follow": chosen,
                         "own_roots": bassline.describe(own[:16]), "bed_roots": bassline.describe(bed_notes[:16]),
                         "own_source": f"{v.track}/{own_stem}", "bed_clip": bed.id})
    ids = [f["clip"] for f in findings if f["follow"]]
    covered = set()
    for b in basses:
        overlapping = [i for i in ids if any(c.id == i and c.out_start_beat < b.out_end_beat
                                             and c.out_end_beat > b.out_start_beat for c in vocals)]
        spec = plan["clips"][b.index]
        if overlapping:
            spec["follow_roots"] = overlapping
            covered.update(overlapping)
        else:
            spec.pop("follow_roots", None)
    notes = plan.setdefault("notes", [])
    notes[:] = [n for n in notes if not n.startswith("bass follows the vocal")]
    if covered:
        notes.append(f"bass follows the vocal's original chords under {', '.join(sorted(covered))} (their sung notes "
                     "sat a half-step off the beat's bassline)")
    missing = sorted(set(ids) - covered)
    if missing:
        notes.append(f"{', '.join(missing)} clash with the beat's bass but the bed has no bass stem clip; run "
                     "glass-harbor mix arrange so the bass can follow the vocal")
    return plan, findings


# ---------------------------------------------------------------- DJ edges, fills, edits


def _lane_override(automation: dict[str, Any], lane: str, start: float, end: float, value: float) -> None:
    """Hold ``lane`` at ``value`` over [start, end) bar offsets, restoring what was there on either side."""
    from glass_harbor.plan import AUTOMATABLE, automation_value

    points = automation.get(lane)
    before = automation_value(points, start, AUTOMATABLE[lane])
    after = automation_value(points, end, AUTOMATABLE[lane])
    kept = [p for p in (points or []) if p[0] < start - 0.004 or p[0] > end]
    new = [[round(start - 0.004, 4), before], [round(start, 4), value], [round(end - 0.004, 4), value],
           [round(end, 4), after]]
    automation[lane] = sorted(kept + new, key=lambda p: p[0])


def _bed_clips(res) -> list:
    return [c for c in res.clips if c.stem not in ("vocals", "fx") and c.chop is None]


def add_dj_edges(plan: dict[str, Any], *, intro_bars: int = 16, outro_bars: int = 16) -> dict[str, Any]:
    """DJ-friendly edit: a beat-only intro (drums, then bass halfway) and outro (bass out halfway) so a DJ can
    mix the edit in and out. Everything else moves later by ``intro_bars``; end-of-bed fades are replaced by the
    outro."""
    from glass_harbor.plan import resolve

    res = resolve(plan)
    if not res.ok:
        raise ValueError("fix plan errors before adding DJ edges")
    beds = _bed_clips(res)
    if not beds:
        raise ValueError("no beat clip to build DJ edges from")
    bed = beds[0]
    analysis = res.analyses[bed.track]
    groove = (analysis.get("drops") or [None])[0] or next(
        (s["start_bar"] for s in analysis.get("sections", []) if s.get("energy") == "high"), 1)
    stems = library.available_stems(bed.track)
    parts = [("drums", 0.0), ("bass", 0.5)] if {"drums", "bass"} <= set(stems) else [(bed.stem, 0.0)]
    loop_len = 8 if intro_bars % 8 == 0 and outro_bars % 8 == 0 else 4

    last_bar = max(1 + c.out_end_beat / res.beats_per_bar for c in res.clips if c.stem != "fx")
    for clip in plan["clips"]:
        clip["at_bar"] = clip["at_bar"] + intro_bars
        gains = (clip.get("automation") or {}).get("gain_db")
        if gains and clip.get("stem") not in ("vocals",) and "generate" not in clip and gains[-1][1] <= -30:
            fade_start = max(p[0] for p in gains if p[1] > -30) if any(p[1] > -30 for p in gains) else 0
            clip["automation"]["gain_db"] = [p for p in gains if p[0] <= fade_start]
    if "tempo" in plan:
        for point in plan["tempo"][1:]:
            point["bar"] += intro_bars
    for edit in plan.get("edits", []):
        edit["at_bar"] += intro_bars

    source = bed.source
    edges = []
    for stem, enter in parts:
        if intro_bars:
            start = int(intro_bars * enter)
            edges.append({"id": f"intro-{stem}", "source": source, "stem": stem, "from_bar": groove,
                          "bars": loop_len, "loop": max(1, (intro_bars - start) // loop_len), "at_bar": 1 + start})
        if outro_bars:
            length = outro_bars if enter == 0 else outro_bars // 2
            edges.append({"id": f"outro-{stem}", "source": source, "stem": stem, "from_bar": groove,
                          "bars": loop_len, "loop": max(1, length // loop_len),
                          "at_bar": round(last_bar + intro_bars, 4)})
    plan["clips"] = edges[: len(parts)] + plan["clips"] + edges[len(parts):] if intro_bars else plan["clips"] + edges
    notes = plan.setdefault("notes", [])
    if intro_bars and notes:
        notes.append(f"bar numbers in the notes above (and in fill ids like riser-92) are from before the DJ intro: "
                     f"add {intro_bars} to find them in this plan")
    notes.append(f"DJ edges: {intro_bars}-bar beat intro, {outro_bars}-bar beat outro "
                 f"(looped from bar {groove} of {bed.track})")
    return plan


def _first_word(res, clip, lyrics: dict[str, Any]) -> tuple[str, int] | None:
    from glass_harbor.lyrics import _normalize

    start = clip.src_beat_times[0]
    words = [w for seg in lyrics["segments"] for w in seg["words"]]
    for i, word in enumerate(words):
        if word["start"] >= start - 0.05 and _normalize(word["word"]):
            text = _normalize(word["word"])
            occurrence = sum(1 for w in words[: i + 1] if _normalize(w["word"]) == text)
            return text, occurrence
    return None


FILL_GAP_BARS = 16  # a crash or swell marks a new section; on every short chant it turns into noise


def add_fills(plan: dict[str, Any], *, crashes: bool = True, swells: bool = True) -> dict[str, Any]:
    """Crash on drops and on hook entries (at least ``FILL_GAP_BARS`` apart), and a one-bar reverse swell of the
    hook's first word leading into each marked hook."""
    from glass_harbor.lyrics import load_lyrics
    from glass_harbor.plan import resolve

    res = resolve(plan)
    if not res.ok:
        raise ValueError("fix plan errors before adding fills")
    beds = _bed_clips(res)
    drum_source = beds[0].source if beds else None
    existing = {(c.get("generate"), c.get("at_bar")) for c in plan["clips"]}
    added = []
    hooks = [c for c in res.clips if c.stem == "vocals" and c.chop is None and c.spec.get("chain") == "hook"]
    marked = sorted({c.spec["at_bar"] for c in res.clips if c.spec.get("generate") == "impact"})
    for hook in sorted(hooks, key=lambda c: c.spec["at_bar"]):
        if all(abs(hook.spec["at_bar"] - bar) >= FILL_GAP_BARS for bar in marked):
            marked.append(hook.spec["at_bar"])
    hooks = [c for c in hooks if c.spec["at_bar"] in marked]
    targets = sorted(set(marked))
    for bar in targets:
        if crashes and drum_source and ("crash", bar) not in existing:
            plan["clips"].append({"id": f"crash-{bar:g}", "generate": "crash", "source": drum_source,
                                  "at_bar": bar, "bars": 2, "gain_db": -8, "duck": FILL_DUCK})
            added.append(f"crash {bar:g}")
    for hook in hooks:
        lyrics = load_lyrics(hook.track)
        found = _first_word(res, hook, lyrics) if lyrics else None
        bar = hook.spec["at_bar"] - 1
        if swells and found and len(found[0]) >= 2 and bar >= 1 and ("reverse_swell", bar) not in existing:
            plan["clips"].append({"id": f"swell-{hook.spec['at_bar']:g}", "generate": "reverse_swell",
                                  "source": hook.source, "word": found[0], "occurrence": found[1], "at_bar": bar,
                                  "bars": 1, "gain_db": -8, "automation": {"highpass_hz": [[0, 250]]},
                                  "duck": FILL_DUCK})
            added.append(f"swell into {hook.spec['at_bar']:g}")
    plan.setdefault("notes", []).append("fills: " + (", ".join(added) or "none needed"))
    return plan


def add_edit(plan: dict[str, Any], kind: str, at_bar: float, *, beats: float = 1.0, word: str | None = None,
             occurrence: int = 1, pattern: str = "j-j-jjjj", source: str | None = None,
             semitones: int = 1) -> dict[str, Any]:
    """Punchline edits: ``mute`` (the beat drops out under a line), ``stutter`` (a word repeated on 16ths, the
    vocal muted under it), ``tape_stop`` (the whole mix brakes to a stop), ``lift`` (clips from ``at_bar`` on go up
    ``semitones``)."""
    from glass_harbor.plan import resolve

    res = resolve(plan)
    if not res.ok:
        raise ValueError("fix plan errors before adding edits")
    bpb = res.beats_per_bar
    start_beat, end_beat = (at_bar - 1) * bpb, (at_bar - 1) * bpb + beats
    if kind == "tape_stop":
        plan.setdefault("edits", []).append({"type": "tape_stop", "at_bar": at_bar, "beats": beats})
    elif kind in ("mute", "stutter"):
        if kind == "stutter":
            vox = source or next(c.source for c in res.clips if c.stem == "vocals")
            if not word:
                raise ValueError("stutter needs --word")
            steps = len(pattern)
            beats = steps * 0.25
            end_beat = start_beat + beats
            plan["clips"].append({"id": f"stutter-{at_bar:g}", "source": vox, "stem": "vocals", "at_bar": at_bar,
                                  "bars": beats / bpb, "chop": {"slices": {"j": {"word": word, "occurrence": occurrence}},
                                                                 "pattern": pattern}})
        for clip in res.clips:
            playing = clip.out_start_beat < end_beat and clip.out_end_beat > start_beat
            silence = (kind == "mute" and clip.stem not in ("vocals", "fx")) or (
                kind == "stutter" and clip.stem == "vocals" and clip.chop is None)
            if playing and silence:
                spec = plan["clips"][clip.index]
                offset = (start_beat - clip.anchor_beat) / bpb
                _lane_override(spec.setdefault("automation", {}), "arrange_db", offset, offset + beats / bpb, -60.0)
    elif kind == "lift":
        spanning = []
        for clip in res.clips:
            if clip.stem == "fx":
                continue
            if clip.anchor_beat >= start_beat:
                spec = plan["clips"][clip.index]
                spec["semitones"] = int(spec.get("semitones", 0)) + semitones
            elif clip.out_end_beat > start_beat:
                spanning.append(clip.id)
        if spanning:
            raise ValueError(f"split these clips at bar {at_bar:g} first: {', '.join(spanning)}")
    else:
        raise ValueError("edit must be mute, stutter, tape_stop, or lift")
    plan.setdefault("notes", []).append(f"edit: {kind} at bar {at_bar:g}")
    return plan


# ---------------------------------------------------------------- structure-aware mashup drafts

TEASE = ["h---j-----------", "........b-------", "h---j-----------", "........b---b---",
         "h---j-----------", "........b-------", "j-------j-------", "j---j---j-j-j-j-"]
BUILD = ["j---j---j---j---", "b---b---j---j---", "j---j---j---j---", "j-j-j-j-j-j-j-j-",
         "j-j-j-j-k-k-k-k-", "k-k-k-k-l-l-l-l-", "jjjjkkkkllllmmmm", "j-----------...."]


def _vocal_material(vox: dict[str, Any], lyrics: dict[str, Any] | None, title: str) -> dict[str, Any] | None:
    """Chorus blocks (from the most repeated line), 8-bar verse chunks, a title line, and chop words."""
    from glass_harbor.grid import Grid
    from glass_harbor.lyrics import _normalize, hooks

    if not lyrics:
        return None
    grid = Grid.from_dict(vox["grid"])
    found = [h for h in hooks(lyrics, grid) if h["occurrences"] and len(h["text"].split()) >= 3]
    if not found:
        return None
    starts = sorted(int(math.floor(o["start_bar"])) for o in found[0]["occurrences"])
    choruses = []
    for i, start in enumerate(starts):
        nxt = starts[i + 1] if i + 1 < len(starts) else grid.bar_count + 1
        length = 16 if nxt - start >= 16 else 8
        if start + length <= grid.bar_count + 1 and all(abs(start - c[0]) >= 8 for c in choruses):
            choruses.append((start, length))
    covered = {b for start, length in choruses for b in range(start, start + length)}
    verses = []
    for phrase in vox.get("stems", {}).get("vocals", {}).get("phrases", []):
        bar = phrase["start_bar"]
        end = phrase["start_bar"] + phrase["bars"]
        while bar + 8 <= end + 2 and bar + 8 <= grid.bar_count + 1:
            if not covered & set(range(bar, bar + 8)) and all(abs(bar - v) >= 8 for v in verses):
                verses.append(bar)
            bar += 8
    verses.sort()
    title_words = [w for w in (_normalize(t) for t in title.split()) if len(w) >= 4]
    line = None
    for seg in lyrics["segments"]:
        words = {_normalize(w["word"]) for w in seg["words"]}
        span = grid.bar_at_time(seg["end"]) - grid.bar_at_time(seg["start"])
        if title_words and words & set(title_words) and span <= 3.0 and (line is None or span < line[2]):
            line = (grid.bar_at_time(seg["start"]), grid.bar_at_time(seg["end"]), span)
    counts: dict[str, int] = {}
    for seg in lyrics["segments"]:
        for w in seg["words"]:
            text = _normalize(w["word"])
            if 3 <= len(text) <= 7:
                counts[text] = counts.get(text, 0) + 1
    chop_word = next((w for w in title_words if counts.get(w)), None) or max(counts, key=counts.get, default=None)
    filler = next((w for w, _ in sorted(counts.items(), key=lambda kv: -kv[1]) if w != chop_word), None)
    first_hook_word = _normalize(found[0]["text"].split()[0]) if found else None
    return {"choruses": choruses, "verses": verses, "title_line": line, "chop_word": chop_word,
            "filler_word": filler or chop_word, "hook_word": first_hook_word}


def smart_arrangement(vocals: str, bed: str, vox: dict[str, Any], beat: dict[str, Any], ratio: float,
                      title: str) -> tuple[list[dict[str, Any]], list[tuple[int, float]], list[str]] | None:
    """Place vocal material on the beat's structure. Returns (vocal clips, drop bars to build, notes) or None
    when there is not enough structure to work with (the caller falls back to back-to-back placement)."""
    from glass_harbor.lyrics import load_lyrics

    material = _vocal_material(vox, load_lyrics(vocals), title)
    levels = beat.get("bar_db") or []
    if material is None or not material["choruses"] or len(levels) < 32 or ratio != 1:
        return None
    bars = len(levels)
    median = float(np.median(levels))
    full = [v >= median - 2.5 for v in levels]
    low = [v <= median - 4.0 for v in levels]
    silent = [v <= median - 12.0 for v in levels]

    def share(mask: list[bool], start: int, length: int) -> float:
        window = mask[start - 1: start - 1 + length]
        return sum(window) / max(1, len(window))

    drops = [d for d in beat.get("drops", []) if d >= 9]
    clips: list[dict[str, Any]] = []
    notes: list[str] = []
    builds: list[tuple[int, float]] = []
    chorus_i = verse_i = chops_i = 0
    last_hook = False
    last_chops = -99
    cursor = 9
    outro = 8
    handled: set[int] = set()  # each drop is arranged once (a hook can end exactly on the next drop)
    while cursor + 8 <= bars + 1 - outro:
        next_drop = next((d for d in drops if d >= cursor and d not in handled), None)
        if next_drop is not None and next_drop - cursor < 8:
            handled.add(next_drop)
            gap = next_drop - cursor
            line = material["title_line"]
            spotlight = 0
            quiet_run = 0  # silent bars right before the drop
            while quiet_run < gap and silent[next_drop - 2 - quiet_run]:
                quiet_run += 1
            if quiet_run and line and math.ceil(line[1]) - math.ceil(line[0]) <= quiet_run:
                from_bar = math.ceil(line[0])
                pre = math.ceil((from_bar - line[0]) * 4)
                length = max(1, math.ceil(line[1]) - from_bar)
                clips.append({"id": "title-break", "source": "vox", "stem": "vocals", "from_bar": from_bar,
                              "bars": length, "at_bar": next_drop - length, **({"pre_beats": pre} if pre else {}),
                              "fx": {"reverb": {"mix": 0.15, "room": 0.5}}})
                notes.append(f"title line a cappella in the break before the bar-{next_drop} drop")
                spotlight = length + pre / 4
            cursor = next_drop
            if not last_hook and cursor + 16 <= bars + 1:
                start, length = material["choruses"][chorus_i % len(material["choruses"])]
                clips.append({"id": f"hook{chorus_i + 1}", "source": "vox", "stem": "vocals", "from_bar": start,
                              "bars": length, "at_bar": cursor, "chain": "hook"})
                builds.append((cursor, spotlight))
                chorus_i += 1
                cursor += length
                last_hook = True
            continue
        straddles = next_drop is not None and cursor < next_drop < cursor + 16
        if not last_hook and not straddles and share(full, cursor, 16) >= 0.75 and cursor + 16 <= bars + 1 - outro + 8:
            start, length = material["choruses"][chorus_i % len(material["choruses"])]
            clips.append({"id": f"hook{chorus_i + 1}", "source": "vox", "stem": "vocals", "from_bar": start,
                          "bars": length, "at_bar": cursor, "chain": "hook"})
            chorus_i += 1
            cursor += length
            last_hook = True
        elif share(low, cursor, 8) >= 0.6 and material["chop_word"] and cursor - last_chops >= 16:
            build = next_drop is not None and next_drop - (cursor + 8) < 8
            slices = {"j": {"word": material["chop_word"], "occurrence": 1},
                      "b": {"word": material["filler_word"], "occurrence": 1},
                      "h": {"word": material["hook_word"] or material["chop_word"], "occurrence": 1},
                      "k": {"word": material["chop_word"], "occurrence": 1, "semitones": 5},
                      "l": {"word": material["chop_word"], "occurrence": 1, "semitones": 7},
                      "m": {"word": material["chop_word"], "occurrence": 1, "semitones": 12}}
            chops_i += 1
            clips.append({"id": f"chops{chops_i}", "source": "vox", "stem": "vocals",
                          "at_bar": cursor, "bars": 8, "gain_db": 2.0,
                          "chop": {"slices": slices, "pattern": BUILD if build else TEASE},
                          "automation": {"highpass_hz": [[0, 200]]},
                          "fx": {"echo": {"beats": 0.75, "feedback": 0.3, "mix": 0.2}}})
            last_chops = cursor
            cursor += 8
            last_hook = False
        elif verse_i < len(material["verses"]):
            clips.append({"id": f"verse{verse_i + 1}", "source": "vox", "stem": "vocals",
                          "from_bar": material["verses"][verse_i], "bars": 8, "at_bar": cursor})
            verse_i += 1
            cursor += 8
            last_hook = False
        else:
            cursor += 8  # let the beat play
            last_hook = False
    if chorus_i == 0:
        return None
    for clip in clips:
        if clip.get("stem") == "vocals" and "chop" not in clip:
            clip.setdefault("automation", {"highpass_hz": [[0, float(taste_default("vocal_highpass_hz"))]]})
    # Drop the chop slices whose word is missing (e.g. no filler word) so the plan validates.
    for clip in clips:
        if "chop" in clip:
            clip["chop"]["slices"] = {k: v for k, v in clip["chop"]["slices"].items() if v["word"]}
    notes.append(f"structure-aware draft: {chorus_i} chorus(es) on the beat's drops/full sections, {verse_i} verse "
                 f"chunk(s), chops in low-energy stretches")
    return clips, builds, notes
