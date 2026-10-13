import json
import urllib.parse

import pytest

from conftest import write_fake_track

from glass_harbor import fit, lookup, potential
from glass_harbor.cli import main


def _card(href, artist, title, key, bpm):
    return (f'<a class="card" href="{href}"> <div><p class="text-sm"> {artist} </p> <p class="pr-2"> {title} </p></div>'
            f' <div><span class="text-xs uppercase">Key</span> <span class="text-2xl">{key}</span></div>'
            f' <div><span class="text-xs uppercase">Duration</span> <span class="text-2xl"> 2:37 </span></div>'
            f' <div><span class="text-xs uppercase">BPM</span> <span class="text-2xl font-bold"> {bpm} </span></div>'
            f' </a> <a href="https://open.spotify.com/track/x"><span class="sr-only">Listen on</span> Spotify</a>')


SEARCHES = {
    "mr eazi lambo": [("/@mr-eazi/lambo-a", "Mr Eazi", "Lambo", "G", 196),
                      ("/@mr-eazi/lambo-b", "Mr Eazi", "Lambo", "D", 196),
                      ("/@mr-eazi/jamboree", "Mr Eazi", "Jamboree", "C", 104)],
    "tape b signature sound": [("/@tape-b/signature-sound", "Tape B", "Signature Sound", "F", 139),
                               ("/@booska-p/on-tape", "Booska-P", "ON TAPE", "A♯/B♭", 146)],
    "someone else lambo": [("/@mr-eazi/lambo-a", "Mr Eazi", "Lambo", "G", 196)],
}
MODES = {"/@mr-eazi/lambo-a": "major", "/@mr-eazi/lambo-b": "minor", "/@tape-b/signature-sound": "minor"}


def _songbpm(url, data=None):
    if url.endswith("/searches"):
        query = urllib.parse.parse_qs(data.decode())["query"][0].lower()  # songbpm search ignores case
        cards = "".join(_card(*row) for row in SEARCHES.get(query, []))
        return f'<html><a href="/@popular/elsewhere">Popular</a><main>{cards}</main></html>'
    mode = MODES.get(url.removeprefix(lookup.SONGBPM))
    sentence = f"with a G key and a {mode} mode" if mode else "with a G key"
    return f"<html><p>Lambo is a song with a tempo of 196 BPM. The track runs 2 minutes {sentence}.</p></html>"


def _deezer(path, params=None):
    if path == "search":
        return {"data": [{"id": 7, "title": "Lambo", "rank": 292_063, "artist": {"name": "Mr Eazi"}}]
                if "Lambo" in params["q"] else []}
    return {"release_date": "2026-07-03"}


@pytest.fixture()
def online(monkeypatch, workspace):
    monkeypatch.setattr(lookup, "_fetch", _songbpm)
    monkeypatch.setattr(potential, "_get", _deezer)
    write_fake_track("umbrella", bpm=95, key="G minor", bars=16, stems=())


def test_parse_results_reads_song_cards_and_skips_other_links():
    page = _songbpm(f"{lookup.SONGBPM}/searches", b"query=tape+b+signature+sound")
    songs = lookup.parse_results(page.replace("Tape B", "Tape B &amp; Zaytoven"))
    assert [(s["artist"], s["title"], s["key"], s["bpm"]) for s in songs] == [
        ("Tape B & Zaytoven", "Signature Sound", "F", 139.0), ("Booska-P", "ON TAPE", "A♯/B♭", 146.0)]
    assert songs[0]["url"] == "https://songbpm.com/@tape-b/signature-sound"
    assert lookup.parse_mode("<p>runs 3 minutes with a <b>F</b> key and a minor mode.</p>") == "minor"
    assert lookup.parse_mode("<p>no mode here</p>") is None
    assert [k.name for k in lookup._keys("A♯/B♭", None)] == ["A# major", "A# minor"]


def test_lookup_applies_the_fit_gates_to_every_key_the_sources_give(online):
    result = lookup.lookup("Mr Eazi - Lambo", profile=lookup.vocal_profile("umbrella"))
    assert (result["artist"], result["bpm"], result["keys"]) == ("Mr Eazi", 196.0, ["G major", "D minor"])
    assert result["popularity"]["rank"] == 292_063 and result["popularity"]["release_date"] == "2026-07-03"
    options = result["fit"]["options"]
    # 95 bpm doubled is 190: 196 needs +3.2%, past the 3% "risky" line but well inside the 6% "poor" one.
    assert {o["tempo_ratio"] for o in options} == {2.0} and all(o["semitones"] == 0 for o in options)
    assert all(o["verdict"] == "risky" and 3 < o["stretch_pct"] < 3.3 for o in options)
    assert result["verdict"] == "risky" and "songbpm lists several keys: each is checked" in result["notes"]
    assert result["fit"]["vocal_type"] == "rap"  # not separated yet: the looser limits

    poor = lookup.lookup("tape b signature sound", profile=lookup.vocal_profile("umbrella"))
    assert poor["keys"] == ["F minor"] and poor["verdict"] == "poor"  # -26.8% at double time
    assert poor["popularity"] is None  # Deezer has no hit that is this song: unknown, not wrong
    assert [r["title"] for r in lookup.rank([poor, result])] == ["Lambo", "Signature Sound"]


def test_lookup_without_a_match_or_network_reports_unknown(online, monkeypatch):
    wrong_artist = lookup.lookup("Someone Else - Lambo", profile=lookup.vocal_profile("umbrella"))
    assert wrong_artist["bpm"] is None and wrong_artist["verdict"] == "unknown"
    assert wrong_artist["notes"] == ["not found on songbpm"]

    given = lookup.lookup("Someone Else - Lambo", profile=lookup.vocal_profile("umbrella"), bpm=96, key="Bb major")
    assert given["source"] == "given" and given["fit"]["options"][0]["relation"] == "relative major/minor"
    assert given["verdict"] == "good"  # +1% and the relative major

    monkeypatch.setattr(lookup, "_fetch", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    offline = lookup.lookup("Mr Eazi - Lambo", profile=lookup.vocal_profile("umbrella"))
    assert offline["verdict"] == "unknown" and offline["notes"][0].startswith("songbpm lookup failed")


def test_lookup_checks_both_modes_when_songbpm_does_not_say(online, monkeypatch):
    monkeypatch.setitem(MODES, "/@tape-b/signature-sound", None)
    result = lookup.lookup("Tape B - Signature Sound")
    assert result["keys"] == ["F major", "F minor"] and "major or minor unknown: both are checked" in result["notes"]
    assert result["fit"] is None and result["verdict"] is None  # no vocal: facts only


def test_lookup_many_measures_the_vocal_once_and_keeps_the_order(online, monkeypatch):
    calls = []
    monkeypatch.setattr(fit, "vocal_kind", lambda track: calls.append(track) or ("rap", None))
    songs = ["Tape B - Signature Sound", "Mr Eazi - Lambo", "Someone Else - Lambo"]
    results = lookup.lookup_many(songs, vocal="umbrella", workers=3)
    assert calls == ["umbrella"] and [r["query"] for r in results] == songs
    assert [r["verdict"] for r in results] == ["poor", "risky", "unknown"]


def test_tempos_agree_up_to_half_and_double_time():
    assert lookup._same_tempo([98.0, 196.0, 97.5])
    assert not lookup._same_tempo([97.0, 140.0])


def test_match_checks_are_the_fit_gates():
    assert fit.match_checks(2.9, 0, "same key", "rap") == []
    assert [c["level"] for c in fit.match_checks(-3.2, 0, "same key", "rap")] == ["risky"]
    assert [c["level"] for c in fit.match_checks(6.5, 0, "same key", "rap")] == ["poor"]
    assert [(c["check"], c["level"]) for c in fit.match_checks(0, 3, "same key", "rap")] == [("key", "risky")]
    assert [(c["check"], c["level"]) for c in fit.match_checks(0, 0, "clash", "sung")] == [("key", "poor")]
    assert fit.verdict(fit.match_checks(-26.8, -2, "same key", "rap")) == "poor"


def test_cli_lookup_ranks_candidates_and_fails_when_none_fit(online, capsys):
    code = main(["lookup", "Tape B - Signature Sound", "Mr Eazi - Lambo", "--vocal", "umbrella", "--json"])
    results = json.loads(capsys.readouterr().out)
    assert code == 0 and [r["title"] for r in results] == ["Lambo", "Signature Sound"]

    assert main(["lookup", "Tape B - Signature Sound", "--vocal", "umbrella"]) == 1
    out = capsys.readouterr().out
    assert "POOR" in out and "-26.8% stretch" in out and "glass-harbor fit" in out

    assert main(["lookup", "a - b", "c - d", "--bpm", "96"]) == 2  # --bpm describes one song


def test_release_age_agrees_with_its_number():
    from glass_harbor.cli import _lookup_lines

    assert [potential.months_ago(m) for m in (0.2, 1.0, 1.4, 1.6, 18.0)] == \
        ["0 months ago", "1 month ago", "1 month ago", "2 months ago", "18 months ago"]
    result = {"query": "elden - SWARM", "artist": "elden", "title": "SWARM", "bpm": 150.0, "keys": ["E minor"],
              "source": "songbpm", "popularity": {"release_date": "2026-09-13"},
              "popularity_note": "niche (Deezer rank 71,023)", "months_old": 1.0, "notes": [], "fit": None,
              "verdict": None}
    assert _lookup_lines(result)[1] == "  niche (Deezer rank 71,023), released 2026-09-13 (1 month ago, fresh)"
