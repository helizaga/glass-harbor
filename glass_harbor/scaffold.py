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

    hook_starts = [o["start_bar"] for h in vox.get("hooks", []) for o in h.get("occurrences", [])]
    for clip in clips:
        if any(clip["from_bar"] <= bar < clip["from_bar"] + clip["bars"] for bar in hook_starts):
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
    if edm:
        plan["groove"] = {"pump_fx": {"db": 5.0, "release": 0.6}}
    if {"drums", "bass", "other"} <= set(library.available_stems(bed)) and len(bed_clips) == 1:
        plan = arrange_bed_stems(plan, pump={"db": 3.0, "release": 0.5} if edm else None)
    plan = add_fills(plan)
    edges = int(taste_default("dj_edge_bars"))
    if edges:
        plan = add_dj_edges(plan, intro_bars=edges, outro_bars=edges)
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
        f"{', ' + str(riser) + ' riser' if riser else ''}{', snare roll' if roll else ''}{', impact' if impact else ''}, "
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
                      duck_drums_db: float = 4.0) -> dict[str, Any]:
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
    plan.setdefault("notes", []).append(f"DJ edges: {intro_bars}-bar beat intro, {outro_bars}-bar beat outro "
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


def add_fills(plan: dict[str, Any], *, crashes: bool = True, swells: bool = True) -> dict[str, Any]:
    """Crash on every hook entry and drop, and a one-bar reverse swell of the hook's first word leading into it."""
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
    targets = sorted({c.spec["at_bar"] for c in hooks} | {c.spec["at_bar"] for c in res.clips
                                                          if c.spec.get("generate") == "impact"})
    for bar in targets:
        if crashes and drum_source and ("crash", bar) not in existing:
            plan["clips"].append({"id": f"crash-{bar:g}", "generate": "crash", "source": drum_source,
                                  "at_bar": bar, "bars": 2, "gain_db": -8, "duck": FILL_DUCK})
            added.append(f"crash {bar:g}")
    for hook in hooks:
        lyrics = load_lyrics(hook.track)
        found = _first_word(res, hook, lyrics) if lyrics else None
        bar = hook.spec["at_bar"] - 1
        if swells and found and bar >= 1 and ("reverse_swell", bar) not in existing:
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
