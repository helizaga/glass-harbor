"""A watch folder: queue a pairing, drop the files, get the mix.

``glass-harbor queue add <vocal> <beat>`` records a pairing by name (words from the file names, or library ids).
``glass-harbor watch`` checks the folder (default ~/Downloads); once both files of a queued pairing are there and
finished downloading, it runs the fit check and, if the beat passes, the whole one-command mix. Results (or the fit
check's reasons) go back into the queue and to a macOS notification.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Iterator

from glass_harbor import library
from glass_harbor.paths import workspace_root

AUDIO = {".flac", ".wav", ".aif", ".aiff", ".mp3", ".m4a", ".aac", ".ogg", ".opus"}
PARTIAL = {".crdownload", ".part", ".download", ".tmp"}
DEFAULT_FOLDER = Path("~/Downloads").expanduser()

Log = Callable[[str], None]


def queue_path() -> Path:
    return workspace_root() / "queue.json"


LOCK_TIMEOUT_S = 30.0
LEASE_S = 3 * 3600.0  # a pairing "running" longer than this without a live owner is retried


def load_queue() -> list[dict[str, Any]]:
    path = queue_path()
    return json.loads(path.read_text()) if path.exists() else []


def save_queue(items: list[dict[str, Any]]) -> None:
    """Write to a temporary file and swap it in, so a reader never sees half a queue."""
    path = queue_path()
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(items, indent=2) + "\n")
    os.replace(tmp, path)


def _try_lock(fd: int) -> None:
    """Take the lock without waiting (OSError when another holder has it). The OS drops it if the holder dies."""
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(fd: int) -> None:
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)


@contextlib.contextmanager
def locked() -> Iterator[None]:
    """Serialize read-modify-write of the queue across processes. The lock belongs to the open file, so the OS
    releases it when its owner exits, even on a crash or kill; the lock file itself stays (deleting it would race)."""
    lock = queue_path().with_name(queue_path().name + ".lock")
    fd = os.open(lock, os.O_CREAT | os.O_RDWR)
    try:
        deadline = time.monotonic() + LOCK_TIMEOUT_S
        while True:
            try:
                _try_lock(fd)
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise TimeoutError(f"the queue is locked by another process ({lock})") from None
                time.sleep(0.05)
        try:
            yield
        finally:
            _unlock(fd)
    finally:
        os.close(fd)


def _update(item_id: str, **fields: Any) -> dict[str, Any]:
    """Change one pairing in the current queue (never a stale copy, so additions made meanwhile survive)."""
    with locked():
        items = load_queue()
        item = next(i for i in items if i["id"] == item_id)
        item.update(fields)
        save_queue(items)
        return dict(item)


def _claim(item_id: str, **fields: Any) -> bool:
    """Mark a waiting pairing running, in one locked step; False when another watcher claimed it first."""
    with locked():
        items = load_queue()
        item = next((i for i in items if i["id"] == item_id), None)
        if item is None or item["status"] != "waiting":
            return False
        item.update(status="running", **fields)
        save_queue(items)
        return True


def add(vocal: str, beat: str, *, slug: str | None = None, title: str = "") -> dict[str, Any]:
    with locked():
        items = load_queue()
        number = max((int(i["id"][1:]) for i in items if i["id"][1:].isdigit()), default=0) + 1
        item = {"id": f"q{number}", "vocal": vocal, "beat": beat, "slug": slug, "title": title,
                "status": "waiting", "added_at": dt.datetime.now().isoformat(timespec="seconds")}
        items.append(item)
        save_queue(items)
    return item


def _owner_alive(item: dict[str, Any]) -> bool:
    """Whether the process that started a running pairing still exists (by pid; by lease age where pids can't
    be checked)."""
    pid = item.get("pid")
    if pid and os.name == "posix":
        try:
            os.kill(int(pid), 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
    started = item.get("started_at")
    if not started:
        return False
    return (dt.datetime.now() - dt.datetime.fromisoformat(started)).total_seconds() < LEASE_S


def recover_stale() -> list[str]:
    """Put pairings whose watcher died mid-mix back to waiting."""
    with locked():
        items = load_queue()
        stale = [i for i in items if i["status"] == "running" and not _owner_alive(i)]
        for item in stale:
            item.update(status="waiting", note="retried after an interrupted run")
        if stale:
            save_queue(items)
    return [i["id"] for i in stale]


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
    for item_id in recover_stale():
        log(f"{item_id}: the last run was interrupted; retrying")
    handled = []
    for item in load_queue():
        if item["status"] != "waiting":
            continue
        vocal, beat = find(item["vocal"], folder), find(item["beat"], folder)
        if not (vocal and beat and _settled(vocal, settle_s) and _settled(beat, settle_s)):
            continue
        if vocal == beat and _words(item["vocal"]) != _words(item["beat"]):
            continue  # both names matched one file: wait for the other one to arrive
        if not _claim(item["id"], vocal_file=vocal, beat_file=beat, pid=os.getpid(),
                      started_at=dt.datetime.now().isoformat(timespec="seconds")):
            continue  # another watcher took it between our read and now
        log(f"{item['id']}: {Path(vocal).name} over {Path(beat).name}")
        try:
            result = runner(vocal, beat, slug=item.get("slug"), title=item.get("title") or "", log=log)
            outcome = {"status": "done", "phone": result.get("phone"), "brief": result.get("brief"),
                       "slug": result.get("slug")}
            notify("Mix ready", f"{result.get('slug')}: {Path(result.get('phone') or '').name}")
        except PoorFit as error:
            outcome = {"status": "poor fit", "reason": str(error)}
            notify("Beat doesn't fit", str(error)[:200])
        except Exception as error:  # noqa: BLE001 - one failed pairing must not stop the watcher
            outcome = {"status": "failed", "reason": f"{error.__class__.__name__}: {error}"[:500]}
            notify("Mix failed", str(error)[:200])
        handled.append(_update(item["id"], **outcome, finished_at=dt.datetime.now().isoformat(timespec="seconds")))
    return handled


def watch(*, folder: Path = DEFAULT_FOLDER, interval: float = 10.0, log: Log = print,
          passes: int | None = None) -> None:
    """Keep checking until interrupted (``passes`` limits it, for tests); pairings queued later are picked up."""
    log(f"watching {folder} (Ctrl-C to stop); {sum(1 for i in load_queue() if i['status'] == 'waiting')} "
        "pairing(s) waiting")
    done = 0
    while passes is None or done < passes:
        run_once(folder=folder, log=log)
        done += 1
        if passes is None or done < passes:
            time.sleep(interval)
