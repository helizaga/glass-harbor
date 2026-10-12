"""Reference lyrics from LRCLIB (lrclib.net: free, no account), time-stamped by line.

Whisper gives word timings but mishears sung and autotuned vocals (it made out about half of GLOCK in the finished
mix). The published lyrics give the right words and show which lines really repeat, so choruses that come back only
twice still count as hooks. Whisper stays the source of word timings; the reference corrects what the words are and
which lines are hooks. Stored only in the gitignored library.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from glass_harbor import library

API = "https://lrclib.net/api"
USER_AGENT = "glass-harbor (https://github.com/helizaga/glass-harbor)"
TIMEOUT_S = 15
DURATION_TOLERANCE_S = 4.0
LINE = re.compile(r"^\[(\d+):(\d+(?:\.\d+)?)\]\s*(.*)$")


def reference_path(track_id: str) -> Path:
    return library.track_dir(track_id) / "lyrics_ref.json"


def load_reference(track_id: str) -> dict[str, Any] | None:
    path = reference_path(track_id)
    return json.loads(path.read_text()) if path.exists() else None


def artist_and_title(meta: dict[str, Any]) -> tuple[str, str]:
    """From the track's metadata, else its file name ("01 - Artist - Title.flac")."""
    artist, title = meta.get("artist") or "", meta.get("title") or ""
    stem = Path(meta.get("source_file") or "").stem
    parts = [p.strip() for p in stem.split(" - ") if p.strip()]
    if parts and parts[0].isdigit():
        parts = parts[1:]
    if not artist and len(parts) >= 2:
        artist, title = parts[0], " - ".join(parts[1:])
    elif not title and parts:
        title = parts[-1]
    if " - " in title and not artist:
        artist, title = title.split(" - ", 1)
    return artist, re.sub(r"^\d+\s*-\s*", "", title)


def parse_synced(text: str) -> list[dict[str, Any]]:
    from glass_harbor.lyrics import _normalize

    lines = []
    for raw in text.splitlines():
        match = LINE.match(raw.strip())
        if match and match.group(3).strip():
            lines.append({"time": int(match.group(1)) * 60 + float(match.group(2)), "text": match.group(3).strip(),
                          "norm": _normalize(match.group(3))})
    for line, nxt in zip(lines, lines[1:]):
        line["end"] = nxt["time"]
    if lines:
        lines[-1]["end"] = lines[-1]["time"] + 4.0
    return lines


def _get(path: str, params: dict[str, Any]) -> Any:
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:  # noqa: S310 - fixed https host
        return json.loads(response.read())


def fetch_reference(track_id: str, *, log=print) -> dict[str, Any] | None:
    """Look the track up on LRCLIB and store its synced lyrics. Returns None (and stores nothing) when there is no
    match, no synced version, or no network."""
    meta = library.load_meta(track_id)
    artist, title = artist_and_title(meta)
    duration = float(meta.get("duration") or 0)
    if not title:
        return None
    try:
        found = None
        if artist:
            try:
                found = _get("get", {"artist_name": artist, "track_name": title, "duration": round(duration)})
            except Exception:  # noqa: BLE001 - 404 means no exact match; fall back to search
                found = None
        if not found or not found.get("syncedLyrics"):
            results = _get("search", {"q": f"{artist} {title}".strip()})
            results = [r for r in results if r.get("syncedLyrics")
                       and abs(float(r.get("duration") or 0) - duration) <= DURATION_TOLERANCE_S]
            found = results[0] if results else None
    except Exception as error:  # noqa: BLE001 - offline or the service is down: lyrics stay Whisper-only
        log(f"no reference lyrics for {track_id} ({error.__class__.__name__})")
        return None
    if not found or not found.get("syncedLyrics"):
        log(f"no reference lyrics for {track_id} on LRCLIB")
        return None
    data = {"source": "lrclib", "id": found.get("id"), "artist": found.get("artistName"),
            "title": found.get("trackName"), "duration": found.get("duration"),
            "lines": parse_synced(found["syncedLyrics"])}
    reference_path(track_id).write_text(json.dumps(data, indent=1) + "\n")
    log(f"reference lyrics: {data['artist']} - {data['title']} ({len(data['lines'])} lines, LRCLIB)")
    return data


def repeated_spans(reference: dict[str, Any], *, min_count: int = 2, max_words: int = 12) -> list[tuple[float, float]]:
    """Time spans (seconds) of lines that come back at least ``min_count`` times: the hooks and choruses."""
    counts: dict[str, int] = {}
    for line in reference["lines"]:
        if 1 <= len(line["norm"].split()) <= max_words:
            counts[line["norm"]] = counts.get(line["norm"], 0) + 1
    return [(line["time"], line["end"]) for line in reference["lines"] if counts.get(line["norm"], 0) >= min_count]


def expected_words(reference: dict[str, Any], start: float, end: float) -> list[tuple[str, float, float]]:
    """(word, line start, line end) for every reference word whose line starts inside [start, end)."""
    from glass_harbor.lyrics import _normalize

    words = []
    for line in reference["lines"]:
        if start <= line["time"] < end:
            for word in line["text"].split():
                text = _normalize(word)
                if text:
                    words.append((text, line["time"], line["end"]))
    return words
