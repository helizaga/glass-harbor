"""Hand-offs out of the engine: set ordering, DAW export (aligned stems + tempo-map MIDI), and a video render."""

from __future__ import annotations

import itertools
import json
import shutil
import struct
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from glass_harbor import audio as A
from glass_harbor import compat, library
from glass_harbor.keys import Key, camelot_distance
from glass_harbor.tempo import TempoMap

# ---------------------------------------------------------------- set ordering


def _energy(analysis: dict) -> float:
    levels = sorted(analysis.get("bar_db") or [-20.0])
    return float(np.mean(levels[len(levels) // 2:]))


def transition_cost(a: dict, b: dict) -> float:
    """Lower = smoother: harmonic distance, tempo stretch (half/double aware), and big energy drops."""
    key_a = Key(int(a["key"]["tonic"]), a["key"]["mode"])
    key_b = Key(int(b["key"]["tonic"]), b["key"]["mode"])
    _, stretch = compat.tempo_options(b["bpm"], a["bpm"])[0]
    energy_drop = max(0.0, _energy(a) - _energy(b) - 2.0)
    return camelot_distance(key_a, key_b) + 0.15 * abs(stretch) + 0.3 * energy_drop


def order_tracks(track_ids: list[str], start: str | None = None) -> tuple[list[str], float]:
    analyses = {t: library.load_analysis(t) for t in track_ids}
    cost = {(a, b): transition_cost(analyses[a], analyses[b]) for a in track_ids for b in track_ids if a != b}

    def total(order: list[str]) -> float:
        return sum(cost[(a, b)] for a, b in zip(order, order[1:]))

    pool = [t for t in track_ids if t != start]
    if len(track_ids) <= 8:
        candidates = ([start, *p] for p in itertools.permutations(pool)) if start else itertools.permutations(track_ids)
        best = min((list(c) for c in candidates), key=total)
        return best, total(best)
    order = [start or track_ids[0]]
    remaining = [t for t in track_ids if t != order[0]]
    while remaining:
        nxt = min(remaining, key=lambda t: cost[(order[-1], t)])
        order.append(nxt)
        remaining.remove(nxt)
    improved = True
    while improved:  # 2-opt
        improved = False
        for i in range(1, len(order) - 1):
            for j in range(i + 1, len(order)):
                candidate = order[:i] + order[i:j + 1][::-1] + order[j + 1:]
                if (start is None or candidate[0] == start) and total(candidate) < total(order) - 1e-9:
                    order, improved = candidate, True
    return order, total(order)


# ---------------------------------------------------------------- DAW export


def _vlq(value: int) -> bytes:
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(out))


def tempo_midi(plan: dict[str, Any], *, lead_beats: float = 0.0, ppq: int = 480) -> bytes:
    """Type-0 MIDI with the plan's time signature and tempo map (ramps as per-beat steps)."""
    bpb = plan.get("beats_per_bar", 4)
    tempo = TempoMap.from_plan(plan, bpb)
    last = max(p.beat for p in tempo.points) + 16 * bpb
    events = [(0, b"\xff\x58\x04" + bytes([bpb, 2, 24, 8]))]
    beat, previous = -lead_beats, None
    while beat <= last:
        bpm = tempo.bpm_at(max(beat, 0.0))
        if previous is None or abs(bpm - previous) > 1e-3:
            micro = int(round(60_000_000 / bpm))
            events.append((int(round((beat + lead_beats) * ppq)), b"\xff\x51\x03" + micro.to_bytes(3, "big")))
            previous = bpm
        beat += 1
    track = bytearray()
    cursor = 0
    for tick, payload in sorted(events, key=lambda e: e[0]):
        track += _vlq(tick - cursor) + payload
        cursor = tick
    track += b"\x00\xff\x2f\x00"
    return b"MThd" + struct.pack(">IHHH", 6, 0, 1, ppq) + b"MTrk" + struct.pack(">I", len(track)) + bytes(track)


def export_daw(run: Path) -> Path:
    """runs/<slug>/<stamp>/daw/: every clip as a WAV starting on a bar line + tempo.mid + README."""
    report = json.loads((run / "render.json").read_text())
    plan = json.loads((run / "plan.json").read_text())
    clips_dir = run / "clips"
    if not clips_dir.exists():
        raise FileNotFoundError("render with --clips first (glass-harbor mix render <slug> --clips)")
    bpb = plan.get("beats_per_bar", 4)
    tempo = TempoMap.from_plan(plan, bpb)
    offset = float(report.get("timeline_offset_s", 0.0))
    # Pickups before bar 1: pad the files back to the previous bar line so the DAW grid and the audio agree.
    bar_seconds = -tempo.time_at(-bpb)
    lead_bars = int(np.ceil(offset / bar_seconds - 1e-9)) if offset > 0 else 0
    lead_beats = float(lead_bars * bpb)
    pad = int(round((-tempo.time_at(-lead_beats) - offset) * A.SR)) if lead_bars else 0
    out = run / "daw"
    out.mkdir(exist_ok=True)
    for wav in sorted(clips_dir.glob("*.wav")):
        audio = A.load(wav)
        A.save(out / wav.name, np.pad(audio, ((pad, 0), (0, 0))) if pad else audio, subtype="FLOAT")
    (out / "tempo.mid").write_bytes(tempo_midi(plan, lead_beats=lead_beats))
    first = f"{lead_bars} bar(s) before bar 1 (pickups)" if lead_bars else "bar 1"
    (out / "README.txt").write_text(
        f"{plan.get('title', '')}\n\n"
        f"1. New project at 44.1 kHz. Import tempo.mid and take its tempo + time signature.\n"
        f"2. Drag every WAV in at the very start of the timeline; the files start at {first}.\n"
        f"3. Tempo: {report.get('tempo')}.\n")
    return out


# ---------------------------------------------------------------- video


def _title_card(path: Path, title: str, subtitle: str, size: tuple[int, int]) -> None:
    import textwrap

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    width, height = size
    vertical = width < 1500
    title_lines = textwrap.fill(title, 22 if vertical else 40)
    sub_lines = "\n".join(part.strip() for part in subtitle.split("|") if part.strip()) if vertical else subtitle
    fig = plt.figure(figsize=(width / 100, height / 100), dpi=100)
    fig.patch.set_alpha(0.0)
    fig.text(0.5, 0.66, title_lines, ha="center", va="center", color="white", fontsize=width / 20,
             fontweight="bold", linespacing=1.1)
    if sub_lines:
        fig.text(0.5, 0.22, sub_lines, ha="center", va="center", color="#9aa0a6", fontsize=width / 40,
                 linespacing=1.35)
    fig.savefig(path, transparent=True)
    plt.close(fig)


def render_video(run: Path, *, vertical: bool = True, subtitle: str = "", start_bar: float | None = None,
                 end_bar: float | None = None) -> Path:
    """Audio-reactive visualizer (constant-Q spectrum) + title card, H.264/AAC, for Shorts/TikTok or YouTube.
    ``start_bar``/``end_bar`` cut a short clip (e.g. the build and drop) on bar lines."""
    from glass_harbor.feedback import run_timeline

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for video")
    report = json.loads((run / "render.json").read_text())
    width, height = (1080, 1920) if vertical else (1920, 1080)
    card_h = 520 if vertical else 260
    viz_h = 1100 if vertical else 760
    _title_card(run / "title.png", report.get("title", ""), subtitle or report.get("tempo", ""), (width, card_h))
    trim: list[str] = []
    suffix = ""
    if start_bar is not None or end_bar is not None:
        bars = {b["bar"]: b["t"] for b in run_timeline(run)["bars"]}
        t0 = bars.get(int(start_bar), 0.0) if start_bar else 0.0
        t1 = bars.get(int(end_bar)) if end_bar else None
        trim = ["-ss", f"{t0:.3f}"] + (["-t", f"{t1 - t0:.3f}"] if t1 else [])
        suffix = f"-bars{int(start_bar or 1)}-{int(end_bar) if end_bar else 'end'}"
    encoder = ["-c:v", "h264_videotoolbox", "-b:v", "6M"] if _has_encoder(ffmpeg, "h264_videotoolbox") \
        else ["-c:v", "libx264", "-crf", "20", "-preset", "medium"]
    target = run / f"video{'-vertical' if vertical else ''}{suffix}.mp4"
    viz_y = (height - viz_h) // 2 + (card_h // 3 if vertical else 60)
    graph = (f"color=c=0x0d0f12:s={width}x{height}:r=30[bg];"
             f"[0:a]showcqt=s={width}x{viz_h}:fps=30:axis=0:bar_g=3:sono_g=4:cscheme=0.15|0.55|1|1|0.35|0.75[viz];"
             f"[bg][viz]overlay=0:{viz_y}:shortest=1[v1];"
             f"[v1][1:v]overlay=0:{60 if vertical else 40}:shortest=1,format=yuv420p[v]")
    cmd = [ffmpeg, "-v", "error", "-y", *trim, "-i", str(run / report["files"]["wav"]), "-loop", "1", "-i",
           str(run / "title.png"), "-filter_complex", graph, "-map", "[v]", "-map", "0:a", *encoder,
           "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", str(target)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.strip()[-800:]}")
    return target


def _has_encoder(ffmpeg: str, name: str) -> bool:
    out = subprocess.run([ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True, check=False).stdout
    return f" {name} " in out
