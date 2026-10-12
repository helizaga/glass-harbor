"""glass-harbor CLI: track library, compatibility, mix plans, rendering, and QA."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from glass_harbor import __version__, library
from glass_harbor.paths import mix_dir, mixes_dir, plan_path, require_slug, runs_dir, workspace_root


def _emit(args: argparse.Namespace, payload: Any, text: str) -> None:
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2))
    else:
        print(text)


def _log(args: argparse.Namespace):
    def log(message: str) -> None:
        if not getattr(args, "json", False):
            print(f"  {message}", file=sys.stderr)
    return log


# ---------------------------------------------------------------- doctor

def cmd_doctor(args: argparse.Namespace) -> int:
    from glass_harbor.analyze import beat_backends

    checks = {
        "workspace": str(workspace_root()),
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "beat_backends": beat_backends(),
        "audio_separator": importlib.util.find_spec("audio_separator") is not None,
        "torch": importlib.util.find_spec("torch") is not None,
    }
    lines = [f"glass-harbor {__version__}"] + [f"- {k}: {v}" for k, v in checks.items()]
    if not checks["audio_separator"]:
        lines.append("  stems need: pip install -e '.[ml]'")
    _emit(args, checks, "\n".join(lines))
    return 0


# ---------------------------------------------------------------- tracks

def _parse_stems(values: list[str] | None) -> dict[str, Path]:
    stems: dict[str, Path] = {}
    for value in values or []:
        name, _, path = value.partition("=")
        if not path:
            raise ValueError(f"--stem expects NAME=PATH, got {value!r}")
        stems[name.strip()] = Path(path)
    return stems


def _summary(track_id: str) -> dict[str, Any]:
    meta = library.load_meta(track_id)
    info: dict[str, Any] = {"id": track_id, "title": meta.get("title"), "duration": meta.get("duration"),
                            "stems": library.available_stems(track_id)}
    if library.analysis_path(track_id).exists():
        analysis = library.load_analysis(track_id)
        info.update({
            "bpm": analysis["bpm"],
            "key": analysis["key"]["name"],
            "camelot": analysis["key"]["camelot"],
            "key_confidence": analysis["key"]["confidence"],
            "key_backend": analysis["key"].get("backend"),
            "bars": analysis["grid"]["bar_count"],
            "grid": analysis["grid"]["mode"],
            "lufs": analysis["loudness_lufs"],
        })
    return info


def _analyze(track_id: str, backend: str, log, sections: str | None = None) -> dict[str, Any]:
    from glass_harbor.analyze import analyze_library_track

    return analyze_library_track(track_id, backend=backend, log=log, sections=sections)


def cmd_track_add(args: argparse.Namespace) -> int:
    log = _log(args)
    results = []
    for raw in args.files:
        track_id, created = library.add_track(Path(raw), track_id=args.id if len(args.files) == 1 else None,
                                              title=args.title, artist=args.artist, stems=_parse_stems(args.stem))
        log(f"{'added' if created else 'already in library'}: {track_id}")
        if args.separate:
            from glass_harbor.separate import separate_track

            separate_track(track_id, stems=args.separate.split(","), quality=args.quality, log=log)
        if not args.no_analyze and (created or args.stem or args.separate or not library.analysis_path(track_id).exists()):
            _analyze(track_id, args.beats, log, args.sections)
        results.append(_summary(track_id))
    _emit(args, results, "\n".join(_format_summary(r) for r in results))
    return 0


def _format_summary(info: dict[str, Any]) -> str:
    if "bpm" not in info:
        return f"{info['id']}: not analyzed"
    stems = ",".join(info["stems"]) or "-"
    return (f"{info['id']}: {info['bpm']:.1f} bpm, {info['key']} ({info['camelot']}, conf {info['key_confidence']:.2f}"
            f"{', ' + info['key_backend'] if info.get('key_backend') else ''}),"
            f" {info['bars']} bars [{info['grid']}], {info['lufs']:.1f} LUFS, stems: {stems}")


def cmd_track_analyze(args: argparse.Namespace) -> int:
    log = _log(args)
    ids = library.list_tracks() if args.all else args.ids
    results = []
    for track_id in ids:
        if not args.force and library.analysis_path(track_id).exists():
            log(f"skip {track_id} (already analyzed; --force to redo)")
        else:
            _analyze(track_id, args.beats, log, args.sections)
        results.append(_summary(track_id))
    _emit(args, results, "\n".join(_format_summary(r) for r in results))
    return 0


def cmd_track_separate(args: argparse.Namespace) -> int:
    from glass_harbor.separate import separate_track

    log = _log(args)
    produced = separate_track(args.id, stems=args.stems.split(",") if args.stems else None, quality=args.quality,
                              force=args.force, log=log)
    if produced and library.analysis_path(args.id).exists():
        _analyze(args.id, args.beats, log)
    _emit(args, {"id": args.id, "produced": produced, "stems": library.available_stems(args.id)},
          f"{args.id}: stems {', '.join(library.available_stems(args.id)) or 'none'}"
          + (f" (new: {', '.join(produced)})" if produced else " (nothing new)"))
    return 0


def cmd_track_lyrics(args: argparse.Namespace) -> int:
    from glass_harbor.grid import Grid
    from glass_harbor.lyrics import bar_lines, hooks, load_lyrics, transcribe, update_analysis

    log = _log(args)
    lyrics = None if args.force else load_lyrics(args.id)
    if lyrics is None:
        log(f"transcribing {args.id} (first run downloads the model)")
        lyrics = transcribe(args.id, model=args.model, backend=args.backend)
    update_analysis(args.id, lyrics)
    from glass_harbor.lyrics_ref import fetch_reference, load_reference

    if args.force or load_reference(args.id) is None:
        fetch_reference(args.id, log=log)
    grid = Grid.from_dict(library.load_analysis(args.id)["grid"])
    lines = bar_lines(lyrics, grid)
    found = hooks(lyrics, grid)
    payload = {"id": args.id, "lines": lines, "hooks": found}
    text = [f"bar {l['start_bar']:>6.2f}-{l['end_bar']:<6.2f} {l['text'][:70]}" for l in lines]
    text += ["hooks:"] + [f"  x{h['count']} {h['text'][:60]} @ bars "
                          + ", ".join(f"{o['start_bar']:g}" for o in h["occurrences"]) for h in found]
    _emit(args, payload, "\n".join(text))
    return 0


def cmd_track_clean(args: argparse.Namespace) -> int:
    from glass_harbor.separate import clean_stem

    result = clean_stem(args.id, args.stem, args.mode, log=_log(args), restart=args.restart)
    _emit(args, result, f"{args.id}/{args.stem}: cleaned with {result['model']} (original kept at {result['raw']})")
    return 0


def cmd_track_list(args: argparse.Namespace) -> int:
    results = [_summary(t) for t in library.list_tracks()]
    _emit(args, results, "\n".join(_format_summary(r) for r in results) or "library is empty")
    return 0


def cmd_track_show(args: argparse.Namespace) -> int:
    info = _summary(args.id)
    analysis = library.load_analysis(args.id) if library.analysis_path(args.id).exists() else {}
    payload = {**info, "sections": analysis.get("sections", []),
               "vocal_phrases": analysis.get("stems", {}).get("vocals", {}).get("phrases", []),
               "grid_notes": analysis.get("grid", {}).get("notes", [])}
    lines = [_format_summary(info), "sections:"]
    for s in payload["sections"]:
        lines.append(f"  bar {s['start_bar']:>3} +{s['bars']:<3} {s['label']} {s['energy']:<4} ({s.get('mean_db', 0):.1f} dB)")
    if payload["vocal_phrases"]:
        lines.append("vocal phrases: " + ", ".join(f"{p['start_bar']}+{p['bars']}" for p in payload["vocal_phrases"]))
    if analysis.get("drops"):
        payload["drops"] = analysis["drops"]
        lines.append("drops (kick + bass return): bars " + ", ".join(str(b) for b in analysis["drops"]))
    if analysis.get("hooks"):
        payload["hooks"] = analysis["hooks"]
        lines.append("hooks (repeated lines): " + "; ".join(
            f"x{h['count']} at bars " + ", ".join(f"{o['start_bar']:g}" for o in h["occurrences"])
            for h in analysis["hooks"]))
    if payload["grid_notes"]:
        lines.append("grid: " + "; ".join(payload["grid_notes"]))
    _emit(args, payload, "\n".join(lines))
    return 0


# ---------------------------------------------------------------- matching

def cmd_match(args: argparse.Namespace) -> int:
    from glass_harbor import compat

    base = library.load_analysis(args.id)
    others = args.against or [t for t in library.list_tracks() if t != args.id]
    rows = []
    for other in others:
        if not library.analysis_path(other).exists():
            continue
        analysis = library.load_analysis(other)
        if args.role == "vocals":
            fit = compat.score_pair(args.id, base, other, analysis)[0]
            rows.append({"track": other, **fit.to_dict()})
        elif args.role == "bed":
            fit = compat.score_pair(other, analysis, args.id, base)[0]
            rows.append({"track": other, **fit.to_dict()})
        else:
            rows.append({"track": other, **compat.transition_fit(base, analysis)})
    rows.sort(key=lambda row: -row["score"])
    if args.role == "next":
        lines = [f"{r['score']:.2f}  {r['track']}: {r['camelot']} ({r['relation']}), "
                 f"{r['stretch_pct_for_b']:+.1f}% stretch x{r['tempo_ratio']:g}" for r in rows]
    else:
        lines = [f"{r['score']:.2f}  {r['track']}: {r['key_a']} over {r['key_b']} ({r['relation']}), "
                 f"{r['semitones']:+d} st, {r['stretch_pct']:+.1f}% stretch x{r['tempo_ratio']:g}" for r in rows]
    _emit(args, rows, "\n".join(lines) or "no analyzed tracks to compare")
    return 0


# ---------------------------------------------------------------- mixes

def _brief(slug: str, plan: dict[str, Any]) -> str:
    sources = "\n".join(f"- `{name}`: {src['track']}" for name, src in plan["sources"].items())
    notes = "\n".join(f"- {note}" for note in plan.get("notes", []))
    return (f"# {plan['title']}\n\n## Goal\n\n- kind: {plan['kind']}\n- vibe: (describe the intended energy and moment)\n\n"
            f"## Sources\n\n{sources}\n\n## Scaffold notes\n\n{notes or '- none'}\n\n## Decisions\n\n- \n")


def cmd_mix_new(args: argparse.Namespace) -> int:
    from glass_harbor import scaffold

    slug = require_slug(args.slug)
    target = plan_path(slug)
    if target.exists() and not args.force:
        raise FileExistsError(f"{target} exists; pass --force to overwrite")
    if args.kind == "mashup":
        if not (args.vocals and args.bed):
            raise ValueError("mashup needs --vocals <track> --bed <track>")
        plan = scaffold.build_mashup(args.vocals, args.bed, semitones=args.semitones, title=args.title or "")
    elif args.kind == "transition":
        if not args.tracks or len(args.tracks) != 2:
            raise ValueError("transition needs --tracks <from> <to>")
        plan = scaffold.build_transition(args.tracks[0], args.tracks[1], style=args.style,
                                         blend_bars=args.blend_bars, title=args.title or "")
    else:
        if not args.tracks or len(args.tracks) < 2:
            raise ValueError("set needs --tracks <a> <b> [<c> ...]")
        styles = args.styles.split(",") if args.styles else None
        plan = scaffold.build_set(args.tracks, styles=styles, play_bars=args.play_bars, blend_bars=args.blend_bars,
                                  title=args.title or "")
    from glass_harbor.plan import save_plan

    save_plan(target, plan)
    brief = mix_dir(slug) / f"{slug}.brief.md"
    if not brief.exists():
        brief.write_text(_brief(slug, plan))
    return _validate_and_report(args, slug, prefix=f"wrote {target.relative_to(workspace_root())}\n")


def _validate_and_report(args: argparse.Namespace, slug: str, prefix: str = "") -> int:
    from glass_harbor.plan import load_plan, resolve

    res = resolve(load_plan(plan_path(slug)))
    issues = [i.to_dict() for i in res.issues]
    shown = [i for i in issues if args.verbose or i["level"] != "info"]
    lines = [f"{prefix}{slug}: {'ok' if res.ok else 'INVALID'} ({len(res.clips)} clips"
             + (f", tempo {res.tempo.describe(res.beats_per_bar)}" if res.tempo else "") + ")"]
    lines += [f"  {i['level']}: {i['where']}: {i['message']}" for i in shown]
    _emit(args, {"slug": slug, "ok": res.ok, "issues": issues}, "\n".join(lines))
    return 0 if res.ok else 1


def cmd_mix_validate(args: argparse.Namespace) -> int:
    return _validate_and_report(args, require_slug(args.slug))


def _latest_run(slug: str) -> Path:
    root = runs_dir(slug)
    runs = sorted(p for p in root.iterdir() if (p / "render.json").exists()) if root.exists() else []
    if not runs:
        raise FileNotFoundError(f"No renders for {slug} yet (glass-harbor mix render {slug}).")
    return runs[-1]


def _qa_text(qa: dict[str, Any], run: Path) -> str:
    lines = [f"render: {run.relative_to(workspace_root()) if run.is_relative_to(workspace_root()) else run}",
             f"verdict: {qa['verdict']} | {qa['loudness_lufs']:.1f} LUFS, {qa['true_peak_db']:.1f} dBTP,"
             f" {qa['duration_s']:.1f}s"]
    lines += [f"  {f['level']}: {f['where']}: {f['message']}" for f in qa["flags"]]
    return "\n".join(lines)


def cmd_mix_render(args: argparse.Namespace) -> int:
    from glass_harbor.check import check_run
    from glass_harbor.plan import load_plan
    from glass_harbor.render import render_plan

    slug = require_slug(args.slug)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = runs_dir(slug) / stamp
    render_plan(load_plan(plan_path(slug)), out_dir, start_bar=args.start_bar, end_bar=args.end_bar,
                write_clips=args.clips, mp3=not args.no_mp3, log=_log(args))
    qa = check_run(out_dir)
    _emit(args, {"run": str(out_dir), "qa": qa}, _qa_text(qa, out_dir))
    return 0


def cmd_mix_check(args: argparse.Namespace) -> int:
    from glass_harbor.check import check_run

    run = Path(args.run) if args.run else _latest_run(require_slug(args.slug))
    qa = check_run(run)
    _emit(args, qa, _qa_text(qa, run))
    return 0


def _run_for(slug: str, run_arg: str | None) -> Path:
    from glass_harbor import feedback

    if run_arg:
        candidate = Path(run_arg)
        if candidate.exists():
            return candidate
        for run in feedback.list_runs(slug):
            if run.name == run_arg:
                return run
        raise FileNotFoundError(f"No render {run_arg} for {slug}")
    return _latest_run(slug)


def cmd_mix_review(args: argparse.Namespace) -> int:
    import webbrowser

    from glass_harbor.review import serve

    slug = require_slug(args.slug)
    _latest_run(slug)
    server = serve(slug, args.port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"reviewing {slug} at {url} (Ctrl+C to stop)")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def _parse_time(value: str) -> float:
    if ":" in value:
        minutes, seconds = value.split(":", 1)
        return int(minutes) * 60 + float(seconds)
    return float(value)


def cmd_mix_comment(args: argparse.Namespace) -> int:
    from glass_harbor import feedback

    slug = require_slug(args.slug)
    run = _run_for(slug, args.run)
    if args.bar is not None:
        timeline = feedback.run_timeline(run)
        bars = {b["bar"]: b["t"] for b in timeline["bars"]}
        if int(args.bar) not in bars:
            raise ValueError(f"bar {args.bar} is not in this render")
        start = bars[int(args.bar)]
        end = bars.get(int(args.end_bar)) if args.end_bar else None
    else:
        start = _parse_time(args.at)
        end = _parse_time(args.to) if args.to else None
    comment = feedback.add_comment(run, time_s=start, end_s=end, tag=args.tag, text=args.text)
    _emit(args, comment, f"added {comment['id']} at bar {comment['bar']} ({', '.join(comment['clips']) or 'no clips'})")
    return 0


def cmd_mix_feedback(args: argparse.Namespace) -> int:
    from glass_harbor import feedback

    slug = require_slug(args.slug)
    runs = feedback.list_runs(slug) if args.all else [_run_for(slug, args.run)]
    items = []
    for run in runs:
        data = feedback.load_feedback(run)
        for comment in data["comments"]:
            if args.include_resolved or comment["status"] == "open":
                items.append({**comment, "run": run.name})
        if data.get("verdict"):
            items.append({"run": run.name, "verdict": data["verdict"]})
    lines = []
    for item in items:
        if "verdict" in item:
            lines.append(f"[{item['run']}] verdict: {item['verdict']['verdict']} {item['verdict'].get('note', '')}")
            continue
        span = f"{item['bar']}" if item["end_bar"] == item["bar"] else f"{item['bar']}-{item['end_bar']}"
        lines.append(f"[{item['run']}] {item['id']} bar {span} {item['tag']}: {item['text']}"
                     f" (clips: {', '.join(item['clips']) or '-'}) [{item['status']}]")
    _emit(args, items, "\n".join(lines) or "no open comments")
    return 0


def cmd_mix_resolve(args: argparse.Namespace) -> int:
    from glass_harbor import feedback

    slug = require_slug(args.slug)
    resolved = []
    for run in feedback.list_runs(slug):
        ids = {c["id"] for c in feedback.load_feedback(run)["comments"]}
        for comment_id in args.ids:
            if comment_id in ids:
                resolved.append(feedback.set_comment_status(run, comment_id, args.status, args.note or ""))
    missing = set(args.ids) - {c["id"] for c in resolved}
    if missing:
        raise ValueError(f"unknown comment ids: {', '.join(sorted(missing))}")
    _emit(args, resolved, f"marked {len(resolved)} comment(s) {args.status}")
    return 0


def cmd_taste(args: argparse.Namespace) -> int:
    from glass_harbor import feedback

    taste = feedback.load_taste()
    if args.action in ("set", "add") and not args.value:
        raise ValueError(f"taste {args.action} needs a value ({'name=value' if args.action == 'set' else 'a preference'})")
    if args.action == "set":
        if "=" not in args.value:
            raise ValueError("taste set expects name=value")
        name, _, value = args.value.partition("=")
        if name not in feedback.TASTE_DEFAULTS:
            raise ValueError(f"unknown default {name!r}; known: {', '.join(feedback.TASTE_DEFAULTS)}")
        taste["defaults"][name] = type(feedback.TASTE_DEFAULTS[name])(value)
        feedback.save_taste(taste)
    elif args.action == "add":
        taste["preferences"].append(args.value)
        feedback.save_taste(taste)
    effective = {**feedback.TASTE_DEFAULTS, **taste["defaults"]}
    lines = ["defaults:"] + [f"  {k} = {v}" for k, v in effective.items()]
    lines += ["preferences:"] + [f"  - {p}" for p in taste["preferences"]] or []
    lines.append(f"history: {len(taste['history'])} verdicts")
    _emit(args, {**taste, "effective_defaults": effective}, "\n".join(lines))
    return 0


def cmd_mix_drop(args: argparse.Namespace) -> int:
    from glass_harbor.plan import load_plan, save_plan
    from glass_harbor.scaffold import add_drop

    slug = require_slug(args.slug)
    path = plan_path(slug)
    riser: bool | str = False if args.no_riser or args.riser == "none" else (args.riser if args.riser.startswith("vocal:") else True)
    plan = add_drop(load_plan(path), args.at_bar, build_bars=args.build_bars,
                    clip_ids=args.clips.split(",") if args.clips else None, riser=riser,
                    impact=not args.no_impact, silence_beats=args.silence_beats, roll=args.roll)
    save_plan(path, plan)
    return _validate_and_report(args, slug, prefix=f"added a drop at bar {args.at_bar:g}\n")


def cmd_set_order(args: argparse.Namespace) -> int:
    from glass_harbor.export import order_tracks
    from glass_harbor.scaffold import choose_style

    order, cost = order_tracks(args.tracks, start=args.start)
    steps = []
    for a, b in zip(order, order[1:]):
        bpm_a, bpm_b = library.load_analysis(a)["bpm"], library.load_analysis(b)["bpm"]
        steps.append({"from": a, "to": b, "style": choose_style(bpm_a, bpm_b)})
    lines = [f"order (cost {cost:.2f}): " + " -> ".join(order)]
    lines += [f"  {s['from']} -> {s['to']}: {s['style']}" for s in steps]
    lines.append("next: glass-harbor mix new <slug> --kind set --tracks " + " ".join(order))
    _emit(args, {"order": order, "cost": round(cost, 3), "transitions": steps}, "\n".join(lines))
    return 0


def cmd_mix_export(args: argparse.Namespace) -> int:
    from glass_harbor.export import export_daw

    out = export_daw(_run_for(require_slug(args.slug), args.run))
    _emit(args, {"daw": str(out)}, f"DAW export: {out} (WAVs + tempo.mid + README.txt)")
    return 0


def cmd_mix_video(args: argparse.Namespace) -> int:
    from glass_harbor.export import render_video

    out = render_video(_run_for(require_slug(args.slug), args.run), vertical=not args.landscape,
                       subtitle=args.subtitle or "", start_bar=args.start_bar, end_bar=args.end_bar)
    _emit(args, {"video": str(out)}, f"video: {out}")
    return 0


def cmd_mix_arrange(args: argparse.Namespace) -> int:
    from glass_harbor.plan import load_plan, save_plan
    from glass_harbor.scaffold import arrange_bed_stems

    slug = require_slug(args.slug)
    path = plan_path(slug)
    pump = None if args.no_pump else {"db": args.pump_db, "release": 0.5}
    plan = arrange_bed_stems(load_plan(path), bed_clip_id=args.bed, verse_other_db=args.verse_other_db,
                             drums_only_bars=args.drums_only_bars, pump=pump, duck_drums_db=args.duck_drums_db)
    save_plan(path, plan)
    return _validate_and_report(args, slug, prefix="arranged the bed from stems\n")


def _edit_plan(args: argparse.Namespace, change, message: str) -> int:
    from glass_harbor.plan import load_plan, save_plan

    slug = require_slug(args.slug)
    path = plan_path(slug)
    save_plan(path, change(load_plan(path)))
    return _validate_and_report(args, slug, prefix=message + "\n")


def cmd_mix_edges(args: argparse.Namespace) -> int:
    from glass_harbor.scaffold import add_dj_edges

    return _edit_plan(args, lambda plan: add_dj_edges(plan, intro_bars=args.intro_bars, outro_bars=args.outro_bars),
                      f"added a {args.intro_bars}-bar DJ intro and {args.outro_bars}-bar outro")


def cmd_mix_follow(args: argparse.Namespace) -> int:
    from glass_harbor.plan import load_plan, save_plan
    from glass_harbor.scaffold import follow_vocal_roots

    slug = require_slug(args.slug)
    path = plan_path(slug)
    plan, findings = follow_vocal_roots(load_plan(path), clip_ids=args.clips.split(",") if args.clips else None)
    save_plan(path, plan)
    lines = ["sung notes a half-step/tritone off the bass (own bass -> this beat's bass):"]
    for f in findings:
        lines.append(f"  {f['clip']:16s} {f['over_own_bass_pct']:5.1f}% -> {f['over_bed_bass_pct']:5.1f}% "
                     f"({f['sung_frames']} sung frames)  {'FOLLOW' if f['follow'] else 'keep'}  "
                     f"own: {f['own_roots']} | beat: {f['bed_roots']}")
    if args.json:
        _emit(args, {"findings": findings}, "")
        return 0
    return _validate_and_report(args, slug, prefix="\n".join(lines) + "\n")


def cmd_mix_listen(args: argparse.Namespace) -> int:
    from glass_harbor.listen import listen_run

    run = _run_for(require_slug(args.slug), args.run)
    result = listen_run(run, log=_log(args))
    lines = [f"{run.name}: Whisper made out {result['overall_recall']:.0%} of the lyrics in the finished mix"
             if result["overall_recall"] is not None else f"{run.name}: no lyrics to check"]
    lines += [f"  {c['clip']:18s} {c['heard']:>3}/{c['expected']:<3} {c['recall']:.0%}"
              + ("  <- masked" if c["clip"] in result["weak"] else "") for c in result["clips"]]
    _emit(args, result, "\n".join(lines))
    return 0


def cmd_mix_fills(args: argparse.Namespace) -> int:
    from glass_harbor.scaffold import add_fills

    return _edit_plan(args, lambda plan: add_fills(plan, crashes=not args.no_crashes, swells=not args.no_swells),
                      "added fills")


def cmd_mix_edit(args: argparse.Namespace) -> int:
    from glass_harbor.scaffold import add_edit

    return _edit_plan(args, lambda plan: add_edit(plan, args.kind, args.at_bar, beats=args.beats, word=args.word,
                                                  occurrence=args.occurrence, pattern=args.pattern,
                                                  semitones=args.semitones),
                      f"added {args.kind} at bar {args.at_bar:g}")


def cmd_mix_list(args: argparse.Namespace) -> int:
    root = mixes_dir()
    slugs = sorted(p.name for p in root.iterdir() if (p / f"{p.name}.mix.json").exists()) if root.exists() else []
    _emit(args, slugs, "\n".join(slugs) or "no mixes yet")
    return 0


# ---------------------------------------------------------------- parser

def cmd_fit(args: argparse.Namespace) -> int:
    from glass_harbor.auto import bed_sections, ingest, separate_vocal_only
    from glass_harbor.fit import assess

    log = _log(args)
    vocal = ingest(args.vocal, sections="novelty", log=log)
    bed = ingest(args.bed, sections=bed_sections(), log=log)
    separate_vocal_only(vocal, log)
    result = assess(vocal, bed, log=log)
    fit = result["fit"]
    lines = [f"{vocal} over {bed}: {result['verdict'].upper()} ({result['vocal_type']} vocal, beat measured on "
             f"{result['measured_on']})",
             f"  key: {fit['relation']}, {fit['semitones']:+d} st; tempo x{fit['tempo_ratio']:g}, "
             f"{fit['stretch_pct']:+.1f}% stretch"]
    lines += [f"  {c['check']:11s} {c['value']}  {c['level']}" for c in result["checks"]]
    lines += [f"  - {reason}" for reason in result["reasons"]]
    _emit(args, result, "\n".join(lines))
    return 0 if result["verdict"] != "poor" else 1


def cmd_auto(args: argparse.Namespace) -> int:
    from glass_harbor.auto import run_auto

    result = run_auto(args.vocal, args.bed, slug=args.slug, title=args.title or "", rounds=args.rounds,
                      force=args.force, log=_log(args))
    lines = [f"{result['slug']}: {result['verdict']}",
             f"  send to a phone: {result['phone']}", f"  full quality:    {result['mp3']}",
             f"  plan: {result['plan']}", f"  brief: {result['brief']}"]
    lines += [f"  fix round {i + 1}: {'; '.join(r) if r else 'nothing left to fix'}"
              for i, r in enumerate(result["rounds"])]
    lines += [f"  {f['level']}: {f['where']}: {f['message']}" for f in result["flags"]]
    _emit(args, result, "\n".join(lines))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="glass-harbor", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> argparse.ArgumentParser:
        p.add_argument("--json", action="store_true", help="machine-readable output")
        return p

    common(sub.add_parser("doctor", help="check optional backends")).set_defaults(func=cmd_doctor)

    track = sub.add_parser("track", help="manage the local track library").add_subparsers(dest="action", required=True)
    p = common(track.add_parser("add", help="decode audio files into the library and analyze them"))
    p.add_argument("files", nargs="+")
    p.add_argument("--id")
    p.add_argument("--title")
    p.add_argument("--artist")
    p.add_argument("--stem", action="append", metavar="NAME=PATH", help="register an official stem (e.g. vocals=acapella.wav)")
    p.add_argument("--separate", metavar="STEMS", help="also separate these stems, e.g. vocals or vocals,instrumental")
    p.add_argument("--quality", choices=("fast", "balanced", "best"), default="balanced")
    p.add_argument("--beats", choices=("auto", "beat_this", "librosa"), default="auto")
    p.add_argument("--no-analyze", action="store_true")
    p.add_argument("--sections", choices=("novelty", "allin1"), help="allin1 = verse/chorus labels (~2 min/song)")
    p.set_defaults(func=cmd_track_add)

    p = common(track.add_parser("analyze", help="beat grid, key, loudness, sections"))
    p.add_argument("ids", nargs="*")
    p.add_argument("--all", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--beats", choices=("auto", "beat_this", "librosa"), default="auto")
    p.add_argument("--sections", choices=("novelty", "allin1"), help="allin1 = verse/chorus labels (~2 min/song)")
    p.set_defaults(func=cmd_track_analyze)

    p = common(track.add_parser("separate", help="split a track into stems locally"))
    p.add_argument("id")
    p.add_argument("--stems", help="comma list from vocals,instrumental,drums,bass,other (default: all)")
    p.add_argument("--quality", choices=("fast", "balanced", "best"), default="balanced")
    p.add_argument("--force", action="store_true")
    p.add_argument("--beats", choices=("auto", "beat_this", "librosa"), default="auto")
    p.set_defaults(func=cmd_track_separate)

    p = common(track.add_parser("clean", help="remove reverb/echo/noise from a stem (default: dereverb vocals)"))
    p.add_argument("id")
    p.add_argument("--stem", default="vocals")
    p.add_argument("--mode", choices=("dereverb", "dereverb-gentle", "deecho", "denoise", "lead"), default="dereverb",
                   help="lead = keep only the lead vocal (drops backing vocals/samples tuned to the original chords)")
    p.add_argument("--restart", action="store_true", help="start over from the original separation")
    p.set_defaults(func=cmd_track_clean)

    p = common(track.add_parser("lyrics", help="transcribe vocals with word timings (local Whisper), find hooks"))
    p.add_argument("id")
    p.add_argument("--model", help="default: whisper-large-v3-turbo for the chosen backend")
    p.add_argument("--backend", choices=("mlx", "faster"), help="default: mlx on Apple Silicon, else faster-whisper")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_track_lyrics)

    common(track.add_parser("list", help="list library tracks")).set_defaults(func=cmd_track_list)
    p = common(track.add_parser("show", help="sections and vocal phrases for one track"))
    p.add_argument("id")
    p.set_defaults(func=cmd_track_show)

    p = common(sub.add_parser("match", help="rank tracks by how well they mash up or mix with one track"))
    p.add_argument("id")
    p.add_argument("--role", choices=("vocals", "bed", "next"), default="next",
                   help="vocals: id's acapella over others; bed: others' vocals over id; next: DJ blend id -> other")
    p.add_argument("--against", nargs="+")
    p.set_defaults(func=cmd_match)

    mix = sub.add_parser("mix", help="mix plans").add_subparsers(dest="action", required=True)
    p = common(mix.add_parser("new", help="scaffold a plan from analysis"))
    p.add_argument("slug")
    p.add_argument("--kind", choices=("mashup", "transition", "set"), required=True)
    p.add_argument("--vocals")
    p.add_argument("--bed")
    p.add_argument("--semitones", type=int)
    p.add_argument("--tracks", nargs="+")
    p.add_argument("--style", choices=("auto", "blend", "cut", "echo", "filter"), default="auto")
    p.add_argument("--styles", help="set: comma list of styles per transition")
    p.add_argument("--play-bars", type=int, default=32)
    p.add_argument("--blend-bars", type=int)
    p.add_argument("--title")
    p.add_argument("--force", action="store_true")
    p.add_argument("--verbose", action="store_true")
    p.set_defaults(func=cmd_mix_new)

    p = common(mix.add_parser("validate", help="check a plan against the library and DJ rules"))
    p.add_argument("slug")
    p.add_argument("--verbose", action="store_true", help="include info-level notes")
    p.set_defaults(func=cmd_mix_validate)

    p = common(mix.add_parser("render", help="render a plan to runs/<slug>/<stamp>/mix.wav and run QA"))
    p.add_argument("slug")
    p.add_argument("--start-bar", type=float)
    p.add_argument("--end-bar", type=float)
    p.add_argument("--clips", action="store_true", help="also export each clip as an aligned WAV for a DAW")
    p.add_argument("--no-mp3", action="store_true")
    p.set_defaults(func=cmd_mix_render)

    p = common(mix.add_parser("check", help="re-run QA on a render"))
    p.add_argument("slug")
    p.add_argument("--run")
    p.set_defaults(func=cmd_mix_check)

    common(mix.add_parser("list", help="list mix plans")).set_defaults(func=cmd_mix_list)

    p = common(mix.add_parser("drop", help="add build -> silence -> drop (riser, high-pass sweep, impact) at a bar"))
    p.add_argument("slug")
    p.add_argument("--at-bar", type=float, required=True)
    p.add_argument("--build-bars", type=float, default=8)
    p.add_argument("--clips", help="comma list of bed clip ids (default: every non-vocal clip in the build)")
    p.add_argument("--silence-beats", type=float, default=1.0)
    p.add_argument("--no-riser", action="store_true")
    p.add_argument("--riser", default="noise", help="noise (default), none, or vocal:<word> (a riser made from a lyric word)")
    p.add_argument("--roll", action="store_true", help="snare roll cut from the beat's drum stem in the last 2 bars")
    p.add_argument("--no-impact", action="store_true")
    p.add_argument("--verbose", action="store_true")
    p.set_defaults(func=cmd_mix_drop)

    p = common(mix.add_parser("arrange", help="split the bed into drums/bass/other and arrange around the vocal"))
    p.add_argument("slug")
    p.add_argument("--bed", help="bed clip id (default: the first instrumental/mix clip)")
    p.add_argument("--verse-other-db", type=float, default=-60.0, help="melodic layer under verses (-60 = off)")
    p.add_argument("--drums-only-bars", type=float, default=1)
    p.add_argument("--pump-db", type=float, default=3.0)
    p.add_argument("--duck-drums-db", type=float, default=4.0, help="spectral duck on the drums under vocals (0 = off)")
    p.add_argument("--no-pump", action="store_true")
    p.add_argument("--verbose", action="store_true")
    p.set_defaults(func=cmd_mix_arrange)

    p = common(mix.add_parser("edges", help="DJ-friendly beat-only intro and outro so DJs can mix the edit"))
    p.add_argument("slug")
    p.add_argument("--intro-bars", type=int, default=16)
    p.add_argument("--outro-bars", type=int, default=16)
    p.add_argument("--verbose", action="store_true")
    p.set_defaults(func=cmd_mix_edges)

    p = common(mix.add_parser("follow", help="make the bed's bass follow the chords each vocal was written over"))
    p.add_argument("slug")
    p.add_argument("--clips", help="comma-separated vocal clip ids to follow (default: decide from pitch clashes)")
    p.add_argument("--verbose", action="store_true")
    p.set_defaults(func=cmd_mix_follow)

    p = common(mix.add_parser("listen", help="Whisper listens to a render: which vocal clips' words survive the beat"))
    p.add_argument("slug")
    p.add_argument("--run", help="run folder name (default: latest)")
    p.set_defaults(func=cmd_mix_listen)

    p = common(mix.add_parser("fills", help="crashes on hook entries and drops, reverse swells into hooks"))
    p.add_argument("slug")
    p.add_argument("--no-crashes", action="store_true")
    p.add_argument("--no-swells", action="store_true")
    p.add_argument("--verbose", action="store_true")
    p.set_defaults(func=cmd_mix_fills)

    p = common(mix.add_parser("edit", help="punchline edits: mute, stutter, tape_stop, lift"))
    p.add_argument("slug")
    p.add_argument("kind", choices=("mute", "stutter", "tape_stop", "lift"))
    p.add_argument("--at-bar", type=float, required=True)
    p.add_argument("--beats", type=float, default=1.0, help="mute/tape_stop length in beats")
    p.add_argument("--word", help="stutter: the lyric word to repeat")
    p.add_argument("--occurrence", type=int, default=1)
    p.add_argument("--pattern", default="j-j-jjjj", help="stutter: 16th-note pattern using j")
    p.add_argument("--semitones", type=int, default=1, help="lift: semitones up from --at-bar")
    p.add_argument("--verbose", action="store_true")
    p.set_defaults(func=cmd_mix_edit)

    p = mix.add_parser("review", help="open the local review page (play, A/B, comment on time ranges)")
    p.add_argument("slug")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-open", action="store_true")
    p.set_defaults(func=cmd_mix_review)

    p = common(mix.add_parser("comment", help="add a comment to a render from the command line"))
    p.add_argument("slug")
    p.add_argument("text")
    p.add_argument("--at", default="0", help="time (m:ss or seconds)")
    p.add_argument("--to", help="end time for a range")
    p.add_argument("--bar", type=float, help="output bar instead of --at")
    p.add_argument("--end-bar", type=float)
    p.add_argument("--tag", default="other")
    p.add_argument("--run")
    p.set_defaults(func=cmd_mix_comment)

    p = common(mix.add_parser("feedback", help="list comments and verdicts (open ones by default)"))
    p.add_argument("slug")
    p.add_argument("--run")
    p.add_argument("--all", action="store_true", help="every render, not just the latest")
    p.add_argument("--include-resolved", action="store_true")
    p.set_defaults(func=cmd_mix_feedback)

    p = common(mix.add_parser("resolve", help="mark comments resolved after revising the plan"))
    p.add_argument("slug")
    p.add_argument("ids", nargs="+")
    p.add_argument("--status", choices=("resolved", "wontfix", "open"), default="resolved")
    p.add_argument("--note")
    p.set_defaults(func=cmd_mix_resolve)

    sets = sub.add_parser("set", help="DJ set helpers").add_subparsers(dest="action", required=True)
    p = common(sets.add_parser("order", help="best play order by key, tempo, and energy flow"))
    p.add_argument("tracks", nargs="+")
    p.add_argument("--start", help="track to open with")
    p.set_defaults(func=cmd_set_order)

    p = common(mix.add_parser("export", help="aligned clip WAVs + tempo.mid for Logic/Ableton (needs a --clips render)"))
    p.add_argument("slug")
    p.add_argument("--run")
    p.set_defaults(func=cmd_mix_export)

    p = common(mix.add_parser("video", help="visualizer video with a title card (vertical for Shorts by default)"))
    p.add_argument("slug")
    p.add_argument("--run")
    p.add_argument("--landscape", action="store_true", help="1920x1080 instead of 1080x1920")
    p.add_argument("--subtitle", help="use | to split lines on the vertical card")
    p.add_argument("--start-bar", type=float, help="cut a short clip starting at this bar")
    p.add_argument("--end-bar", type=float)
    p.set_defaults(func=cmd_mix_video)

    p = common(sub.add_parser("auto", help="two audio files (or track ids) in, a finished mashup out: separate, "
                                           "draft, render, and fix what QA finds"))
    p.add_argument("vocal", help="the song whose vocal you want (audio file or track id)")
    p.add_argument("bed", help="the song whose beat you want (audio file or track id)")
    p.add_argument("--slug", help="mix name (default: <vocal>-x-<bed>)")
    p.add_argument("--title")
    p.add_argument("--rounds", type=int, default=2, help="QA fix rounds after the first render (default 2)")
    p.add_argument("--force", action="store_true", help="make it even if the fit check says the beat is a poor fit")
    p.set_defaults(func=cmd_auto)

    p = common(sub.add_parser("fit", help="one-minute check: will this vocal sit on this beat? (files or track ids)"))
    p.add_argument("vocal")
    p.add_argument("bed")
    p.set_defaults(func=cmd_fit)

    p = common(sub.add_parser("taste", help="your mixing defaults and preferences (read by scaffolds and agents)"))
    p.add_argument("action", nargs="?", choices=("show", "set", "add"), default="show")
    p.add_argument("value", nargs="?", help="set: name=value; add: free-text preference")
    p.set_defaults(func=cmd_taste)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except (FileNotFoundError, FileExistsError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
