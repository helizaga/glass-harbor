"""Listener feedback: timestamped comments on renders, verdicts, and the taste file that scaffolds read.

Comments live next to the render (``runs/<slug>/<stamp>/feedback.json``) and are mapped to output bars and the
clips playing there, so the agent can turn "vocal late at 1:12" into "clip vox2, bar 37".
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from pathlib import Path
from typing import Any

import numpy as np

from glass_harbor import audio as A
from glass_harbor.paths import runs_dir, workspace_root
from glass_harbor.tempo import TempoMap

TAGS = ("timing", "level", "vocal", "transition", "chop", "eq", "keep", "other")
TASTE_DEFAULTS: dict[str, Any] = {
    "master_lufs": -9.0,
    "edm_blend_bars": 16,
    "hiphop_blend_bars": 8,
    "vocal_highpass_hz": 110,
    "duck_db": 3.0,
}


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def list_runs(slug: str) -> list[Path]:
    root = runs_dir(slug)
    if not root.exists():
        return []
    return sorted(p for p in root.iterdir() if (p / "render.json").exists())


def run_timeline(run: Path) -> dict[str, Any]:
    """Bar start times (seconds in the rendered file) and clip spans for a render."""
    report = json.loads((run / "render.json").read_text())
    plan = json.loads((run / "plan.json").read_text())
    bpb = plan.get("beats_per_bar", 4)
    tempo = TempoMap.from_plan(plan, bpb)
    offset = float(report.get("timeline_offset_s", 0.0))
    start_bar = (report.get("range") or {}).get("start_bar")
    crop = tempo.time_at((start_bar - 1) * bpb) + offset if start_bar else 0.0
    duration = float(report["duration_s"])
    bars = []
    bar = 1
    while True:
        t = tempo.time_at((bar - 1) * bpb) + offset - crop
        if t > duration:
            break
        if t >= -1e-6:
            bars.append({"bar": bar, "t": round(t, 4)})
        bar += 1
    clips = [{"id": c["id"], "track": c["track"], "stem": c["stem"], "start": c["start_s"],
              "end": round(c["start_s"] + c["length_s"], 4)} for c in report["clips"]]
    return {"duration": duration, "bars": bars, "clips": clips, "title": report.get("title", ""),
            "tempo": report.get("tempo", "")}


def bar_at(timeline: dict[str, Any], seconds: float) -> float:
    bars = timeline["bars"]
    if not bars:
        return 1.0
    times = [b["t"] for b in bars]
    numbers = [b["bar"] for b in bars]
    if seconds <= times[0]:
        return float(numbers[0])
    for (t0, n0), (t1, _) in zip(zip(times, numbers), zip(times[1:], numbers[1:])):
        if t0 <= seconds < t1:
            return n0 + (seconds - t0) / (t1 - t0)
    last_len = (times[-1] - times[-2]) if len(times) > 1 else 2.0
    return numbers[-1] + (seconds - times[-1]) / last_len


def peaks(run: Path, buckets: int = 2400) -> list[float]:
    cache = run / "peaks.json"
    if cache.exists():
        return json.loads(cache.read_text())
    audio = A.mono(A.load(run / "mix.wav"))
    edges = np.linspace(0, audio.size, buckets + 1).astype(int)
    values = [float(np.max(np.abs(audio[a:b]))) if b > a else 0.0 for a, b in zip(edges[:-1], edges[1:])]
    data = [round(v, 4) for v in values]
    cache.write_text(json.dumps(data))
    return data


def _feedback_path(run: Path) -> Path:
    return run / "feedback.json"


def load_feedback(run: Path) -> dict[str, Any]:
    path = _feedback_path(run)
    if path.exists():
        return json.loads(path.read_text())
    return {"comments": [], "verdict": None}


def save_feedback(run: Path, data: dict[str, Any]) -> None:
    _feedback_path(run).write_text(json.dumps(data, indent=2) + "\n")


def add_comment(run: Path, *, time_s: float, text: str, tag: str = "other", end_s: float | None = None) -> dict:
    if tag not in TAGS:
        raise ValueError(f"tag must be one of {', '.join(TAGS)}")
    if not text.strip():
        raise ValueError("comment text is empty")
    timeline = run_timeline(run)
    end = end_s if end_s is not None and end_s > time_s else time_s
    active = [c["id"] for c in timeline["clips"] if c["start"] <= end and c["end"] >= time_s]
    comment = {
        "id": uuid.uuid4().hex[:8],
        "time_s": round(time_s, 3),
        "end_s": round(end, 3),
        "bar": round(bar_at(timeline, time_s), 2),
        "end_bar": round(bar_at(timeline, end), 2),
        "clips": active,
        "tag": tag,
        "text": text.strip(),
        "status": "open",
        "created_at": _now(),
    }
    data = load_feedback(run)
    data["comments"].append(comment)
    save_feedback(run, data)
    return comment


def set_comment_status(run: Path, comment_id: str, status: str, note: str = "") -> dict:
    if status not in ("open", "resolved", "wontfix"):
        raise ValueError("status must be open, resolved, or wontfix")
    data = load_feedback(run)
    for comment in data["comments"]:
        if comment["id"] == comment_id:
            comment["status"] = status
            if note:
                comment["resolution"] = note
            save_feedback(run, data)
            return comment
    raise KeyError(f"No comment {comment_id} in {run}")


def delete_comment(run: Path, comment_id: str) -> None:
    data = load_feedback(run)
    data["comments"] = [c for c in data["comments"] if c["id"] != comment_id]
    save_feedback(run, data)


def set_verdict(run: Path, slug: str, verdict: str, note: str = "") -> dict:
    if verdict not in ("approve", "reject"):
        raise ValueError("verdict must be approve or reject")
    data = load_feedback(run)
    data["verdict"] = {"verdict": verdict, "note": note, "at": _now()}
    save_feedback(run, data)
    taste = load_taste()
    taste.setdefault("history", []).append({"slug": slug, "run": run.name, "verdict": verdict, "note": note,
                                            "at": _now()})
    save_taste(taste)
    return data["verdict"]


# ---------------------------------------------------------------- taste

def taste_path() -> Path:
    return workspace_root() / "taste.json"


def load_taste() -> dict[str, Any]:
    path = taste_path()
    data = json.loads(path.read_text()) if path.exists() else {}
    data.setdefault("defaults", {})
    data.setdefault("preferences", [])
    data.setdefault("history", [])
    return data


def save_taste(data: dict[str, Any]) -> None:
    taste_path().write_text(json.dumps(data, indent=2) + "\n")


def taste_default(name: str) -> Any:
    return load_taste()["defaults"].get(name, TASTE_DEFAULTS[name])


def open_comments(slug: str, run: Path | None = None) -> list[dict[str, Any]]:
    runs = [run] if run else list_runs(slug)[-1:]
    out = []
    for r in runs:
        for comment in load_feedback(r)["comments"]:
            if comment["status"] == "open":
                out.append({**comment, "run": r.name})
    return out
