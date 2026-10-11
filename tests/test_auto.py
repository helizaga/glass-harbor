import json

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
