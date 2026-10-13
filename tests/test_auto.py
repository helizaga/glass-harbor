import json

import pytest

from conftest import write_fake_track

from glass_harbor import arrange, library
from glass_harbor.lyrics import lyrics_path
from glass_harbor.plan import resolve


def _seg(start_s, words):
    out = [{"word": w, "start": start_s + 0.3 * i, "end": start_s + 0.3 * i + 0.25, "prob": 1}
           for i, w in enumerate(words.split())]
    return {"start": out[0]["start"], "end": out[-1]["end"], "text": words, "words": out}


def _dnb_beat(bars=195):
    levels = [-18.0] * 16 + [-7.0] * 80 + [-18.0] * 16 + [-7.0] * (bars - 112)
    low = [-33.0] * 16 + [-13.0] * (bars - 16)
    return {"bpm": 175.0, "bar_db": levels, "low_db": low, "drops": [17, 113],
            "sections": [{"start_bar": 1, "bars": 32, "label": "intro"}, {"start_bar": 33, "bars": 64, "label": "chorus"},
                         {"start_bar": 97, "bars": 16, "label": "break"}, {"start_bar": 113, "bars": 83, "label": "chorus"}]}


def _chant_song(workspace):
    """A 90 bpm rap song: intro line, "yeah bop" chants, verses, and outro chants (2.667 s per bar)."""
    write_fake_track("vox", bpm=90, key="Am", bars=46)
    bar = 240 / 90
    at = lambda b: (b - 1) * bar  # noqa: E731  (bar 1 starts at 0 s)
    segs = [_seg(at(1), "intro line one two three four"), _seg(at(3), "yeah bop"), _seg(at(4), "yeah bop")]
    segs += [_seg(at(b), f"rapping verse line number {b} with many words") for b in range(6, 18)]
    segs += [_seg(at(18), "yeah bop")]
    segs += [_seg(at(b), f"second verse line {b} with plenty of words") for b in range(20, 40)]
    segs += [_seg(at(42), "yeah bop"), _seg(at(44), "yeah bop")]
    lyrics_path("vox").write_text(json.dumps({"segments": segs}))
    return segs


def test_own_intro_bars():
    assert arrange.own_intro_bars(_dnb_beat()) == 16
    assert arrange.own_intro_bars({"low_db": [-12.0] * 64}) == 0
    # Stay With Me: a pad-only bass keeps the low band up, but the drums are 24 dB down until the bar-17 drop.
    soft = {"low_db": [-27.0] * 16 + [-17.0] * 100, "drops": [17, 66],
            "stems": {"drums": {"bar_db": [-45.0] * 16 + [-21.0] * 100}}}
    assert arrange.own_intro_bars(soft) == 16
    busy = {**soft, "stems": {"drums": {"bar_db": [-22.0] * 16 + [-13.0] * 100}}}  # SWARM: real drums before it
    assert arrange.own_intro_bars(busy) == 0
    fill = {**soft, "stems": {"drums": {"bar_db": [-45.0] * 15 + [-27.0] + [-21.0] * 100}}}  # a fill into the drop
    assert arrange.own_intro_bars(fill) == 16
    groove = {"low_db": [-27.0] * 32 + [-17.0] * 100, "drops": [33],
              "stems": {"drums": {"bar_db": [-45.0] * 24 + [-21.0] * 108}}}  # drums in 8 bars before the drop
    assert arrange.own_intro_bars(groove) == 24


def test_a_verse_groove_after_the_first_drop_is_full():
    sections = [{"start_bar": 1, "label": "intro"}, {"start_bar": 9, "label": "verse"},
                {"start_bar": 17, "label": "verse"}, {"start_bar": 41, "label": "chorus"}]
    assert arrange.full_start({"sections": sections, "drops": [17, 66]}) == 17  # not the bar-41 chorus
    assert arrange.full_start({"sections": sections, "drops": [33]}) == 41  # verses before the beat comes in don't count


def test_song_order_lands_verse_one_on_the_full_section_and_resumes_after_the_breakdown(workspace):
    from glass_harbor.lyrics import load_lyrics

    _chant_song(workspace)
    clips, builds, notes = arrange.song_order("vox", _dnb_beat(), 2.0, load_lyrics("vox"))
    by_from = {c.get("from_bar"): c for c in clips if "from_bar" in c}
    assert by_from[6]["at_bar"] == 33 and "chain" not in by_from[6]  # verse 1 on the full section, rap chain
    assert by_from[1]["chain"] == "hook" and by_from[1]["at_bar"] == 23  # intro and chants ride the build
    assert all(c["at_bar"] + c["bars"] * 2 <= 97 or c["at_bar"] >= 105 for c in clips)  # silent in the breakdown
    assert 113 in builds and any(c.get("chop") and c["at_bar"] == 105 for c in clips)  # chant build into drop 2
    assert any("comes back on the bar-113 drop" in n for n in notes)


def _plan_with_stems(workspace, *, bpm=175.0):
    write_fake_track("bed", bpm=bpm, key="Am", bars=195, stems=("drums", "bass", "other", "vocals"))
    clips = [{"id": f"bed-{s}", "source": "bed", "stem": s, "from_bar": 1, "bars": 195, "at_bar": 1}
             for s in ("drums", "bass", "other")]
    return {"version": 1, "kind": "mashup", "bpm": bpm, "sources": {"vox": {"track": "vox", "tempo_ratio": 2.0},
                                                                   "bed": {"track": "bed"}}, "clips": clips}


def test_reprise_fills_a_silent_back_half(workspace):
    _chant_song(workspace)
    plan = _plan_with_stems(workspace)
    plan["clips"].append({"id": "verse1", "source": "vox", "stem": "vocals", "from_bar": 6, "bars": 12, "at_bar": 33})
    plan = arrange.add_reprise(plan, _dnb_beat())
    reprise = next(c for c in plan["clips"] if c["id"] == "verse-reprise")
    assert reprise["from_bar"] == 10 and reprise["bars"] == 8 and reprise["at_bar"] >= 117
    assert resolve(plan).ok


def test_bed_answers_only_where_the_acapella_is_silent(workspace):
    _chant_song(workspace)
    plan = _plan_with_stems(workspace)
    plan["clips"].append({"id": "verse1", "source": "vox", "stem": "vocals", "from_bar": 6, "bars": 12, "at_bar": 33})
    bar = 240 / 175
    lyrics_path("bed").write_text(json.dumps({"segments": [_seg((b - 1) * bar, "get up") for b in (16, 40, 150)]}))
    plan = arrange.add_bed_answers(plan, "bed")
    shouts = sorted(c["at_bar"] for c in plan["clips"] if c["id"].startswith("bed-shout"))
    assert shouts == [16, 150]  # bar 40 sits under verse 1
    assert resolve(plan).ok


def test_halftime_switch_on_dnb(workspace):
    _chant_song(workspace)
    plan = _plan_with_stems(workspace)
    plan["clips"] += [{"id": "verse1", "source": "vox", "stem": "vocals", "from_bar": 6, "bars": 12, "at_bar": 33},
                      {"id": "hook1", "source": "vox", "stem": "vocals", "from_bar": 18, "bars": 2, "at_bar": 57,
                       "chain": "hook"},
                      {"id": "verse2", "source": "vox", "stem": "vocals", "from_bar": 20, "bars": 8, "at_bar": 61}]
    plan = arrange.add_halftime_switch(plan)
    half = next(c for c in plan["clips"] if c.get("generate") == "halftime")
    assert half["at_bar"] == 61 and any(c.get("generate") == "impact" and c["at_bar"] == 77 for c in plan["clips"])
    drums = next(c for c in plan["clips"] if c["id"] == "bed-drums")
    assert any(p[1] == -60.0 for p in drums["automation"]["arrange_db"])
    assert resolve(plan).ok
    slow = _plan_with_stems(workspace, bpm=126.0)
    slow["clips"] += plan["clips"][3:6]
    assert not any(c.get("generate") == "halftime" for c in arrange.add_halftime_switch(slow)["clips"])


def test_fix_rounds_lift_buried_vocals_and_strip_before_flat_drops(workspace):
    from glass_harbor.auto import apply_qa_fixes

    _chant_song(workspace)
    plan = _plan_with_stems(workspace)
    plan["clips"][2]["duck"] = {"under": "vocals", "db": 5.0}
    plan["clips"].append({"id": "verse1", "source": "vox", "stem": "vocals", "from_bar": 6, "bars": 12, "at_bar": 33})
    report = {"vocal_presence": [{"bar": b, "db": -5.0} for b in (40, 41, 42)], "bass_clash": []}
    qa = {"flags": [{"level": "warning", "where": "bar 81", "message": "the drop has only 1.0 dB of contrast with "
                                                                      "the 8 bars before it; strip or filter more"}]}
    changes = apply_qa_fixes(plan, report, qa)
    verse = next(c for c in plan["clips"] if c["id"] == "verse1")
    assert verse["gain_db"] == 2.0 and plan["clips"][2]["duck"]["db"] == 7.0
    bass = next(c for c in plan["clips"] if c["id"] == "bed-bass")
    assert any(p == [79.0, -60.0] for p in bass["automation"]["arrange_db"])  # bar 80 = offset 79
    assert len(changes) >= 2 and resolve(plan).ok
    assert not any("drop at bar 81" in c for c in apply_qa_fixes(plan, {"vocal_presence": []}, qa))  # done once


def test_match_words_counts_each_heard_word_once_near_its_spot():
    from glass_harbor.listen import match_words

    expected = [("yeah", 1.0), ("bop", 1.3), ("yeah", 5.0), ("money", 9.0)]
    heard = [("yeah", 1.1), ("bop", 1.25), ("money", 12.0)]  # second yeah missed, money far off
    assert match_words(expected, heard) == 2


def test_fix_rounds_lift_clips_whisper_cannot_make_out(workspace):
    from glass_harbor.auto import apply_qa_fixes

    _chant_song(workspace)
    plan = _plan_with_stems(workspace)
    plan["clips"].append({"id": "hook1", "source": "vox", "stem": "vocals", "from_bar": 1, "bars": 5, "at_bar": 23,
                          "chain": "hook"})
    changes = apply_qa_fixes(plan, {"vocal_presence": []}, {"flags": []}, {"weak": ["hook1"]})
    assert plan["clips"][-1]["gain_db"] == 2.0 and any("hard to make out" in c for c in changes)


def test_bed_sections_fall_back_without_allin1(monkeypatch):
    import importlib.util

    from glass_harbor import auto

    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a: None if name == "allin1_infer" else real(name, *a))
    assert auto.bed_sections() == "novelty"
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a: object() if name == "allin1_infer" else real(name, *a))
    assert auto.bed_sections() == "allin1"


def test_auto_callers_use_novelty_without_allin1(monkeypatch):
    import importlib.util

    from glass_harbor import analyze, auto, separate

    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a: None if name == "allin1_infer" else real(name, *a))
    seen = []

    class Stop(Exception):
        pass

    def fake_ingest(source, *, sections, log):
        seen.append(("ingest", source, sections))
        if source == "bed":
            raise Stop
        return source

    monkeypatch.setattr(auto, "ingest", fake_ingest)
    with pytest.raises(Stop):
        auto.run_auto("vox", "bed", log=lambda m: None)
    monkeypatch.setattr(separate, "separate_track", lambda *a, **k: {"drums": {}})
    monkeypatch.setattr(analyze, "analyze_library_track",
                        lambda track_id, **k: seen.append(("analyze", track_id, k.get("sections"))))
    monkeypatch.setattr(auto, "_lyrics", lambda *a: None)
    auto.prepare_bed("bed", lambda m: None)
    assert ("ingest", "bed", "novelty") in seen and ("analyze", "bed", "novelty") in seen


def test_split_cuts_at_the_last_line_start_inside_the_limit():
    pieces = arrange._split_at_lines(1, 20, [5, 9, 14, 18], limit=12)
    assert pieces == [(1, 9), (9, 20)] and all(b - a <= 12 for a, b in pieces)
    assert arrange._split_at_lines(1, 30, [], limit=12) == [(1, 30)]  # one long line stays whole


def test_song_order_keeps_the_fitting_part_of_a_clip_at_the_beat_end(workspace):
    from glass_harbor.lyrics import load_lyrics

    _chant_song(workspace)
    beat = _dnb_beat(bars=80)  # ends at bar 80: the second verse cannot fit whole
    beat["bar_db"] = beat["bar_db"][:80]
    clips, _, notes = arrange.song_order("vox", beat, 2.0, load_lyrics("vox"))
    last = max((c for c in clips if "from_bar" in c), key=lambda c: c["at_bar"])
    # The second verse's first 12-bar piece (vocal bars 20-31) would run to bar 85; it is cut at the last line
    # start that fits and ends exactly where the beat does.
    assert last["from_bar"] == 20 and last["bars"] == 10 and last["at_bar"] + last["bars"] * 2 == 81
    assert any("keeps 4 of 6" in note for note in notes)


def test_reference_lyrics_parse_and_mark_repeats(workspace):
    from glass_harbor.lyrics_ref import artist_and_title, expected_words, parse_synced, repeated_spans

    lines = parse_synced("[00:01.00] Yeah bop\n[00:03.50] a verse line here\n[00:06.00] Yeah bop\n[00:08.00] end")
    assert [round(l["time"], 1) for l in lines] == [1.0, 3.5, 6.0, 8.0] and lines[0]["end"] == 3.5
    reference = {"lines": lines}
    assert repeated_spans(reference) == [(1.0, 3.5), (6.0, 8.0)]
    assert [w for w, _, _ in expected_words(reference, 3.0, 7.0)] == ["a", "verse", "line", "here", "yeah", "bop"]
    assert artist_and_title({"source_file": "01 - Don Toliver - GLOCK.flac"}) == ("Don Toliver", "GLOCK")
    assert artist_and_title({"title": "SWARM", "artist": "", "source_file": "SWARM.mp3"}) == ("", "SWARM")


def test_listen_counts_reference_words_inside_their_line_span():
    from glass_harbor.listen import match_spans

    expected = [("yeah", 1.0, 3.0), ("bop", 1.0, 3.0), ("money", 5.0, 6.0)]
    heard = [("bop", 2.8), ("yeah", 1.2), ("money", 9.0)]
    assert match_spans(expected, heard) == 2


def test_fit_levels_follow_the_vocal_type(monkeypatch, workspace):
    import numpy as np

    from glass_harbor import fit

    write_fake_track("v", bpm=76, key="E", bars=16)
    write_fake_track("b", bpm=150, key="E", bars=32, stems=("instrumental",))
    monkeypatch.setattr(fit, "beat_profile", lambda audio, tonic, mode: {"vocal_room": 0.134, "harshness": 0.02,
                                                                        "out_of_key": 0.3})
    monkeypatch.setattr(fit, "sung_share", lambda track: 0.13)
    sung = fit.assess("v", "b", log=lambda m: None)
    assert sung["vocal_type"] == "sung" and sung["verdict"] == "poor" and "1-4 kHz" in sung["reasons"][0]
    monkeypatch.setattr(fit, "beat_profile", lambda audio, tonic, mode: {"vocal_room": 0.02, "harshness": 0.01,
                                                                        "out_of_key": 0.3})
    assert fit.assess("v", "b", log=lambda m: None)["verdict"] == "good"


def test_reference_search_only_accepts_the_same_song():
    from glass_harbor.lyrics_ref import pick_search_result

    hits = [{"trackName": "Different Song", "artistName": "Lil Bean", "duration": 127, "syncedLyrics": "x"},
            {"trackName": "Yeah Bop 2 (feat. Lil Yee)", "artistName": "Lil Bean", "duration": 151, "syncedLyrics": "x"},
            {"trackName": "yeah bop", "artistName": "Lil Bean", "duration": 127, "syncedLyrics": "x"}]
    assert pick_search_result(hits, "Lil Bean", "yeah bop", 127)["trackName"] == "yeah bop"
    assert pick_search_result(hits, "Someone Else", "yeah bop", 127) is None
    lookalikes = [{"trackName": "yeah bop", "artistName": "Lil Bean Tribute", "duration": 127, "syncedLyrics": "x"},
                  {"trackName": "Janice STFU", "artistName": "Mandrake", "duration": 237, "syncedLyrics": "x"}]
    assert pick_search_result(lookalikes, "Lil Bean", "yeah bop", 127) is None  # a containing name is not a match
    assert pick_search_result(lookalikes, "Drake", "Janice STFU", 237) is None  # nor a substring of one
    collab = [{"trackName": "yeah bop 2", "artistName": "Lil Bean, Lil Yee", "duration": 151, "syncedLyrics": "x"}]
    assert pick_search_result(collab, "Lil Bean", "yeah bop 2", 151) is not None  # one of the credited artists
    assert pick_search_result(collab, "Lil Bean; Lil Yee", "yeah bop 2", 151) is not None  # a file tag's "A; B"
    same_title = [{"trackName": "Swarm", "artistName": "Elden", "duration": 143, "syncedLyrics": "x"},
                  {"trackName": "Swarm", "artistName": "Risk, Viperactive", "duration": 141, "syncedLyrics": "x"}]
    assert pick_search_result(same_title, "", "SWARM", 142.9) is None  # no artist and two different songs
    assert pick_search_result(same_title[:1], "", "SWARM", 142.9)["artistName"] == "Elden"
    featured = [{"trackName": "yeah bop 2", "artistName": "Lil Yee", "duration": 151, "syncedLyrics": "x"}]
    assert pick_search_result(featured, "Lil Bean feat. Lil Yee", "yeah bop 2", 151) is None  # the lead must match


def test_reference_lookup_falls_back_to_search_for_a_multi_artist_file_tag(monkeypatch, workspace):
    from glass_harbor import lyrics_ref

    write_fake_track("b", bpm=130, key="Bm", bars=32)
    library.save_meta("b", {**library.load_meta("b"), "artist": "Calvin Harris; Clementine Douglas",
                            "title": "Blessings", "duration": 220})
    calls = []

    def fake(path, params):
        calls.append(path)
        if path == "get":  # LRCLIB credits "Calvin Harris", so the exact lookup of the tag misses
            raise OSError("404")
        return [{"id": 7, "trackName": "Blessings", "artistName": "Calvin Harris", "duration": 220,
                 "syncedLyrics": "[00:10.00] count my blessings\n[00:14.00] count my blessings"}]

    monkeypatch.setattr(lyrics_ref, "_get", fake)
    assert lyrics_ref.fetch_reference("b", log=lambda *_: None)["artist"] == "Calvin Harris"
    assert calls == ["get", "search"]
    stored = lyrics_ref.load_reference("b")
    assert stored["id"] == 7 and [line["time"] for line in stored["lines"]] == [10.0, 14.0]


def _deezer(results, released):
    calls = []

    def fake(path, params=None):
        calls.append(path)
        if path == "search":
            return {"data": results[params["q"]]}
        return {"release_date": released[path]}

    return fake, calls


def test_hit_potential_scores_the_ingredients(monkeypatch, workspace):
    import datetime as dt

    from glass_harbor import potential
    from glass_harbor.lyrics_ref import parse_synced, reference_path

    write_fake_track("v", bpm=76, key="E", bars=16)
    write_fake_track("b", bpm=150, key="E", bars=32)
    for track, artist, title in (("v", "Don Toliver", "GLOCK"), ("b", "DABIN", "Stay With Me (feat. VELVETEARS)")):
        library.save_meta(track, {**library.load_meta(track), "artist": artist, "title": title})
    days = lambda n: (dt.date.today() - dt.timedelta(days=n)).isoformat()  # noqa: E731
    fake, calls = _deezer(
        {"don toliver GLOCK": [{"id": 1, "title": "GLOCK", "rank": 450_000, "artist": {"name": "Don Toliver"}}],
         "dabin Stay With Me (feat. VELVETEARS)": [
             {"id": 9, "title": "Stay With Me", "rank": 990_000, "artist": {"name": "Calvin Harris"}},
             {"id": 2, "title": "Stay With Me", "rank": 700_000, "artist": {"name": "Dabin"}}]},
        {"track/1": days(900), "track/2": days(60)})
    monkeypatch.setattr(potential, "_get", fake)
    reference_path("v").write_text(json.dumps({"lines": parse_synced(
        "[00:20.00] Glock in my hand\n[00:30.00] a long verse line that is not the hook at all\n"
        "[00:40.00] Glock in my hand\n[00:60.00] Glock in my hand")}))

    result = potential.assess("v", "b")
    # popular vocal + hit beat 36.25, fresh beat 15 + old vocal 1.25, 4-word hook x3 at 20 s 18.75, crossover 10
    assert result["score"] == 81 and result["level"] == "high"
    assert result["beat"]["artist"] == "Dabin"  # the same title by another artist is not this song
    assert result["hook"] == {"repeats": 3, "words": 4, "first_s": 20.0}
    assert any("crossover" in r for r in result["reasons"])
    potential.assess("v", "b")
    assert calls.count("search") == 2  # cached for a week
    (library.track_dir("b") / "popularity.json").write_text('{"checked": "20')  # a half-written cache
    assert potential.popularity("b")["artist"] == "Dabin" and calls.count("search") == 3  # looked up again


def test_popularity_reads_a_multi_artist_file_tag(monkeypatch, workspace):
    from glass_harbor import potential

    write_fake_track("b", bpm=130, key="Bm", bars=32)
    library.save_meta("b", {**library.load_meta("b"), "artist": "Calvin Harris; Clementine Douglas",
                            "title": "Blessings"})
    # Searched by the lead artist alone: Deezer finds nothing for a long credit ("1 Umbrella; Lil Bean; Lil Yee; ...").
    fake, _ = _deezer({"calvin harris Blessings": [
        {"id": 1, "title": "Blessings", "rank": 875_690, "artist": {"name": "Calvin Harris"}}]},
        {"track/1": "2025-05-09"})
    monkeypatch.setattr(potential, "_get", fake)
    assert potential.popularity("b")["rank"] == 875_690  # the lead of "A; B" is A


def test_crossover_needs_a_club_tempo_beat(workspace):
    from glass_harbor import potential

    write_fake_track("rap", bpm=90, key="E", bars=16)
    write_fake_track("rapbeat", bpm=90, key="E", bars=16)
    write_fake_track("house", bpm=126, key="E", bars=16)
    assert not any("crossover" in r for r in potential.assess("rap", "rapbeat")["reasons"])
    assert any("crossover" in r for r in potential.assess("rap", "house")["reasons"])


def test_hit_potential_treats_ambiguous_and_offline_lookups_as_unknown(monkeypatch, workspace):
    from glass_harbor import potential

    write_fake_track("swarm", bpm=150, key="E", bars=32)
    library.save_meta("swarm", {**library.load_meta("swarm"), "artist": "", "title": "SWARM"})
    fake, _ = _deezer({"SWARM": [{"id": 1, "title": "Swarm", "rank": 335_000, "artist": {"name": "elden"}},
                                 {"id": 2, "title": "Swarm", "rank": 50_000, "artist": {"name": "Risk"}}]}, {})
    monkeypatch.setattr(potential, "_get", fake)
    assert potential.popularity("swarm") is None  # two artists share the title: unknown beats wrong

    write_fake_track("v", bpm=76, key="E", bars=16)
    monkeypatch.setattr(potential, "_get", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    assert potential.popularity("v") is None and not (library.track_dir("v") / "popularity.json").exists()
    assert "unknown popularity" in potential.assess("v", "swarm", crossover=False)["reasons"][0]


def test_track_add_reads_artist_and_title_tags(workspace, tmp_path):
    import shutil
    import subprocess

    if not shutil.which("ffmpeg"):
        pytest.skip("needs ffmpeg")
    source = tmp_path / "SWARM.flac"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "1",
                    "-metadata", "artist=elden", "-metadata", "title=SWARM", str(source)], check=True)
    assert library.file_tags(source) == {"artist": "elden", "title": "SWARM"}


def test_a_rapped_vocal_skips_the_bass_separation(workspace, monkeypatch):
    from glass_harbor import analyze, auto, separate

    asked = []
    monkeypatch.setattr(separate, "separate_track", lambda track, stems, **k: asked.append(stems) or {})
    monkeypatch.setattr(separate, "clean_stem", lambda *a, **k: None)
    monkeypatch.setattr(analyze, "analyze_library_track", lambda *a, **k: None)
    monkeypatch.setattr(auto, "_lyrics", lambda *a, **k: None)
    write_fake_track("rap", bpm=95, key="Gm", bars=16)
    auto.prepare_vocal("rap", lambda m: None, kind="rap")
    auto.prepare_vocal("rap", lambda m: None, kind="sung")
    assert asked == [["vocals"], ["vocals", "bass"]]  # bass only to follow sung chords


def test_embedded_synced_lyrics_are_the_reference(workspace, tmp_path, monkeypatch):
    import shutil
    import subprocess

    from glass_harbor import lyrics_ref

    if not shutil.which("ffmpeg"):
        pytest.skip("needs ffmpeg")
    lrc = "[00:00.85] (Brutal Money)\n[00:03.10] \n[00:04.32] I am not your kinfolk\n[00:06.89] 1 Umbrella"
    tagged, plain = tmp_path / "Umbrella.flac", tmp_path / "Plain.flac"
    for path, extra in ((tagged, ["-metadata", f"LYRICS={lrc}"]), (plain, ["-metadata", "lyrics=just words"])):
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "1",
                        "-metadata", "artist=1 Umbrella; Lil Bean", "-metadata", "title=1 Umbrella", *extra,
                        str(path)], check=True)
    monkeypatch.setattr(lyrics_ref, "_get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no LRCLIB")))

    track, _ = library.add_track(tagged)
    reference = lyrics_ref.fetch_reference(track, log=lambda m: None)
    assert reference["source"] == "embedded" and lyrics_ref.load_reference(track) == reference
    assert [(line["time"], line["text"]) for line in reference["lines"]] == [
        (0.85, "(Brutal Money)"), (4.32, "I am not your kinfolk"), (6.89, "1 Umbrella")]  # blank lines dropped

    library.embedded_lyrics_path(track).unlink()
    assert library.add_track(tagged) == (track, False)  # added before lyrics were kept: a re-add picks them up
    assert library.embedded_lyrics_path(track).exists()

    other, _ = library.add_track(plain, track_id="plain")
    assert lyrics_ref.embedded_reference(other) is None  # plain text, no timestamps: not a reference


def test_a_clip_counts_as_masked_only_when_it_reads_weak_twice_running():
    from glass_harbor.auto import steady_weak

    assert steady_weak(None, {"weak": ["hook5"]}) == {"weak": []}  # one reading is not enough
    assert steady_weak({"hook5"}, {"weak": ["verse2"]}) == {"weak": []}  # a different clip each time: noise
    assert steady_weak({"hook5", "verse2"}, {"weak": ["verse2"]}) == {"weak": ["verse2"]}
    assert steady_weak({"verse2"}, None) == {"weak": []}


def test_a_single_weak_reading_gets_a_second_listen_before_it_counts(monkeypatch, workspace):
    from glass_harbor import auto

    _chant_song(workspace)
    plan = _plan_with_stems(workspace)
    plan["clips"].append({"id": "hook1", "source": "vox", "stem": "vocals", "from_bar": 1, "bars": 5, "at_bar": 23,
                          "chain": "hook"})
    shifts = []

    def second_reading(weak):
        def fake_listen(run_dir, log, *, shift_s=0.0):
            shifts.append(shift_s)
            return {"weak": weak}
        return fake_listen

    clean = {"vocal_presence": []}, {"flags": []}
    monkeypatch.setattr(auto, "_listen", second_reading([]))
    changes, latest = auto.fix_round(plan, *clean, {"weak": ["hook1"]}, None, workspace, lambda m: None)
    assert changes == [] and latest == set() and shifts == [auto.LISTEN_SHIFT_S]  # noise: the re-listen disagreed
    monkeypatch.setattr(auto, "_listen", second_reading(["hook1"]))
    changes, latest = auto.fix_round(plan, *clean, {"weak": ["hook1"]}, None, workspace, lambda m: None)
    assert plan["clips"][-1]["gain_db"] == 2.0 and latest == {"hook1"}  # confirmed by the second reading


def test_hearing_works_slice_by_slice_and_takes_each_overlap_word_once():
    import numpy as np

    from glass_harbor import audio as A
    from glass_harbor.listen import SLICE_S, hear, vocal_spans  # noqa: F401

    calls = []

    def fake_transcribe(audio):
        calls.append(audio.shape[0] / A.SR)
        # a word every second of the slice, named by its offset into the slice
        return [{"text": "", "words": [{"word": f"w{int(s)}", "start": float(s), "end": s + 0.3}
                                       for s in range(int(audio.shape[0] / A.SR))]}], "m", "b"

    audio = np.zeros((int(80 * A.SR), 2), dtype=np.float32)
    heard, model, backend = hear(audio, [(10.0, 50.0)], transcribe=fake_transcribe)
    assert all(c <= SLICE_S + 1e-6 for c in calls) and len(calls) == 2  # 9-51 s heard as two slices
    times = [t for _, t in heard]
    assert times == sorted(times) and len(times) == len(set(times))  # nothing doubled where slices overlap
    assert times[0] == 9.0 and times[-1] == 50.0 and model == "m"


def test_a_weak_clip_is_heard_again_on_its_own_window_before_it_counts():
    from glass_harbor.listen import settle_weak

    def clip(name, heard, start):
        return {"clip": name, "expected": 100, "heard": heard, "recall": heard / 100, "start_s": start,
                "end_s": start + 30}

    judged = [clip("verse2", 80, 0), clip("verse4", 38, 30), clip("verse5", 30, 60), clip("verse6", 75, 90)]
    windows = []
    own = {30: 66, 60: 25}  # verse4 was lost to a slice cut; verse5 really is buried

    def rehear(start, end):
        windows.append((start, end))
        return ["word"] * own[start]

    weak = settle_weak(judged, {c["clip"]: len for c in judged}, rehear)
    assert weak == ["verse5"] and windows == [(30, 60), (60, 90)]  # only the weak ones are heard again
    assert judged[1]["recall"] == 0.66 and judged[1]["pass_recall"] == 0.38  # the better reading, both kept
    assert judged[2]["recall"] == 0.3 and "pass_recall" not in judged[2]  # no better on its own


def test_a_shifted_reading_moves_the_slice_boundaries():
    import numpy as np

    from glass_harbor import audio as A
    from glass_harbor.listen import hear

    lengths = []

    def fake_transcribe(audio):
        lengths.append(round(audio.shape[0] / A.SR, 1))
        return [], "m", "b"

    audio = np.zeros((int(80 * A.SR), 2), dtype=np.float32)
    hear(audio, [(10.0, 50.0)], transcribe=fake_transcribe)
    hear(audio, [(10.0, 50.0)], shift_s=10.0, transcribe=fake_transcribe)
    assert lengths[0] == 28.0 and lengths[2] == 18.0  # the second reading's first cut comes 10 s earlier


def test_fix_rounds_pull_back_a_vocal_that_buries_the_beat(workspace):
    from glass_harbor.auto import apply_qa_fixes

    _chant_song(workspace)
    plan = _plan_with_stems(workspace)
    plan["clips"].append({"id": "verse1", "source": "vox", "stem": "vocals", "from_bar": 6, "bars": 12, "at_bar": 33})
    buried = [{"bar": b, "db": -5.0} for b in (40, 41, 42)]
    balance = lambda mix: [{"track": "vox", "clips": ["verse1"], "mix_lu": mix, "record_lu": -4.0}]  # noqa: E731
    changes = apply_qa_fixes(plan, {"vocal_presence": buried, "vocal_balance": balance(5.0)}, {"flags": []})
    verse = next(c for c in plan["clips"] if c["id"] == "verse1")
    # 9 LU over its own record is 3 past the 6 LU limit: back down to it, and the buried bars do not lift it
    assert verse["gain_db"] == -3.0 and any("own record" in c for c in changes)
    assert not any("buried" in c for c in changes)
    verse.pop("gain_db")
    plan.pop("auto")
    # 1 dB of room left: a +2 dB lift would cross the limit, so the buried bars are left to the ears
    assert apply_qa_fixes(plan, {"vocal_presence": buried, "vocal_balance": balance(1.0)}, {"flags": []}) == []
    assert "gain_db" not in verse
    # Any excess QA warns about gets corrected, rounded down so the vocal lands under the limit
    apply_qa_fixes(plan, {"vocal_presence": [], "vocal_balance": balance(2.04)}, {"flags": []})
    assert verse["gain_db"] == -0.1
    # The beat's own vocal is measured like any other, so it is pulled back too (though never lifted)
    plan["clips"].append({"id": "bed-hook", "source": "bed", "stem": "vocals", "from_bar": 40, "bars": 8, "at_bar": 81})
    over = [{"track": "bed", "clips": ["bed-hook"], "mix_lu": 3.0, "record_lu": -4.0}]
    apply_qa_fixes(plan, {"vocal_presence": [], "vocal_balance": over}, {"flags": []})
    assert next(c for c in plan["clips"] if c["id"] == "bed-hook")["gain_db"] == -1.0
