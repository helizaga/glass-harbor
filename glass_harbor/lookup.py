"""Before you buy a beat: its tempo, key, and popularity, and whether a vocal would fit it.

Chart tags are hints, not measurements. Beatport's BPM is reliable inside a genre's usual tempo but often wrong
outside it (Tape B & Zaytoven's "Signature Sound" is tagged 97 bpm and plays at 140), so a beat picked for its
chart BPM can fail the fit check after it is bought. This looks a song up where tempo and key come from an
audio analysis, then applies the same tempo and key gates as ``fit``:

- songbpm.com: tempo, key, and mode (Spotify's analysis; free, no account);
- Deezer: popularity rank and release date (the source the hit-potential score uses).

Without the audio it cannot measure vocal room or harshness; ``glass-harbor fit`` on the file still decides.
"""

from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
from typing import Any

from glass_harbor import compat, fit, library, potential
from glass_harbor.keys import Key, parse_key

SONGBPM = "https://songbpm.com"
TIMEOUT_S = 15
USER_AGENT = "Mozilla/5.0 (compatible; glass-harbor)"
WORKERS = 8  # songs looked up at once; each is a few small requests, so the wait is the network, not the CPU
VERDICT_ORDER = {"good": 0, "risky": 1, "poor": 2, "unknown": 3}

_CARD = re.compile(r'<a[^>]*href="(/@[^"]+)"[^>]*>(.*?)</a>', re.S)
_MODE = re.compile(r"with an? ([A-G]\S*) key and an? (major|minor) mode")


def _fetch(url: str, data: bytes | None = None) -> str:
    request = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:  # noqa: S310 - fixed https host
        return response.read().decode("utf-8", "replace")


def _text(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def _field(card: str, label: str) -> str | None:
    match = re.search(rf">\s*{label}\s*</span>\s*<span[^>]*>(.*?)</span>", card, re.S)
    return _text(match.group(1)) if match else None


def parse_results(page: str) -> list[dict[str, Any]]:
    """Songs on a songbpm search page, best match first: artist, title, key (home note only), bpm, song page."""
    songs = []
    for href, card in _CARD.findall(page):
        names = [_text(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", card, re.S)]
        bpm = _field(card, "BPM")
        if len(names) < 2 or not bpm:
            continue  # a link that is not a song card
        try:
            songs.append({"artist": names[0], "title": names[1], "key": _field(card, "Key"), "bpm": float(bpm),
                          "url": SONGBPM + href})
        except ValueError:
            continue
    return songs


def parse_mode(page: str) -> str | None:
    """"major" or "minor" from a songbpm song page ("... with a G key and a major mode")."""
    match = _MODE.search(_text(page))
    return match.group(2) if match else None


def _keys(note: str, mode: str | None) -> list[Key]:
    """Keys a songbpm key could be: its note ("A♯/B♭" -> A♯) in the given mode, or both modes when unknown."""
    name = note.split("/")[0].strip()
    return [parse_key(f"{name} {m}") for m in ([mode] if mode else ["major", "minor"])]


def _same_song(query: str, songs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The results that are the song asked for. "Artist - Title" must match both; free text trusts the top hit."""
    from glass_harbor.lyrics_ref import _artists, _norm_name

    if " - " in query:
        artist, title = (part.strip() for part in query.split(" - ", 1))
    elif songs:
        artist, title = songs[0]["artist"], songs[0]["title"]
    else:
        return []
    return [s for s in songs if _norm_name(s["title"]) == _norm_name(title) and _artists(s["artist"]) & _artists(artist)]


def songbpm(query: str) -> dict[str, Any] | None:
    """Tempo and key(s) for a song, or None when songbpm doesn't know it. Network errors raise."""
    search = urllib.parse.urlencode({"query": query.replace(" - ", " ")}).encode()
    same = _same_song(query, parse_results(_fetch(f"{SONGBPM}/searches", search)))
    if not same:
        return None
    keys: list[Key] = []
    modes_known = True
    for note in dict.fromkeys(s["key"] for s in same if s["key"]):  # each distinct key once, best match first
        mode = parse_mode(_fetch(next(s["url"] for s in same if s["key"] == note)))
        modes_known = modes_known and mode is not None
        try:
            keys += _keys(note, mode)
        except ValueError:
            continue  # a key the page shows as something other than a note name: skip it, keep the rest
    return {"artist": same[0]["artist"], "title": same[0]["title"], "bpm": same[0]["bpm"],
            "bpms": sorted({s["bpm"] for s in same}), "keys": list(dict.fromkeys(keys)), "modes_known": modes_known,
            "url": same[0]["url"]}


def vocal_profile(vocal: str) -> dict[str, Any]:
    """What every check against this vocal needs, measured once per batch (the sung-or-rap check takes seconds)."""
    return {"id": vocal, "analysis": library.load_analysis(vocal), "kind": fit.vocal_kind(vocal)[0]}


def against(profile: dict[str, Any], bpm: float, keys: list[Key]) -> dict[str, Any]:
    """The fit check's tempo and key gates for laying the vocal over a beat at this tempo, once per possible key.
    Where the sources disagree on the key, the verdict is the worst of them."""
    vocal, vox, kind = profile["id"], profile["analysis"], profile["kind"]
    options = []
    for key in keys:
        # No audio, so no chroma: the matcher ranks shifts by the key wheel and the semitone cost alone.
        bed = {"bpm": bpm, "key": {"tonic": key.tonic, "mode": key.mode, "confidence": 0.5}, "chroma": [0.0] * 12}
        best = compat.score_pair(vocal, vox, "lookup", bed)[0]
        checks = fit.match_checks(best.stretch_pct, best.semitones, best.relation, kind)
        options.append({"key": key.name, "relation": best.relation, "semitones": best.semitones,
                        "tempo_ratio": best.tempo_ratio, "stretch_pct": best.stretch_pct, "checks": checks,
                        "verdict": fit.verdict(checks)})
    worst = max(options, key=lambda option: VERDICT_ORDER[option["verdict"]])
    reasons = dict.fromkeys(fit.REASONS[c["check"]] for o in options for c in o["checks"] if c["level"] != "good")
    return {"vocal": vocal, "vocal_bpm": round(float(vox["bpm"]), 1), "vocal_key": vox["key"]["name"],
            "vocal_type": kind, "options": options, "verdict": worst["verdict"], "reasons": list(reasons)}


def lookup(query: str, *, profile: dict[str, Any] | None = None, bpm: float | None = None, key: str | None = None
           ) -> dict[str, Any]:
    """One song: what songbpm and Deezer know about it and, given a vocal's ``vocal_profile``, whether the vocal
    would fit. ``bpm``/``key`` override songbpm (to check a chart's numbers, or a song songbpm doesn't know)."""
    notes = []
    found = None
    try:
        found = songbpm(query)
        if found is None:
            notes.append("not found on songbpm")
    except Exception as error:  # noqa: BLE001 - offline or the page changed: keep going with what was given
        notes.append(f"songbpm lookup failed ({error})")
    if found:
        artist, title = found["artist"], found["title"]
    elif " - " in query:
        artist, title = (part.strip() for part in query.split(" - ", 1))
    else:
        artist, title = "", ""  # free text that songbpm couldn't place: too vague to match on Deezer
    tempo = bpm if bpm is not None else (found or {}).get("bpm")
    keys = [parse_key(key)] if key else (found or {}).get("keys", [])
    if found and len(found["bpms"]) > 1 and not _same_tempo(found["bpms"]):
        notes.append(f"songbpm lists different tempos ({', '.join(f'{b:g}' for b in found['bpms'])})")
    if found and len({k.tonic for k in found["keys"]}) > 1:
        notes.append("songbpm lists several keys: each is checked")
    elif found and not found["modes_known"]:
        notes.append("major or minor unknown: both are checked")

    pop = None
    if title:
        try:
            pop = potential.find(artist, title)
        except Exception as error:  # noqa: BLE001 - offline or rate-limited: unknown, not zero
            notes.append(f"Deezer lookup failed ({error})")
    months = potential._months_old((pop or {}).get("release_date"))

    result: dict[str, Any] = {
        "query": query, "artist": artist, "title": title, "bpm": tempo, "keys": [k.name for k in keys],
        "source": "given" if bpm is not None or key else "songbpm" if found else None,
        "songbpm_url": (found or {}).get("url"), "popularity": pop, "popularity_note": potential.tier(pop)[1],
        "months_old": None if months is None else round(months, 1), "notes": notes, "fit": None, "verdict": None,
    }
    if profile:
        if tempo and keys:
            result["fit"] = against(profile, float(tempo), keys)
            result["verdict"] = result["fit"]["verdict"]
        else:
            result["verdict"] = "unknown"
    return result


def lookup_many(queries: list[str], *, vocal: str | None = None, bpm: float | None = None, key: str | None = None,
                workers: int = WORKERS) -> list[dict[str, Any]]:
    """``lookup`` for each song, several at once, in the order given. The vocal is measured once for all of them."""
    from concurrent.futures import ThreadPoolExecutor

    profile = vocal_profile(vocal) if vocal else None
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(queries)))) as pool:
        return list(pool.map(lambda query: lookup(query, profile=profile, bpm=bpm, key=key), queries))


def _same_tempo(bpms: list[float]) -> bool:
    """True when the tempos agree up to half/double time (196 and 98 are the same groove)."""
    base = bpms[0]
    return all(min(abs(b / (base * r) - 1) for r in (0.5, 1.0, 2.0)) <= 0.02 for b in bpms)


def rank(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Best candidates first: by verdict, then by how little the vocal has to stretch."""
    def order(result: dict[str, Any]) -> tuple[int, float]:
        stretch = abs(result["fit"]["options"][0]["stretch_pct"]) if result.get("fit") else float("inf")
        return VERDICT_ORDER[result.get("verdict") or "unknown"], stretch
    return sorted(results, key=order)
