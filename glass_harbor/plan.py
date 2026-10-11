"""Mix plans: the agent-authored ``mixes/<slug>/<slug>.mix.json`` contract, validation, and resolution to time.

A plan places *clips* (a bar range of one stem of one source track) on an output bar grid at a single tempo.
Everything is expressed in bars so the agent reasons musically; the renderer turns bars into seconds using each
track's beat grid, which is what makes clips land on the beat after time-stretching.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from glass_harbor import library
from glass_harbor.grid import Grid, shift_downbeat
from glass_harbor.keys import Key, camelot_distance
from glass_harbor.tempo import TempoMap, validate_tempo

KINDS = ("mashup", "transition", "set")
STEMS = ("mix",) + library.STEM_NAMES
AUTOMATABLE = {
    "gain_db": 0.0,
    "arrange_db": 0.0,  # a second gain lane for stem arrangement (mutes/strips), independent of fades
    "highpass_hz": 20.0,
    "lowpass_hz": 20000.0,
    "eq_low_db": 0.0,
    "eq_mid_db": 0.0,
    "eq_high_db": 0.0,
}
FREQUENCY_PARAMS = {"highpass_hz", "lowpass_hz"}
BASS_STEMS = {"mix", "instrumental", "bass"}
VOCAL_STEMS = {"mix", "vocals"}
HARMONIC_STEMS = {"mix", "instrumental", "vocals", "bass", "other"}
KILL_DB = -15.0


@dataclass
class Issue:
    level: str  # "error" | "warning" | "info"
    where: str
    message: str

    def to_dict(self) -> dict:
        return {"level": self.level, "where": self.where, "message": self.message}


@dataclass
class ResolvedClip:
    index: int
    id: str
    source: str
    track: str
    stem: str
    spec: dict[str, Any]
    src_beat_times: list[float]  # source times of each beat boundary (len = beats + 1)
    out_start_beat: float  # output beat index (0 = bar 1 beat 1) of the first boundary (includes pre_beats)
    anchor_beat: float  # output beat of at_bar; automation offsets are measured from here
    out_beats_per_src_beat: float
    loop: int
    semitones: int
    gain_db: float
    stretch_pct: float
    chop: dict[str, Any] | None = None  # resolved chop spec (slices with source times, steps)
    length_beats: float | None = None  # explicit output length (chop clips)

    @property
    def src_beats(self) -> int:
        return len(self.src_beat_times) - 1

    @property
    def out_beats(self) -> float:
        if self.length_beats is not None:
            return self.length_beats
        return self.src_beats * self.out_beats_per_src_beat * self.loop

    @property
    def out_end_beat(self) -> float:
        return self.out_start_beat + self.out_beats


@dataclass
class Resolution:
    plan: dict[str, Any]
    issues: list[Issue] = field(default_factory=list)
    clips: list[ResolvedClip] = field(default_factory=list)
    grids: dict[str, Grid] = field(default_factory=dict)
    analyses: dict[str, dict] = field(default_factory=dict)
    tempo: TempoMap | None = None
    beats_per_bar: int = 4

    @property
    def ok(self) -> bool:
        return not any(issue.level == "error" for issue in self.issues)

    def add(self, level: str, where: str, message: str) -> None:
        self.issues.append(Issue(level, where, message))


def load_plan(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: invalid JSON ({error})") from error


def save_plan(path: Path, plan: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=2) + "\n")


def automation_value(points: list[list[float]] | None, offset_bars: float, default: float, *,
                     log_scale: bool = False) -> float:
    if not points:
        return default
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    if offset_bars <= xs[0]:
        return ys[0]
    if offset_bars >= xs[-1]:
        return ys[-1]
    for (x0, y0), (x1, y1) in zip(zip(xs, ys), zip(xs[1:], ys[1:])):
        if x0 <= offset_bars <= x1:
            t = 0.0 if x1 == x0 else (offset_bars - x0) / (x1 - x0)
            if log_scale and y0 > 0 and y1 > 0:
                return math.exp(math.log(y0) + t * (math.log(y1) - math.log(y0)))
            return y0 + t * (y1 - y0)
    return ys[-1]


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _check_automation(res: Resolution, where: str, automation: Any) -> None:
    if automation is None:
        return
    if not isinstance(automation, dict):
        res.add("error", where, "automation must be an object of parameter -> [[bar_offset, value], ...]")
        return
    for name, points in automation.items():
        if name not in AUTOMATABLE:
            res.add("error", where, f"unknown automation parameter {name!r} (allowed: {', '.join(AUTOMATABLE)})")
            continue
        if not isinstance(points, list) or not points or not all(
            isinstance(p, list) and len(p) == 2 and _number(p[0]) and _number(p[1]) for p in points
        ):
            res.add("error", where, f"automation {name} must be a non-empty list of [bar_offset, value] pairs")
            continue
        offsets = [p[0] for p in points]
        if offsets != sorted(offsets):
            res.add("error", where, f"automation {name} bar offsets must be ascending")
        if name in FREQUENCY_PARAMS and any(not 20 <= p[1] <= 20000 for p in points):
            res.add("error", where, f"automation {name} values must be between 20 and 20000 Hz")


def _check_fx(res: Resolution, where: str, fx: Any) -> None:
    if fx is None:
        return
    if not isinstance(fx, dict):
        res.add("error", where, "fx must be an object")
        return
    allowed = {"reverb": {"mix", "room"}, "echo": {"beats", "feedback", "mix"}}
    for name, params in fx.items():
        if name not in allowed:
            res.add("error", where, f"unknown fx {name!r} (allowed: {', '.join(allowed)})")
            continue
        if not isinstance(params, dict) or set(params) - allowed[name]:
            res.add("error", where, f"fx {name} accepts only {', '.join(sorted(allowed[name]))}")
            continue
        for key in ("mix", "room", "feedback"):
            if key in params and not (_number(params[key]) and 0 <= params[key] <= 1):
                res.add("error", where, f"fx {name}.{key} must be between 0 and 1")
        if "beats" in params and not (_number(params["beats"]) and 0 < params["beats"] <= 4):
            res.add("error", where, f"fx {name}.beats must be in (0, 4]")


def _check_vocal_options(res: Resolution, where: str, clip: dict[str, Any]) -> None:
    from glass_harbor.vocals import CHAINS

    if "chain" in clip and clip["chain"] not in CHAINS:
        res.add("error", where, f"chain must be one of {', '.join(CHAINS)}")
    for flag in ("word_safe", "ride"):
        if flag in clip and not isinstance(clip[flag], bool):
            res.add("error", where, f"{flag} must be true or false")


def _check_duck(res: Resolution, where: str, duck: Any) -> None:
    if duck is None:
        return
    if not isinstance(duck, dict):
        res.add("error", where, "duck must be an object like {\"under\": \"vocals\", \"db\": 3}")
        return
    under = duck.get("under", "vocals")
    if not (under == "vocals" or (isinstance(under, list) and all(isinstance(u, str) for u in under))):
        res.add("error", where, "duck.under must be \"vocals\" or a list of clip ids")
    for key in ("db", "level_db"):
        if key in duck and not (_number(duck[key]) and 0 <= duck[key] <= 12):
            res.add("error", where, f"duck.{key} must be between 0 and 12 dB")
    if duck.get("mode", "spectral") not in ("spectral", "band"):
        res.add("error", where, "duck.mode must be spectral or band")


def _check_pump(res: Resolution, where: str, pump: Any) -> None:
    if pump is None:
        return
    if not isinstance(pump, dict) or not (_number(pump.get("db", 4)) and 0 < pump.get("db", 4) <= 12) or not (
            _number(pump.get("release", 0.5)) and 0.1 <= pump.get("release", 0.5) <= 1.0):
        res.add("error", where, "pump must be {db: 0-12, release: 0.1-1.0 beats}")


def _active_value(clip: ResolvedClip, param: str, out_beat: float, bpb: int) -> float:
    offset_bars = (out_beat - clip.anchor_beat) / bpb
    return automation_value((clip.spec.get("automation") or {}).get(param), offset_bars, AUTOMATABLE[param],
                            log_scale=param in FREQUENCY_PARAMS)


def _bass_killed(clip: ResolvedClip, out_beat: float, bpb: int) -> bool:
    gain = clip.gain_db + _active_value(clip, "gain_db", out_beat, bpb) + _active_value(clip, "arrange_db", out_beat, bpb)
    return (
        _active_value(clip, "eq_low_db", out_beat, bpb) <= KILL_DB
        or _active_value(clip, "highpass_hz", out_beat, bpb) >= 150
        or gain <= -20
        or clip.stem not in BASS_STEMS
    )


def _vocal_active(res: Resolution, clip: ResolvedClip, out_beat: float, bpb: int) -> bool:
    if clip.stem not in VOCAL_STEMS:
        return False
    if (clip.spec.get("gain_db", 0) + _active_value(clip, "gain_db", out_beat, bpb)
            + _active_value(clip, "arrange_db", out_beat, bpb)) <= -20:
        return False
    if clip.chop is not None:
        return True
    analysis = res.analyses[clip.track]
    vocal_db = analysis.get("stems", {}).get("vocals", {}).get("bar_db")
    if not vocal_db:
        return True  # unknown: assume a full mix carries vocals
    grid = res.grids[clip.source]
    src_time = _src_time_at(clip, out_beat)
    bar = int(grid.bar_at_time(src_time)) - 1
    if not 0 <= bar < len(vocal_db):
        return False
    return vocal_db[bar] > max(-42.0, max(vocal_db) - 22.0)


def _src_time_at(clip: ResolvedClip, out_beat: float) -> float:
    rel = (out_beat - clip.out_start_beat) / clip.out_beats_per_src_beat
    rel %= clip.src_beats
    lower = int(rel)
    frac = rel - lower
    times = clip.src_beat_times
    upper = min(lower + 1, len(times) - 1)
    return times[lower] + frac * (times[upper] - times[lower])


def _ranges(bars: list[int]) -> str:
    if not bars:
        return ""
    spans = []
    start = prev = bars[0]
    for bar in bars[1:]:
        if bar != prev + 1:
            spans.append((start, prev))
            start = bar
        prev = bar
    spans.append((start, prev))
    return ", ".join(f"{a}" if a == b else f"{a}-{b}" for a, b in spans)


CHOP_REST = "."
CHOP_HOLD = "-"


def _chop_steps(pattern: Any) -> list[str] | None:
    bars = [pattern] if isinstance(pattern, str) else pattern
    if not isinstance(bars, list) or not bars or not all(isinstance(b, str) for b in bars):
        return None
    steps: list[str] = []
    for bar in bars:
        steps.extend(ch for ch in bar if ch not in " |")
    return steps or None


def _resolve_chop(res: Resolution, where: str, clip: dict[str, Any], source_name: str, source: dict[str, Any],
                  bpb: int) -> dict[str, Any] | None:
    """Validate a chop spec and resolve each slice to source times. Returns None on errors."""
    chop = clip["chop"]
    if not isinstance(chop, dict):
        res.add("error", where, "chop must be an object with slices and pattern")
        return None
    slices = chop.get("slices")
    if not isinstance(slices, dict) or not slices:
        res.add("error", where, "chop.slices must map single-character names to {bar, beat, beats}")
        return None
    grid = res.grids[source_name]
    resolved: dict[str, dict[str, Any]] = {}
    ok = True
    for name, spec in slices.items():
        here = f"{where} chop.slices.{name}"
        if len(name) != 1 or not name.isalnum():
            res.add("error", here, "slice names must be a single letter or digit")
            ok = False
            continue
        if isinstance(spec, dict) and isinstance(spec.get("word"), str):
            from glass_harbor.lyrics import find_word, load_lyrics

            lyrics = load_lyrics(source["track"])
            if lyrics is None:
                res.add("error", here, f"no lyrics yet (glass-harbor track lyrics {source['track']})")
                ok = False
                continue
            try:
                word = find_word(lyrics, spec["word"], int(spec.get("occurrence", 1)))
            except ValueError as error:
                res.add("error", here, str(error))
                ok = False
                continue
            semis = spec.get("semitones", 0)
            if not isinstance(semis, int) or abs(semis) > 12:
                res.add("error", here, "semitones must be an integer between -12 and 12")
                ok = False
                continue
            start = max(0.0, word["start"] - 0.01)
            end = word["end"] + float(spec.get("tail", 0.03))
            resolved[name] = {"start": start, "end": end, "beats": (end - start) / grid.period, "semitones": semis,
                              "reverse": bool(spec.get("reverse", False)), "word": word["word"]}
            continue
        if not isinstance(spec, dict) or not all(_number(spec.get(k)) for k in ("bar", "beat", "beats")):
            res.add("error", here, "slice needs numeric bar, beat (1-based, fractional ok), and beats (length),"
                    " or a word (+ occurrence) from the lyrics")
            ok = False
            continue
        if spec["bar"] < 1 or not 1 <= spec["beat"] < grid.beats_per_bar + 1 or not 0 < spec["beats"] <= 8:
            res.add("error", here, "bar >= 1, 1 <= beat < beats_per_bar + 1, 0 < beats <= 8")
            ok = False
            continue
        semis = spec.get("semitones", 0)
        if not isinstance(semis, int) or abs(semis) > 12:
            res.add("error", here, "semitones must be an integer between -12 and 12")
            ok = False
            continue
        start_index = grid.first_downbeat + (spec["bar"] - 1) * grid.beats_per_bar + (spec["beat"] - 1)
        start = grid.beat_time(start_index)
        end = grid.beat_time(start_index + spec["beats"])
        if start < 0 or end > grid.duration:
            res.add("error", here, "slice falls outside the track")
            ok = False
            continue
        resolved[name] = {"start": start, "end": end, "beats": float(spec["beats"]), "semitones": semis,
                          "reverse": bool(spec.get("reverse", False))}
    steps = _chop_steps(chop.get("pattern"))
    if steps is None:
        res.add("error", where, "chop.pattern must be a string (or list of strings, one per bar) of slice names,"
                " '-' (hold) and '.' (rest)")
        return None
    unknown = sorted({ch for ch in steps if ch not in (CHOP_REST, CHOP_HOLD) and ch not in slices})
    if unknown:
        res.add("error", where, f"pattern uses undefined slices: {', '.join(unknown)}")
        ok = False
    step = chop.get("step", 0.25)
    if not (_number(step) and 0.0625 <= step <= 4):
        res.add("error", where, "chop.step must be between 0.0625 and 4 beats (0.25 = 16th notes)")
        ok = False
    if not ok:
        return None
    return {"slices": resolved, "steps": steps, "step": float(step)}


def resolve(plan: dict[str, Any]) -> Resolution:
    res = Resolution(plan=plan)
    if not isinstance(plan, dict):
        res.add("error", "plan", "plan must be a JSON object")
        return res
    if plan.get("version", 1) != 1:
        res.add("error", "version", "only plan version 1 is supported")
    if plan.get("kind") not in KINDS:
        res.add("error", "kind", f"kind must be one of {', '.join(KINDS)}")
    tempo_errors = validate_tempo(plan)
    for message in tempo_errors:
        res.add("error", "tempo", message)
    bpb = plan.get("beats_per_bar", 4)
    if bpb not in (3, 4):
        res.add("error", "beats_per_bar", "beats_per_bar must be 3 or 4")
    if tempo_errors or bpb not in (3, 4):
        return res
    res.beats_per_bar = bpb
    res.tempo = TempoMap.from_plan(plan, bpb)

    sources = plan.get("sources")
    if not isinstance(sources, dict) or not sources:
        res.add("error", "sources", "sources must be a non-empty object of name -> {track, ...}")
        return res
    keys: dict[str, Key] = {}
    key_confidence: dict[str, float] = {}
    for name, source in sources.items():
        where = f"sources.{name}"
        if not isinstance(source, dict) or not isinstance(source.get("track"), str):
            res.add("error", where, "each source needs a track id")
            continue
        track = source["track"]
        try:
            analysis = library.load_analysis(track)
        except FileNotFoundError as error:
            res.add("error", where, str(error))
            continue
        semitones = source.get("semitones", 0)
        if not isinstance(semitones, int) or abs(semitones) > 12:
            res.add("error", where, "semitones must be an integer between -12 and 12")
            semitones = 0
        ratio = source.get("tempo_ratio", 1)
        if ratio not in (0.5, 1, 2):
            res.add("error", where, "tempo_ratio must be 0.5, 1, or 2 (output beats per source beat)")
        shift = source.get("downbeat_shift", 0)
        if not isinstance(shift, int):
            res.add("error", where, "downbeat_shift must be an integer number of beats")
            shift = 0
        grid = Grid.from_dict(analysis["grid"])
        res.grids[name] = shift_downbeat(grid, shift) if shift else grid
        res.analyses[track] = analysis
        keys[name] = Key(int(analysis["key"]["tonic"]), analysis["key"]["mode"]).shifted(semitones)
        key_confidence[name] = float(analysis["key"].get("confidence", 0.5))

    clips = plan.get("clips")
    if not isinstance(clips, list) or not clips:
        res.add("error", "clips", "clips must be a non-empty list")
        return res

    for index, clip in enumerate(clips):
        where = f"clips[{index}]" + (f" ({clip.get('id')})" if isinstance(clip, dict) and clip.get("id") else "")
        if not isinstance(clip, dict):
            res.add("error", where, "clip must be an object")
            continue
        if "generate" in clip:
            from glass_harbor.fx import TYPES as FX_TYPES

            kind = clip["generate"]
            if kind not in FX_TYPES:
                res.add("error", where, f"generate must be one of {', '.join(FX_TYPES)}")
                continue
            if not (_number(clip.get("bars")) and clip["bars"] > 0 and _number(clip.get("at_bar")) and clip["at_bar"] >= 1):
                res.add("error", where, "generated fx need bars > 0 and at_bar >= 1")
                continue
            _check_automation(res, where, clip.get("automation"))
            _check_fx(res, where, clip.get("fx"))
            anchor = (clip["at_bar"] - 1) * bpb
            res.clips.append(ResolvedClip(
                index=index, id=str(clip.get("id") or f"{kind}{index + 1}"), source="fx", track="", stem="fx",
                spec=clip, src_beat_times=[0.0, 1.0], out_start_beat=anchor, anchor_beat=anchor,
                out_beats_per_src_beat=1.0, loop=1, semitones=0, gain_db=float(clip.get("gain_db", 0)),
                stretch_pct=0.0, length_beats=float(clip["bars"]) * bpb,
            ))
            continue
        source_name = clip.get("source")
        if source_name not in sources:
            res.add("error", where, f"unknown source {source_name!r}")
            continue
        if source_name not in res.grids:
            continue
        source = sources[source_name]
        track = source["track"]
        stem = clip.get("stem", "mix")
        if stem not in STEMS:
            res.add("error", where, f"stem must be one of {', '.join(STEMS)}")
            continue
        if stem != "mix" and stem not in library.available_stems(track):
            res.add("error", where, f"track {track!r} has no {stem} stem yet (glass-harbor track separate {track})")
        if "chop" in clip:
            if not (_number(clip.get("bars")) and clip["bars"] > 0 and _number(clip.get("at_bar"))
                    and clip["at_bar"] >= 1):
                res.add("error", where, "chop clips need bars > 0 and at_bar >= 1")
                continue
            _check_automation(res, where, clip.get("automation"))
            _check_fx(res, where, clip.get("fx"))
            chop = _resolve_chop(res, where, clip, source_name, source, bpb)
            if chop is None:
                continue
            grid = res.grids[source_name]
            ratio = source.get("tempo_ratio", 1)
            anchor = (clip["at_bar"] - 1) * bpb
            out_bpm = res.tempo.bpm_at(anchor)
            stretch_pct = (out_bpm / (grid.bpm * ratio) - 1.0) * 100.0
            first = next(iter(chop["slices"].values()))
            res.clips.append(ResolvedClip(
                index=index,
                id=str(clip.get("id") or f"clip{index + 1}"),
                source=source_name,
                track=track,
                stem=stem,
                spec=clip,
                src_beat_times=[first["start"], first["end"]],
                out_start_beat=anchor,
                anchor_beat=anchor,
                out_beats_per_src_beat=float(ratio),
                loop=1,
                semitones=source.get("semitones", 0) if isinstance(source.get("semitones", 0), int) else 0,
                gain_db=float(source.get("gain_db", 0)) + float(clip.get("gain_db", 0)),
                stretch_pct=stretch_pct,
                chop=chop,
                length_beats=float(clip["bars"]) * bpb,
            ))
            continue
        for name in ("from_bar", "bars", "at_bar"):
            if not _number(clip.get(name)):
                res.add("error", where, f"{name} is required and must be a number")
        if any(not _number(clip.get(n)) for n in ("from_bar", "bars", "at_bar")):
            continue
        if clip["bars"] <= 0 or clip["at_bar"] < 1 or clip["from_bar"] < 1:
            res.add("error", where, "bars must be > 0, at_bar >= 1, and from_bar >= 1")
            continue
        loop = clip.get("loop", 1)
        pre_beats = clip.get("pre_beats", 0)
        if not isinstance(loop, int) or loop < 1:
            res.add("error", where, "loop must be a positive integer")
            continue
        if not (_number(pre_beats) and 0 <= pre_beats <= 8):
            res.add("error", where, "pre_beats must be between 0 and 8")
            continue
        if loop > 1 and pre_beats:
            res.add("error", where, "pre_beats cannot be combined with loop")
            continue
        for name in ("gain_db", "fade_in_beats", "fade_out_beats", "tail_beats"):
            if name in clip and not _number(clip[name]):
                res.add("error", where, f"{name} must be a number")
        _check_automation(res, where, clip.get("automation"))
        _check_fx(res, where, clip.get("fx"))
        _check_duck(res, where, clip.get("duck"))
        _check_pump(res, where, clip.get("pump"))
        _check_vocal_options(res, where, clip)

        grid = res.grids[source_name]
        src_bpb = grid.beats_per_bar
        start_index = grid.first_downbeat + (clip["from_bar"] - 1) * src_bpb - pre_beats
        beat_count = clip["bars"] * src_bpb + pre_beats
        if abs(beat_count - round(beat_count)) > 1e-6 or abs(start_index - round(start_index)) > 1e-6:
            res.add("error", where, "from_bar, bars, and pre_beats must land on whole beats")
            continue
        start_index, beat_count = int(round(start_index)), int(round(beat_count))
        times = [grid.beat_time(start_index + i) for i in range(beat_count + 1)]
        if times[0] < -0.01:
            res.add("warning", where, f"clip starts {-times[0]:.2f}s before the track begins (silence)")
        if times[-1] > grid.duration + 0.01:
            res.add("warning", where, f"clip runs {times[-1] - grid.duration:.2f}s past the end of {track} (silence)")

        ratio = source.get("tempo_ratio", 1)
        src_bpm = 60.0 * beat_count / (times[-1] - times[0])
        at_beat = (clip["at_bar"] - 1) * bpb - pre_beats * ratio
        out_beats = beat_count * ratio * loop
        out_seconds = res.tempo.time_at(at_beat + out_beats) - res.tempo.time_at(at_beat)
        out_bpm = 60.0 * out_beats / out_seconds
        stretch_pct = (out_bpm / (src_bpm * ratio) - 1.0) * 100.0
        limit = 6.0 if stem in VOCAL_STEMS else 10.0
        if abs(stretch_pct) > 30:
            res.add("error", where, f"needs {stretch_pct:+.1f}% time-stretch; pick another tempo or tempo_ratio")
        elif abs(stretch_pct) > limit:
            res.add("warning", where, f"{stretch_pct:+.1f}% time-stretch on {stem} will be audible")
        semitones = source.get("semitones", 0) if isinstance(source.get("semitones", 0), int) else 0
        if abs(semitones) > (2 if stem in VOCAL_STEMS else 4):
            res.add("warning", where, f"{semitones:+d} semitone shift on {stem} may sound unnatural")

        if clip["at_bar"] % 4 != 1 and clip["at_bar"] % 1 == 0:
            res.add("info", where, f"at_bar {clip['at_bar']} is off the 4-bar phrase grid")
        res.clips.append(ResolvedClip(
            index=index,
            id=str(clip.get("id") or f"clip{index + 1}"),
            source=source_name,
            track=track,
            stem=stem,
            spec=clip,
            src_beat_times=times,
            out_start_beat=at_beat,
            anchor_beat=(clip["at_bar"] - 1) * bpb,
            out_beats_per_src_beat=float(ratio),
            loop=loop,
            semitones=semitones,
            gain_db=float(source.get("gain_db", 0)) + float(clip.get("gain_db", 0)),
            stretch_pct=stretch_pct,
        ))

    groove = plan.get("groove")
    if groove is not None:
        if not isinstance(groove, dict):
            res.add("error", "groove", "groove must be an object")
        else:
            _check_pump(res, "groove.pump_fx", groove.get("pump_fx"))

    master = plan.get("master", {})
    if not isinstance(master, dict):
        res.add("error", "master", "master must be an object")
    else:
        if "lufs" in master and not (_number(master["lufs"]) and -24 <= master["lufs"] <= -6):
            res.add("error", "master.lufs", "lufs must be between -24 and -6")
        if "ceiling_db" in master and not (_number(master["ceiling_db"]) and -6 <= master["ceiling_db"] <= 0):
            res.add("error", "master.ceiling_db", "ceiling_db must be between -6 and 0")
        if "mono_bass_hz" in master and not (_number(master["mono_bass_hz"]) and 0 <= master["mono_bass_hz"] <= 300):
            res.add("error", "master.mono_bass_hz", "mono_bass_hz must be between 0 (off) and 300")
        ref = master.get("reference")
        if ref is not None:
            track = ref if isinstance(ref, str) else ref.get("track") if isinstance(ref, dict) else None
            if not isinstance(track, str):
                res.add("error", "master.reference", "reference must be a track id or {track, stem}")
            elif not (library.track_dir(track) / "track.json").exists():
                res.add("error", "master.reference", f"reference track {track!r} is not in the library")

    if res.ok and res.clips:
        _check_overlaps(res, bpb, keys, key_confidence)
    return res


LOW_KEY_CONFIDENCE = 0.3


def _check_overlaps(res: Resolution, bpb: int, keys: dict[str, Key], confidence: dict[str, float]) -> None:
    last_beat = max(clip.out_end_beat for clip in res.clips)
    total_bars = int(math.ceil(last_beat / bpb))
    bass_clash: dict[tuple[str, str], list[int]] = {}
    vocal_clash: dict[tuple[str, str], list[int]] = {}
    key_clash: dict[tuple[str, str], tuple[int, set[str]]] = {}
    empty: list[int] = []
    for bar in range(total_bars):
        probe = bar * bpb + bpb / 2  # middle of the bar
        active = [c for c in res.clips if c.out_start_beat <= probe < c.out_end_beat]
        if not active:
            empty.append(bar + 1)
            continue
        for i, a in enumerate(active):
            for b in active[i + 1:]:
                pair = tuple(sorted((a.id, b.id)))
                if not _bass_killed(a, probe, bpb) and not _bass_killed(b, probe, bpb):
                    bass_clash.setdefault(pair, []).append(bar + 1)
                if _vocal_active(res, a, probe, bpb) and _vocal_active(res, b, probe, bpb):
                    vocal_clash.setdefault(pair, []).append(bar + 1)
                if (a.source != b.source and a.stem in HARMONIC_STEMS and b.stem in HARMONIC_STEMS
                        and camelot_distance(keys[a.source], keys[b.source]) >= 2):
                    sources = tuple(sorted((a.source, b.source)))
                    key_clash.setdefault(sources, (camelot_distance(keys[a.source], keys[b.source]), set()))[1].update(
                        (a.id, b.id))
    for pair, bars in bass_clash.items():
        res.add("warning", f"bars {_ranges(bars)}",
                f"two basslines play at once ({pair[0]} + {pair[1]}); cut eq_low_db on one side or swap them")
    for pair, bars in vocal_clash.items():
        res.add("warning", f"bars {_ranges(bars)}", f"two vocals overlap ({pair[0]} + {pair[1]})")
    for (source_a, source_b), (distance, clip_ids) in key_clash.items():
        unsure = min(confidence.get(source_a, 0.5), confidence.get(source_b, 0.5)) < LOW_KEY_CONFIDENCE
        res.add("info" if unsure else "warning", f"sources {source_a} + {source_b} ({', '.join(sorted(clip_ids))})",
                f"keys {keys[source_a].camelot} vs {keys[source_b].camelot} are {distance} steps apart on the "
                "Camelot wheel; shift semitones or keep the overlap short/percussive"
                + (" (low key confidence: trust your ears)" if unsure else ""))
    if empty:
        res.add("warning", f"bars {_ranges(empty)}", "no clip is playing (silence)")
