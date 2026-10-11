"""Deterministic QA on a rendered mix: loudness, peaks, dead air, pile-ups, and beat alignment of every clip."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from glass_harbor import audio as A

SOURCE_GRID_TOLERANCE_MS = 35.0
WARP_TOLERANCE_MS = 15.0


def _bar_levels(audio: np.ndarray, plan: dict, report: dict) -> list[float]:
    from glass_harbor.tempo import TempoMap

    bpb = plan.get("beats_per_bar", 4)
    tempo = TempoMap.from_plan(plan, bpb)
    offset = float(report.get("timeline_offset_s", 0.0))
    start_bar = (report.get("range") or {}).get("start_bar") or 1
    crop = tempo.time_at((start_bar - 1) * bpb) + offset if (report.get("range") or {}).get("start_bar") else 0.0
    signal = A.mono(audio)
    levels = []
    bar = start_bar
    while True:
        t0 = tempo.time_at((bar - 1) * bpb) + offset - crop
        t1 = tempo.time_at(bar * bpb) + offset - crop
        if t0 * A.SR >= signal.shape[0] - A.SR // 4:
            break
        chunk = signal[max(0, int(t0 * A.SR)): int(t1 * A.SR)]
        levels.append(A.gain_to_db(float(np.sqrt(np.mean(chunk**2)))) if chunk.size else -120.0)
        bar += 1
    return levels


BANDS = ((20, 60, "sub"), (60, 150, "bass"), (150, 400, "low-mid"), (400, 2000, "mid"), (2000, 6000, "presence"),
         (6000, 16000, "air"))


def tonal_balance(audio: np.ndarray) -> dict[str, float]:
    """Share of energy per band in dB relative to the total (spectral shape, independent of loudness)."""
    from scipy.signal import welch

    freqs, psd = welch(A.mono(audio), fs=A.SR, nperseg=8192)
    total = float(np.sum(psd[(freqs >= 20) & (freqs <= 16000)])) + 1e-20
    return {name: round(10 * np.log10(float(np.sum(psd[(freqs >= lo) & (freqs < hi)])) / total + 1e-12), 2)
            for lo, hi, name in BANDS}


def low_end_correlation(audio: np.ndarray, cutoff: float = 120.0) -> float:
    from scipy.signal import butter, sosfiltfilt

    low = sosfiltfilt(butter(4, cutoff, btype="lowpass", fs=A.SR, output="sos"), audio, axis=0)
    left, right = low[:, 0], low[:, 1]
    denom = float(np.sqrt(np.sum(left ** 2) * np.sum(right ** 2))) + 1e-12
    return round(float(np.sum(left * right)) / denom, 3)


def _spans(bars: list[int]) -> str:
    spans, start, prev = [], bars[0], bars[0]
    for bar in bars[1:]:
        if bar != prev + 1:
            spans.append((start, prev))
            start = bar
        prev = bar
    spans.append((start, prev))
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in spans)


def _bar_times(plan: dict, report: dict, count: int) -> list[float]:
    from glass_harbor.tempo import TempoMap

    bpb = plan.get("beats_per_bar", 4)
    tempo = TempoMap.from_plan(plan, bpb)
    offset = float(report.get("timeline_offset_s", 0.0))
    start_bar = (report.get("range") or {}).get("start_bar") or 1
    crop = tempo.time_at((start_bar - 1) * bpb) + offset if (report.get("range") or {}).get("start_bar") else 0.0
    return [tempo.time_at((start_bar - 1 + i) * bpb) + offset - crop for i in range(count + 1)]


def check_run(run_dir: Path) -> dict[str, Any]:
    report = json.loads((run_dir / "render.json").read_text())
    plan = json.loads((run_dir / "plan.json").read_text())
    audio = A.load(run_dir / report["files"]["wav"])
    flags: list[dict[str, str]] = []

    def flag(level: str, where: str, message: str) -> None:
        flags.append({"level": level, "where": where, "message": message})

    lufs = A.integrated_lufs(audio)
    true_peak = A.true_peak_db(audio)
    clipped = int(np.sum(np.abs(audio) >= 0.9999))
    target = float(report.get("master", {}).get("target_lufs", (plan.get("master") or {}).get("lufs", -9.0)))
    if abs(lufs - target) > 1.0:
        flag("warning", "master", f"integrated loudness {lufs:.1f} LUFS misses the {target:.1f} target")
    if true_peak > float((plan.get("master") or {}).get("ceiling_db", -1.0)) + 0.5:
        flag("warning", "master", f"true peak {true_peak:.1f} dBTP is above the ceiling")
    if clipped:
        flag("error", "master", f"{clipped} clipped samples")

    levels = _bar_levels(audio, plan, report)
    start_bar = (report.get("range") or {}).get("start_bar") or 1
    bar_times = _bar_times(plan, report, len(levels) + 1)
    if levels:
        median = float(np.median(levels))
        # A fade-out tail (levels falling to the end) is intended, not dead air.
        tail = len(levels)
        while tail > 1 and levels[tail - 1] <= levels[tail - 2] + 0.5 and levels[tail - 1] < median - 3:
            tail -= 1
        # Quiet bars right before a planned impact are a deliberate break, not dead air.
        impacts = [c["at_bar"] for c in plan.get("clips", []) if c.get("generate") == "impact"]
        planned_breaks = {b for at in impacts for b in range(int(at) - 3, int(at))}
        for i in range(1, min(tail, len(levels) - 1)):
            bar = start_bar + i
            if levels[i] < median - 12 and bar in planned_breaks:
                flag("info", f"bar {bar}", f"break before the drop ({levels[i]:.1f} dB)")
            elif levels[i] < median - 12:
                flag("warning", f"bar {bar}", f"near silence ({levels[i]:.1f} dB vs median {median:.1f} dB)")
            elif levels[i] - levels[i - 1] > 8 and i > 1:
                flag("info", f"bar {bar}", f"jumps {levels[i] - levels[i - 1]:+.1f} dB (intended drop?)")
        loud = []
        for i, value in enumerate(levels):
            t0, t1 = bar_times[i], bar_times[i + 1]
            playing = sum(1 for c in report["clips"] if c["start_s"] < t1 - 0.05 and c["start_s"] + c["length_s"] > t0 + 0.05)
            if playing >= 2 and value > median + 4:
                loud.append(start_bar + i)
        if loud:
            flag("warning", f"bars {loud[0]}-{loud[-1]}" if len(loud) > 1 else f"bar {loud[0]}",
                 "overlap pile-up: mix is >4 dB louder than its median here; pull one side down")

    for clip in report["clips"]:
        src = clip.get("source_grid_offset_ms")
        warp = clip.get("warp_offset_ms")
        # Vocal syllables sit around the beat by design (laid-back or pushed delivery); only rhythm stems
        # say anything about the grid itself.
        if src is not None and abs(src) > SOURCE_GRID_TOLERANCE_MS and clip["stem"] != "vocals":
            flag("warning", clip["id"], f"source beat grid is {src:+.0f} ms off the audible beat for {clip['track']}"
                 " (re-analyze or adjust downbeat_shift)")
        if warp is not None and abs(warp) > WARP_TOLERANCE_MS:
            flag("warning", clip["id"], f"warped clip lands {warp:+.0f} ms off the output grid")
        if abs(clip.get("stretch_pct", 0)) > 8:
            flag("info", clip["id"], f"{clip['stretch_pct']:+.1f}% stretch; listen for artifacts")

    reference = (plan.get("master") or {}).get("reference")
    reference_balance = None
    mix_balance = tonal_balance(audio)
    if reference:
        from glass_harbor import library

        ref_track = reference if isinstance(reference, str) else reference.get("track")
        reference_balance = tonal_balance(library.load_audio(ref_track))
        for name, value in mix_balance.items():
            diff = value - reference_balance[name]
            if abs(diff) > 3.0:
                flag("warning", f"tone: {name}", f"{diff:+.1f} dB vs the reference master {ref_track}")
    correlation = low_end_correlation(audio)
    if correlation < 0.9:
        flag("warning", "low end", f"bass below 120 Hz is not mono (correlation {correlation:.2f})")
    for clip in report["clips"]:
        edges = (clip.get("notes") or {}).get("edges") or {}
        if edges.get("words_cut"):
            flag("warning", clip["id"], f"{edges['words_cut']} word(s) still cut at the clip edges")

    buried = [item["bar"] for item in report.get("vocal_presence", []) if item["db"] < -3.0]
    if buried:
        spans = _spans(buried)
        flag("warning", f"bars {spans}", "vocal is buried under the beat in the 1-4 kHz band; raise the vocal, add duck"
             " to the bed, or cut the bed's mids")

    for issue in report.get("issues", []):
        if issue["level"] == "warning":
            flags.append({"level": "warning", "where": issue["where"], "message": f"plan: {issue['message']}"})

    result = {
        "run": str(run_dir),
        "loudness_lufs": round(lufs, 2),
        "true_peak_db": round(true_peak, 2),
        "clipped_samples": clipped,
        "duration_s": round(audio.shape[0] / A.SR, 2),
        "bar_db": [round(v, 1) for v in levels],
        "tonal_balance": mix_balance,
        "reference_balance": reference_balance,
        "low_end_correlation": correlation,
        "flags": flags,
        "verdict": "fail" if any(f["level"] == "error" for f in flags)
        else "review" if any(f["level"] == "warning" for f in flags) else "pass",
    }
    (run_dir / "qa.json").write_text(json.dumps(result, indent=2) + "\n")
    (run_dir / "qa.md").write_text(render_markdown(result, report))
    return result


def render_markdown(result: dict[str, Any], report: dict[str, Any]) -> str:
    lines = [
        f"# QA: {report.get('title') or Path(result['run']).parent.name}",
        "",
        f"- verdict: **{result['verdict']}**",
        f"- tempo: {report.get('tempo')}",
        f"- duration: {result['duration_s']:.1f}s, loudness {result['loudness_lufs']:.1f} LUFS, "
        f"true peak {result['true_peak_db']:.1f} dBTP",
        "",
        "## Clips",
        "",
        "| clip | track/stem | stretch | semitones | grid (src / warp ms) |",
        "|---|---|---|---|---|",
    ]
    for clip in report["clips"]:
        src = clip.get("source_grid_offset_ms")
        warp = clip.get("warp_offset_ms")
        lines.append(
            f"| {clip['id']} | {clip['track']}/{clip['stem']} | {clip['stretch_pct']:+.1f}% | {clip['semitones']:+d} |"
            f" {'-' if src is None else f'{src:+.0f}'} / {'-' if warp is None else f'{warp:+.0f}'} |"
        )
    lines += ["", "## Flags", ""]
    if not result["flags"]:
        lines.append("None.")
    for item in result["flags"]:
        lines.append(f"- **{item['level']}** {item['where']}: {item['message']}")
    return "\n".join(lines) + "\n"
