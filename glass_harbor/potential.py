"""Hit potential: the ingredients viral mashups tend to share, scored before the long work.

No one can predict virality. What can be measured is whether a pairing has the usual ingredients:

- recognizable: at least one song people already know (Deezer's public popularity rank; no account needed);
- current: a recent release, especially the beat (the lane people are dancing to now);
- hook: a short line that comes back several times (from the published lyrics), early in the song;
- crossover: a vocal and a beat from different worlds (a rap or R&B vocal under 115 bpm over a club beat at 120+).

The score is advisory: ``fit`` reports it next to the musical fit, and the brief records it.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import urllib.parse
import urllib.request
from typing import Any

from glass_harbor import library

API = "https://api.deezer.com"
TIMEOUT_S = 10
CACHE_DAYS = 7
HIT_RANK, POPULAR_RANK, KNOWN_RANK = 600_000, 300_000, 100_000  # Deezer ranks; the #1 song sits near 1,000,000


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{API}/{path}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
    request = urllib.request.Request(url, headers={"User-Agent": "glass-harbor"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:  # noqa: S310 - fixed https host
        return json.loads(response.read())


def find(artist: str, title: str) -> dict[str, Any] | None:
    """Deezer rank and release date for one song, or None when no hit is clearly that song. Network errors raise."""
    from glass_harbor.lyrics_ref import _artists, _norm_name, lead_artist

    want_title, lead = _norm_name(title), lead_artist(artist)
    # Search by the lead artist only: a long credit ("1 Umbrella; Lil Bean; Lil Yee; ...") finds nothing.
    hits = _get("search", {"q": f"{lead or ''} {title}".strip(), "limit": 10}).get("data", [])
    same = [h for h in hits if _norm_name(h.get("title", "")) == want_title
            and (lead is None or lead in _artists(h.get("artist", {}).get("name", "")))]
    # Without an artist, a title several artists share is ambiguous: unknown beats wrong.
    if not same or not (lead or len({h["artist"]["name"].lower() for h in same}) == 1):
        return None
    hit = same[0]
    track = _get(f"track/{hit['id']}")
    return {"title": hit["title"], "artist": hit["artist"]["name"], "rank": int(hit.get("rank") or 0),
            "release_date": track.get("release_date")}


def popularity(track_id: str) -> dict[str, Any] | None:
    """Deezer rank and release date for a library track (cached for a week). None when not found or offline."""
    from glass_harbor.lyrics_ref import artist_and_title

    cache = library.track_dir(track_id) / "popularity.json"
    try:
        data = json.loads(cache.read_text())
        if (dt.date.today() - dt.date.fromisoformat(data["checked"])).days < CACHE_DAYS:
            return data.get("result")
    except (OSError, ValueError, KeyError):
        pass  # missing or unreadable cache: look it up again
    try:
        result = find(*artist_and_title(library.load_meta(track_id)))
    except Exception:  # noqa: BLE001 - offline or rate-limited: unknown, not zero
        return None
    # Write a temporary file and swap it in, so a parallel reader (another watcher) never sees half a cache.
    tmp = cache.with_name(f"{cache.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps({"checked": dt.date.today().isoformat(), "result": result}) + "\n")
    os.replace(tmp, cache)
    return result


def _months_old(release_date: str | None) -> float | None:
    if not release_date:
        return None
    try:
        return (dt.date.today() - dt.date.fromisoformat(release_date)).days / 30.4
    except ValueError:
        return None


def months_ago(months: float) -> str:
    """'1 month ago', '18 months ago': the age as the reasons and the lookup print it."""
    count = f"{months:.0f}"
    return f"{count} month{'' if count == '1' else 's'} ago"


def tier(pop: dict[str, Any] | None) -> tuple[float, str]:
    """How well known a song is: a 0-1 weight and a note for the reasons."""
    if pop is None:
        return 0.3, "unknown popularity"
    rank = pop["rank"]
    if rank >= HIT_RANK:
        return 1.0, f"a hit (Deezer rank {rank:,})"
    if rank >= POPULAR_RANK:
        return 0.75, f"popular (Deezer rank {rank:,})"
    if rank >= KNOWN_RANK:
        return 0.45, f"known (Deezer rank {rank:,})"
    return 0.2, f"niche (Deezer rank {rank:,})"


def freshness(months: float | None) -> float:
    """1 for a release in the last six months, less the older it is; unknown dates sit in between."""
    if months is None:
        return 0.4
    return 1.0 if months <= 6 else 0.6 if months <= 18 else 0.25


def hook(track_id: str) -> dict[str, Any] | None:
    """The vocal's hook from its published lyrics: the most repeated short line, how often, and how early."""
    from glass_harbor.lyrics_ref import load_reference

    reference = load_reference(track_id)
    if not reference or not reference.get("lines"):
        return None
    counts: dict[str, list[float]] = {}
    for line in reference["lines"]:
        words = len(line["norm"].split())
        if 1 <= words <= 8:
            counts.setdefault(line["norm"], []).append(line["time"])
    if not counts:
        return None
    text, times = max(counts.items(), key=lambda kv: (len(kv[1]), -len(kv[0].split())))
    return {"repeats": len(times), "words": len(text.split()), "first_s": round(min(times), 1)}


def assess(vocal: str, beat: str, *, crossover: bool | None = None) -> dict[str, Any]:
    """Score 0-100 with the reasons behind it."""
    vocal_pop, beat_pop = popularity(vocal), popularity(beat)
    hook_info = hook(vocal)
    score, reasons = 0.0, []
    vocal_tier, vocal_note = tier(vocal_pop)
    beat_tier, beat_note = tier(beat_pop)
    score += 35 * max(vocal_tier, 0.6 * beat_tier) + 10 * beat_tier
    reasons.append(f"vocal is {vocal_note}; beat is {beat_note}")

    beat_age = _months_old((beat_pop or {}).get("release_date"))
    vocal_age = _months_old((vocal_pop or {}).get("release_date"))
    score += 15 * freshness(beat_age) + 5 * freshness(vocal_age)
    if beat_age is not None:
        reasons.append(f"beat released {months_ago(beat_age)}" + (" (fresh)" if beat_age <= 6 else ""))

    if hook_info:
        catchy = min(1.0, hook_info["repeats"] / 4) * (1.0 if hook_info["words"] <= 6 else 0.7)
        early = 1.0 if hook_info["first_s"] <= 45 else 0.6 if hook_info["first_s"] <= 75 else 0.3
        score += 25 * catchy * early
        reasons.append(f"hook: {hook_info['words']}-word line repeated {hook_info['repeats']}x, first at "
                       f"{hook_info['first_s']:.0f}s")
    else:
        score += 8
        reasons.append("hook unknown (no published lyrics)")

    if crossover is None:
        vocal_bpm = library.load_analysis(vocal)["grid"]["bpm"]
        beat_bpm = library.load_analysis(beat)["grid"]["bpm"]
        # Analysis grids sit at the faster pulse, so club beats (house, jersey, DnB) read 120 bpm and up; a slower
        # beat is the vocal's own world, not a crossover.
        crossover = vocal_bpm < 115 and beat_bpm >= 120
    if crossover:
        score += 10
        reasons.append("crossover: a hip-hop/R&B vocal on a club beat")
    level = "high" if score >= 70 else "medium" if score >= 45 else "low"
    return {"score": round(score), "level": level, "reasons": reasons,
            "vocal": vocal_pop, "beat": beat_pop, "hook": hook_info}
