"""Workspace layout.

Everything lives under one workspace root (the repo by default, or ``GLASS_HARBOR_HOME``):

- ``library/<track-id>/``: decoded source audio, stems, and analysis (gitignored; private audio)
- ``mixes/<slug>/``: agent-authored mix plans and briefs (committed)
- ``runs/<slug>/<stamp>/``: rendered audio and QA reports (gitignored)
"""

from __future__ import annotations

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def workspace_root() -> Path:
    explicit = os.environ.get("GLASS_HARBOR_HOME", "").strip()
    return Path(explicit).expanduser().resolve() if explicit else REPO_ROOT


def library_dir() -> Path:
    return workspace_root() / "library"


def track_dir(track_id: str) -> Path:
    return library_dir() / track_id


def mixes_dir() -> Path:
    return workspace_root() / "mixes"


def mix_dir(slug: str) -> Path:
    return mixes_dir() / slug


def plan_path(slug: str) -> Path:
    return mix_dir(slug) / f"{slug}.mix.json"


def runs_dir(slug: str) -> Path:
    return workspace_root() / "runs" / slug


def model_dir() -> Path:
    explicit = os.environ.get("GLASS_HARBOR_MODEL_DIR", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return Path.home() / ".cache" / "glass-harbor" / "models"


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:64].rstrip("-") or "track"


def require_slug(value: str, what: str = "slug") -> str:
    if not SLUG_PATTERN.match(value):
        raise ValueError(f"Invalid {what} {value!r}: use lowercase letters, digits, and dashes.")
    return value
