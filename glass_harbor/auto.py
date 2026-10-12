"""One command from two audio files to a finished mashup.

``run_auto`` ingests both records (or reuses library tracks), separates and cleans what the draft needs,
transcribes lyrics, drafts the plan (``scaffold.build_mashup``: structure, stems, drops, fills, call and response,
half-time switch, bass that follows the vocal), renders, and then runs fix rounds: it reads QA, applies the fixes
it knows to be safe, and renders again until nothing is left to fix or the rounds run out. The result is a
rendered mix with a phone version, a plan, and a brief that records every decision.

The only things left to a person are choosing the records and saying whether it sounds good.
"""

from __future__ import annotations

import datetime as dt
import math
from pathlib import Path
from typing import Any, Callable

from glass_harbor import library

Log = Callable[[str], None]

MAX_AUTO_GAIN_DB = 6.0  # fix rounds never lift one vocal clip more than this in total
MAX_AUTO_DUCK_DB = 10.0
BASS_CLASH_PCT = 10.0


def ingest(source: str, *, sections: str, log: Log) -> str:
    """A path is added to the library (or matched to the copy already there); anything else is a track id."""
    from glass_harbor.analyze import analyze_library_track

    path = Path(source).expanduser()
    if path.is_file():
        track_id, created = library.add_track(path)
        log(f"{'added' if created else 'already in the library'}: {track_id}")
    else:
        track_id = source
        if not (library.track_dir(track_id) / "track.json").exists():
            raise FileNotFoundError(f"{source} is neither an audio file nor a library track id")
    analysis = library.load_analysis(track_id) if library.analysis_path(track_id).exists() else None
    if analysis is None or (sections == "allin1" and analysis.get("sections_backend") != "allin1"):
        analyze_library_track(track_id, log=log, sections=sections)
    return track_id


def _lyrics(track_id: str, log: Log) -> None:
    from glass_harbor.lyrics import load_lyrics, transcribe, update_analysis
    from glass_harbor.lyrics_ref import fetch_reference, load_reference

    if load_lyrics(track_id) is None and "vocals" in library.available_stems(track_id):
        log(f"transcribing {track_id}")
        update_analysis(track_id, transcribe(track_id))
    if load_lyrics(track_id) is not None and load_reference(track_id) is None:
        fetch_reference(track_id, log=log)


def separate_vocal_only(track_id: str, log: Log) -> None:
    """The acapella alone (best quality), enough for the fit check to tell sung from rapped."""
    from glass_harbor.separate import separate_track

    separate_track(track_id, stems=["vocals"], quality="best", log=log)


def prepare_vocal(track_id: str, log: Log) -> None:
    """Best-quality acapella, gently de-reverbed; the original bass (so the beat's bass can follow the vocal's
    chords); word-timed lyrics."""
    from glass_harbor.analyze import analyze_library_track
    from glass_harbor.separate import clean_stem, separate_track

    produced = separate_track(track_id, stems=["vocals", "bass"], quality="best", log=log)
    info = library.load_meta(track_id).get("stems", {}).get("vocals", {})
    if not info.get("cleaned"):
        clean_stem(track_id, "vocals", "dereverb-gentle", log=log)
        produced["cleaned"] = {}
    if produced:
        analyze_library_track(track_id, log=log)
    _lyrics(track_id, log)


def bed_sections() -> str:
    """Verse/chorus labels from allin1 when its optional package is installed, else energy-based novelty sections."""
    import importlib.util

    return "allin1" if importlib.util.find_spec("allin1_infer") else "novelty"


def prepare_bed(track_id: str, log: Log) -> None:
    """Instrumental and drums/bass/other stems (the separation keeps the beat's own vocal for call and response),
    verse/chorus sections, and lyrics for that vocal."""
    from glass_harbor.analyze import analyze_library_track
    from glass_harbor.separate import separate_track

    produced = separate_track(track_id, stems=["instrumental", "drums", "bass", "other"], quality="best", log=log)
    if produced:
        analyze_library_track(track_id, log=log, sections=bed_sections())
    _lyrics(track_id, log)


# ---------------------------------------------------------------- fix rounds


def _bars(clip: Any, bpb: int) -> range:
    return range(int(math.floor(1 + clip.out_start_beat / bpb)), int(math.ceil(1 + clip.out_end_beat / bpb)))


def apply_qa_fixes(plan: dict[str, Any], report: dict[str, Any], qa: dict[str, Any],
                   heard: dict[str, Any] | None = None) -> list[str]:
    """The fixes QA findings map to safely. Changes ``plan`` in place; returns what was done (empty when there is
    nothing left that a rule can fix)."""
    from glass_harbor.plan import resolve
    from glass_harbor.scaffold import _lane_override, follow_vocal_roots

    res = resolve(plan)
    bpb = res.beats_per_bar
    auto = plan.setdefault("auto", {"gain_db": {}, "duck_db": {}})
    changes: list[str] = []

    # 1. Buried vocal: lift the clips that carry two or more buried bars, and duck the melodic layer harder.
    buried = {p["bar"] for p in report.get("vocal_presence", []) if p["db"] < -3.0}
    masked = set((heard or {}).get("weak", []))  # Whisper could not make out the words in the finished mix
    lifted = []
    for clip in res.clips:
        if clip.stem != "vocals" or clip.chop is not None or clip.source == "bed":
            continue
        weak = len(buried & set(_bars(clip, bpb))) >= 2 or clip.id in masked
        if weak and auto["gain_db"].get(clip.id, 0.0) < MAX_AUTO_GAIN_DB:
            spec = plan["clips"][clip.index]
            spec["gain_db"] = round(float(spec.get("gain_db", 0.0)) + 2.0, 2)
            auto["gain_db"][clip.id] = auto["gain_db"].get(clip.id, 0.0) + 2.0
            lifted.append(clip.id)
    if lifted:
        changes.append(f"vocal buried or hard to make out: +2 dB on {', '.join(lifted)}")
        for clip in res.clips:
            spec = plan["clips"][clip.index]
            if clip.stem == "other" and spec.get("duck") and auto["duck_db"].get(clip.id, 0.0) < 4.0 \
                    and float(spec["duck"].get("db", 0)) + 2.0 <= MAX_AUTO_DUCK_DB:
                spec["duck"]["db"] = float(spec["duck"]["db"]) + 2.0
                auto["duck_db"][clip.id] = auto["duck_db"].get(clip.id, 0.0) + 2.0
                changes.append(f"{clip.id} ducks {spec['duck']['db']:g} dB under the vocal")

    # 2. A drop without contrast: take the bass and melody out of the bar before it.
    for flag in qa.get("flags", []):
        if "of contrast with the 8 bars before it" not in flag["message"]:
            continue
        bar = int(float(flag["where"].split()[-1]))
        stripped = []
        for clip in res.clips:
            if clip.source != "bed" or clip.stem not in ("bass", "other", "instrumental") or clip.loop != 1:
                continue
            anchor = 1 + clip.anchor_beat / bpb
            if not anchor <= bar - 1 < 1 + clip.out_end_beat / bpb:
                continue
            lanes = plan["clips"][clip.index].setdefault("automation", {})
            from glass_harbor.plan import AUTOMATABLE, automation_value

            if automation_value(lanes.get("arrange_db"), bar - 1 - anchor + 0.5, AUTOMATABLE["arrange_db"]) <= -40:
                continue  # already stripped: nothing more this rule can do
            _lane_override(lanes, "arrange_db", bar - 1 - anchor, bar - anchor, -60.0)
            stripped.append(clip.id)
        if stripped:
            changes.append(f"drop at bar {bar}: {', '.join(stripped)} out for bar {bar - 1}")

    # 3. Sung notes off the bass: make the bass follow the vocal's chords under those clips.
    clashing = [c["clip"] for c in report.get("bass_clash", []) if c["pct"] >= BASS_CLASH_PCT and c["sung_frames"] >= 40]
    if clashing:
        already = {i for c in plan["clips"] for i in (c.get("follow_roots") or []) if isinstance(i, str)}
        wanted = sorted(set(clashing) - already)
        if wanted and any(c.get("stem") == "bass" for c in plan["clips"]):
            follow_vocal_roots(plan, clip_ids=sorted(already | set(wanted)))
            changes.append(f"bass follows the vocal's chords under {', '.join(wanted)}")
    if changes:
        plan.setdefault("notes", []).append("auto fix: " + "; ".join(changes))
    return changes


def steady_weak(previous: set[str] | None, heard: dict[str, Any] | None) -> dict[str, Any]:
    """Clips Whisper could not make out in this render and the one before. Its read of a sung, autotuned vocal
    swings between near-identical renders (GLOCK's hook read 49%, 40%, then 0% with nothing changed under it), so
    one weak reading is not enough to act on."""
    weak = set((heard or {}).get("weak", []))
    return {"weak": sorted(weak & previous) if previous is not None else []}


def fix_round(plan: dict[str, Any], report: dict[str, Any], qa: dict[str, Any], heard: dict[str, Any] | None,
              previous_weak: set[str] | None, run_dir: Path, log: Log) -> tuple[list[str], set[str]]:
    """One round of QA fixes. Returns (changes, the weak clips of the latest reading)."""
    steady = steady_weak(previous_weak, heard)
    latest = heard
    changes = apply_qa_fixes(plan, report, qa, steady)
    if not changes and set((heard or {}).get("weak", [])) - set(steady["weak"]):
        # A clip read weak once and nothing else changes this round: listen to the same render again with Whisper's
        # windows shifted before calling it noise (re-rendering an unchanged plan would give the same audio).
        latest = _listen(run_dir, log, shift_s=LISTEN_SHIFT_S)
        changes = apply_qa_fixes(plan, report, qa, steady_weak(set(heard["weak"]), latest))
    return changes, set((latest or {}).get("weak", []))


LISTEN_SHIFT_S = 15.0  # half a Whisper window: the second reading cuts the audio at different places


def _listen(run_dir: Path, log: Log, *, shift_s: float = 0.0) -> dict[str, Any] | None:
    """Whisper intelligibility of the finished mix (skipped when no Whisper backend is installed)."""
    from glass_harbor.listen import listen_run
    from glass_harbor.lyrics import whisper_backend

    if whisper_backend() is None:
        log("no Whisper backend installed: skipping the listening pass")
        return None
    return listen_run(run_dir, log=log, shift_s=shift_s)


# ---------------------------------------------------------------- brief


def write_brief(slug: str, plan: dict[str, Any], vocal: str, bed: str, qa: dict[str, Any] | None,
                rounds: list[list[str]], check: dict[str, Any] | None = None) -> Path:
    from glass_harbor.paths import mix_dir

    def describe(track_id: str) -> str:
        meta = library.load_meta(track_id)
        analysis = library.load_analysis(track_id)
        key = analysis.get("key", {})
        name = " - ".join(x for x in (meta.get("artist", ""), meta.get("title", track_id)) if x)
        stems = ", ".join(library.available_stems(track_id))
        return (f"`{track_id}`: {name} — {analysis['grid']['bpm']:.1f} bpm ({analysis['grid']['mode']} grid), "
                f"{key.get('name', '?')} ({key.get('camelot', '?')}, confidence {key.get('confidence', 0):.2f}), "
                f"drops at {analysis.get('drops') or 'none'}; stems: {stems}")

    lines = [f"# {plan['title']}", "", "## Goal", "",
             "- kind: mashup (one-command draft: `glass-harbor auto`)",
             "- vibe: club edit on the beat's own structure; the user judges it by ear", "",
             "## Sources (from analysis)", "", f"- {describe(vocal)}", f"- {describe(bed)}", "",
             "## Fit check", "",
             *([f"- verdict: {check['verdict']} ({check['vocal_type']} vocal); "
                + ", ".join(f"{c['check']} {c['value']} ({c['level']})" for c in check["checks"])]
               + [f"- {r}" for r in check["reasons"]]
               + [f"- hit potential: {check['potential']['level']} ({check['potential']['score']}/100)"]
               + [f"  - {r}" for r in check["potential"]["reasons"]] if check else ["- not run"]), "",
             "## Decisions (the draft's rules; edit the plan to change them)", ""]
    lines += [f"- {note}" for note in plan.get("notes", [])]
    lines += ["", "## Fix rounds", ""]
    lines += [f"- round {i + 1}: {'; '.join(r) if r else 'nothing left to fix'}" for i, r in enumerate(rounds)] or ["- none"]
    if qa is not None:
        lines += ["", "## QA after the last render", "", f"- verdict: {qa['verdict']}, "
                  f"{qa['loudness_lufs']:.1f} LUFS, {qa['true_peak_db']:.1f} dBTP"]
        lines += [f"- {f['level']}: {f['where']}: {f['message']}" for f in qa.get("flags", [])]
    lines += ["", "## Needs ears", "", "- Does the vocal ride the beat? Do the drops land? Anything off pitch or buried?"]
    path = mix_dir(slug) / f"{slug}.brief.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    return path


# ---------------------------------------------------------------- pipeline


class PoorFit(ValueError):
    """The fit check says this beat will not carry this vocal (raised before the long work starts)."""


def run_auto(vocal: str, bed: str, *, slug: str | None = None, title: str = "", rounds: int = 2,
             force: bool = False, log: Log = print) -> dict[str, Any]:
    from glass_harbor.check import check_run
    from glass_harbor.paths import plan_path, require_slug, runs_dir
    from glass_harbor.plan import resolve, save_plan
    from glass_harbor.render import render_plan
    from glass_harbor.scaffold import build_mashup

    from glass_harbor.fit import assess

    vocal_id = ingest(vocal, sections="novelty", log=log)
    bed_id = ingest(bed, sections=bed_sections(), log=log)
    separate_vocal_only(vocal_id, log)
    check = assess(vocal_id, bed_id, log=log)
    log(f"fit check: {check['verdict']}" + (f" ({'; '.join(check['reasons'])})" if check["reasons"] else "")
        + f"; hit potential {check['potential']['level']} ({check['potential']['score']}/100)")
    if check["verdict"] == "poor" and not force:
        raise PoorFit(f"{vocal_id} over {bed_id} fails the fit check: {'; '.join(check['reasons'])}. Pick another "
                      "beat, or pass --force to make it anyway.")
    prepare_vocal(vocal_id, log)
    prepare_bed(bed_id, log)
    slug = require_slug(slug or f"{vocal_id}-x-{bed_id}")
    names = [library.load_meta(t).get("title", t) for t in (vocal_id, bed_id)]
    plan = build_mashup(vocal_id, bed_id, title=title or f"{names[0]} x {names[1]}")
    res = resolve(plan)
    if not res.ok:
        raise ValueError("the draft has plan errors: " + "; ".join(i.message for i in res.issues if i.level == "error"))
    save_plan(plan_path(slug), plan)

    history: list[list[str]] = []
    run_dir, qa, report = None, None, None
    previous_weak: set[str] | None = None
    for round_index in range(rounds + 1):
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        run_dir = runs_dir(slug) / stamp
        log(f"render {round_index + 1}: {run_dir}")
        report = render_plan(plan, run_dir, log=log)
        heard = _listen(run_dir, log)
        qa = check_run(run_dir)
        if round_index == rounds:
            break
        changes, previous_weak = fix_round(plan, report, qa, heard, previous_weak, run_dir, log)
        history.append(changes)
        if not changes:
            break
        log("fixing: " + "; ".join(changes))
        save_plan(plan_path(slug), plan)
    brief = write_brief(slug, plan, vocal_id, bed_id, qa, history, check)
    files = (report or {}).get("files", {})
    return {"slug": slug, "vocal": vocal_id, "bed": bed_id, "run": str(run_dir), "brief": str(brief),
            "plan": str(plan_path(slug)), "phone": str(run_dir / files["phone"]) if files.get("phone") else None,
            "short": str(run_dir / files["short"]) if files.get("short") else None,
            "mp3": str(run_dir / files["mp3"]) if files.get("mp3") else None,
            "verdict": qa["verdict"] if qa else None, "flags": qa.get("flags", []) if qa else [],
            "rounds": history}
