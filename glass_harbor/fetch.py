"""Fetch a track only through the artist's own free download.

SoundCloud: when the uploader turned on downloads, yt-dlp exposes that original file as the ``download`` format;
that file (often WAV or 320 kbps) is fetched and nothing else. Tracks without it are refused: ripping the stream
would take music the artist chose not to give away. Bandcamp free and name-your-price downloads go through
Bandcamp's own download page (sometimes with an email step), so they stay a click for the user.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_FOLDER = Path("~/Downloads").expanduser()


class NoFreeDownload(ValueError):
    """The artist did not make this track free to download."""


def _yt_dlp() -> str:
    binary = shutil.which("yt-dlp")
    if not binary:
        raise RuntimeError("fetch needs yt-dlp: brew install yt-dlp (or pip install yt-dlp)")
    return binary


def free_download_format(info: dict) -> dict | None:
    """The uploader's original file, present only when they enabled downloads."""
    return next((f for f in info.get("formats") or [] if f.get("format_id") == "download"), None)


def fetch(url: str, *, folder: Path = DEFAULT_FOLDER, log=print) -> Path:
    host = (urlparse(url).hostname or "").lower()
    if host.endswith("bandcamp.com"):
        raise NoFreeDownload("Bandcamp free and name-your-price downloads go through Bandcamp's own download page: "
                             f"open {url}, choose Buy / Free Download, enter $0, and save the file to {folder}")
    if not (host == "soundcloud.com" or host.endswith(".soundcloud.com")):
        raise NoFreeDownload("only SoundCloud tracks with the artist's free download turned on are fetched "
                             "automatically")
    binary = _yt_dlp()
    probe = subprocess.run([binary, "--dump-single-json", "--no-playlist", "--no-warnings", url],
                           capture_output=True, text=True, check=False)
    if probe.returncode != 0:
        raise RuntimeError(f"could not read {url}: {probe.stderr.strip()[-300:]}")
    info = json.loads(probe.stdout)
    original = free_download_format(info)
    if original is None:
        raise NoFreeDownload(f"{info.get('title', url)} has no free download from the artist; buy it or ask the "
                             "artist (streams are not ripped)")
    folder.mkdir(parents=True, exist_ok=True)
    log(f"fetching the artist's download of {info.get('uploader', '?')} - {info.get('title', '?')}")
    done = subprocess.run([binary, "-f", "download", "--no-playlist", "--no-warnings", "--print", "after_move:filepath",
                           "-o", str(folder / "%(uploader)s - %(title)s.%(ext)s"), url],
                          capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise RuntimeError(f"download failed: {done.stderr.strip()[-300:]}")
    path = Path(done.stdout.strip().splitlines()[-1])
    log(f"saved {path}")
    return path
