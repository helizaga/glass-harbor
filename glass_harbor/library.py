"""The local track library: decoded audio, stems, and analysis per track (gitignored, never committed)."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

import numpy as np

from glass_harbor import audio as A
from glass_harbor.grid import Grid
from glass_harbor.paths import library_dir, require_slug, slugify, track_dir

STEM_NAMES = ("vocals", "instrumental", "drums", "bass", "other")
AUDIO_FILE = "audio.flac"
_JUNK = re.compile(r"\(getmp3\.pro\)|y2mate\.is|tomp3\.cc|\[?official (audio|video|music video)\]?|\(?lyrics?\)?|-\w{11}-\d+k-\d+", re.I)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def suggest_id(path: Path) -> str:
    stem = _JUNK.sub(" ", path.stem)
    return slugify(stem)


def list_tracks() -> list[str]:
    root = library_dir()
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir() if (p / "track.json").exists())


def find_by_hash(digest: str) -> str | None:
    for track_id in list_tracks():
        if load_meta(track_id).get("sha256") == digest:
            return track_id
    return None


def load_meta(track_id: str) -> dict[str, Any]:
    path = track_dir(track_id) / "track.json"
    if not path.exists():
        raise FileNotFoundError(f"Track {track_id!r} is not in the library (glass-harbor track add <file>).")
    return _read_json(path)


def save_meta(track_id: str, meta: dict[str, Any]) -> None:
    _write_json(track_dir(track_id) / "track.json", meta)


def audio_path(track_id: str) -> Path:
    return track_dir(track_id) / AUDIO_FILE


def stem_path(track_id: str, stem: str) -> Path:
    return track_dir(track_id) / "stems" / f"{stem}.flac"


def available_stems(track_id: str) -> list[str]:
    return [name for name in STEM_NAMES if stem_path(track_id, name).exists()]


def load_audio(track_id: str, stem: str = "mix") -> np.ndarray:
    if stem == "mix":
        return A.load(audio_path(track_id))
    path = stem_path(track_id, stem)
    if not path.exists():
        raise FileNotFoundError(f"Track {track_id!r} has no {stem!r} stem (glass-harbor track separate {track_id}).")
    return A.load(path)


def analysis_path(track_id: str) -> Path:
    return track_dir(track_id) / "analysis.json"


def load_analysis(track_id: str) -> dict[str, Any]:
    path = analysis_path(track_id)
    if not path.exists():
        raise FileNotFoundError(f"Track {track_id!r} has no analysis yet (glass-harbor track analyze {track_id}).")
    return _read_json(path)


def save_analysis(track_id: str, analysis: dict[str, Any]) -> None:
    _write_json(analysis_path(track_id), analysis)


def load_grid(track_id: str) -> Grid:
    return Grid.from_dict(load_analysis(track_id)["grid"])


FFPROBE_TIMEOUT_S = 15


def file_tags(path: Path) -> dict[str, str]:
    """Artist and title from the file's own tags (ffprobe), lowercase keys; empty when unavailable."""
    import subprocess

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {}
    try:
        result = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format_tags=artist,title", "-of", "json",
                                 str(path)], capture_output=True, text=True, check=False, timeout=FFPROBE_TIMEOUT_S)
        tags = json.loads(result.stdout or "{}").get("format", {}).get("tags", {})
    except (subprocess.TimeoutExpired, ValueError):
        return {}
    return {k.lower(): v.strip() for k, v in tags.items() if k.lower() in ("artist", "title") and v.strip()}


def add_track(
    source: Path,
    *,
    track_id: str | None = None,
    title: str | None = None,
    artist: str | None = None,
    stems: dict[str, Path] | None = None,
) -> tuple[str, bool]:
    """Decode ``source`` into the library. Returns (track_id, created)."""
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"No such audio file: {source}")
    digest = sha256_file(source)
    existing = find_by_hash(digest)
    if existing and not stems:
        return existing, False

    track_id = require_slug(track_id or existing or suggest_id(source), "track id")
    if existing is None and (track_dir(track_id) / "track.json").exists():
        raise FileExistsError(f"Track id {track_id!r} is already used by another file; pass --id.")

    folder = track_dir(track_id)
    folder.mkdir(parents=True, exist_ok=True)
    meta = load_meta(track_id) if existing else {}
    if not existing:
        tags = file_tags(source)
        title = title or tags.get("title")
        artist = artist or tags.get("artist")
        audio = A.load(source)
        A.save(audio_path(track_id), audio, subtype="PCM_24")
        meta = {
            "id": track_id,
            "title": title or source.stem,
            "artist": artist or "",
            "source_file": source.name,
            "sha256": digest,
            "duration": round(audio.shape[0] / A.SR, 4),
            "added_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "stems": {},
        }
    for name, path in (stems or {}).items():
        if name not in STEM_NAMES:
            raise ValueError(f"Unknown stem {name!r}; expected one of {', '.join(STEM_NAMES)}")
        stem_audio = A.load(Path(path).expanduser())
        A.save(stem_path(track_id, name), stem_audio, subtype="PCM_24")
        meta.setdefault("stems", {})[name] = {"backend": "provided", "source_file": Path(path).name}
    save_meta(track_id, meta)
    return track_id, existing is None


def remove_stems(track_id: str, names: list[str]) -> None:
    for name in names:
        path = stem_path(track_id, name)
        if path.exists():
            path.unlink()


def copy_stem_file(track_id: str, name: str, source: Path) -> None:
    target = stem_path(track_id, name)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    raw = target.parent / "raw" / target.name
    if raw.exists():  # a fresh separation replaces the pre-cleanup copy too
        raw.unlink()
    backing = target.parent / "raw" / f"{name}-backing.flac"
    if backing.exists():  # set aside by lead cleanup of the previous stem
        backing.unlink()
    meta_path = track_dir(track_id) / "track.json"
    if meta_path.exists():
        meta = _read_json(meta_path)
        info = meta.get("stems", {}).get(name, {})
        info.pop("cleaned", None)
        info.pop("cleaned_steps", None)
        _write_json(meta_path, meta)
