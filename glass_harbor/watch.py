"""A watch folder: queue a pairing, drop the files, get the mix.

``glass-harbor queue add <vocal> <beat>`` records a pairing by name (words from the file names, or library ids).
``glass-harbor watch`` checks the folder (default ~/Downloads); once both files of a queued pairing are there and
finished downloading, it runs the fit check and, if the beat passes, the whole one-command mix. Results (or the fit
check's reasons) go back into the queue and to a macOS notification.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from glass_harbor import library
from glass_harbor.paths import workspace_root

AUDIO = {".flac", ".wav", ".aif", ".aiff", ".mp3", ".m4a", ".aac", ".ogg", ".opus"}
PARTIAL = {".crdownload", ".part", ".download", ".tmp"}
DEFAULT_FOLDER = Path("~/Downloads").expanduser()

Log = Callable[[str], None]


def queue_path() -> Path:
    return workspace_root() / "queue.json"


def load_queue() -> list[dict[str, Any]]:
    path = queue_path()
    return json.loads(path.read_text()) if path.exists() else []


def save_queue(items: list[dict[str, Any]]) -> None:
    queue_path().write_text(json.dumps(items, indent=2) + "\n")


def add(vocal: str, beat: str, *, slug: str | None = None, title: str = "") -> dict[str, Any]:
    items = load_queue()
    item = {"id": f"q{len(items) + 1}", "vocal": vocal, "beat": beat, "slug": slug, "title": title,
            "status": "waiting", "added_at": dt.datetime.now().isoformat(timespec="seconds")}
    items.append(item)
    save_queue(items)
    return item


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def find(hint: str, folder: Path) -> str | None:
    """A library track id, an existing path, or the newest finished audio file in ``folder`` whose name has every
    word of ``hint``."""
    if (library.track_dir(hint) / "track.json").exists():
        return hint
    path = Path(hint).expanduser()
    if path.is_file():
        return str(path)
    wanted = _words(hint)
    if not wanted or not folder.is_dir():
        return None
    matches = [f for f in folder.iterdir()
               if f.is_file() and f.suffix.lower() in AUDIO and all(w in _words(f.stem) for w in wanted)]
    return str(max(matches, key=lambda f: f.stat().st_mtime)) if matches else None


def _settled(path: str, settle_s: float) -> bool:
    """Finished downloading: no partial-download twin next to it, and the size holds still for ``settle_s``."""
    file = Path(path)
    if not file.is_file():
        return True  # a library id
    if any(file.with_name(file.name + suffix).exists() for suffix in PARTIAL):
        return False
    size = file.stat().st_size
    if settle_s:
        time.sleep(settle_s)
    return file.stat().st_size == size and size > 0


def notify(title: str, message: str) -> None:
    """A local macOS notification (nothing is sent anywhere)."""
    script = f'display notification {json.dumps(message)} with title {json.dumps(title)}'
    subprocess.run(["osascript", "-e", script], capture_output=True, check=False)


def run_once(*, folder: Path = DEFAULT_FOLDER, settle_s: float = 2.0, log: Log = print,
             runner: Callable[..., dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Process every waiting pairing whose files are both present. Returns the items handled this pass."""
    from glass_harbor.auto import PoorFit, run_auto

    runner = runner or run_auto
    items = load_queue()
    handled = []
    for item in items:
        if item["status"] != "waiting":
            continue
        vocal, beat = find(item["vocal"], folder), find(item["beat"], folder)
        if not (vocal and beat and _settled(vocal, settle_s) and _settled(beat, settle_s)):
            continue
        item.update(status="running", vocal_file=vocal, beat_file=beat)
        save_queue(items)
        log(f"{item['id']}: {Path(vocal).name} over {Path(beat).name}")
        try:
            result = runner(vocal, beat, slug=item.get("slug"), title=item.get("title") or "", log=log)
            item.update(status="done", phone=result.get("phone"), brief=result.get("brief"), slug=result.get("slug"))
            notify("Mix ready", f"{result.get('slug')}: {Path(result.get('phone') or '').name}")
        except PoorFit as error:
            item.update(status="poor fit", reason=str(error))
            notify("Beat doesn't fit", str(error)[:200])
        except Exception as error:  # noqa: BLE001 - one failed pairing must not stop the watcher
            item.update(status="failed", reason=f"{error.__class__.__name__}: {error}"[:500])
            notify("Mix failed", str(error)[:200])
        item["finished_at"] = dt.datetime.now().isoformat(timespec="seconds")
        save_queue(items)
        handled.append(item)
    return handled


def watch(*, folder: Path = DEFAULT_FOLDER, interval: float = 10.0, log: Log = print) -> None:
    """Keep checking until no pairing is waiting."""
    log(f"watching {folder} for {sum(1 for i in load_queue() if i['status'] == 'waiting')} queued pairing(s)")
    while any(i["status"] == "waiting" for i in load_queue()):
        run_once(folder=folder, log=log)
        if any(i["status"] == "waiting" for i in load_queue()):
            time.sleep(interval)
    log("nothing left in the queue")
