from conftest import write_fake_track

from glass_harbor import scaffold
from glass_harbor.plan import automation_value, resolve


def _plan(**overrides):
    plan = {
        "version": 1,
        "title": "t",
        "kind": "mashup",
        "bpm": 124,
        "sources": {"a": {"track": "song-a"}, "b": {"track": "song-b"}},
        "clips": [
            {"id": "bed", "source": "b", "stem": "mix", "from_bar": 1, "bars": 16, "at_bar": 1},
            {"id": "vox", "source": "a", "stem": "vocals", "from_bar": 1, "bars": 8, "at_bar": 5},
        ],
    }
    plan.update(overrides)
    return plan


def _levels(res):
    return {(i.level, i.message.split(" ")[0]) for i in res.issues}


def test_valid_plan_resolves(workspace):
    write_fake_track("song-a", bpm=122, key="Am", bars=32)
    write_fake_track("song-b", bpm=124, key="C", bars=32)
    res = resolve(_plan())
    assert res.ok, [i.to_dict() for i in res.issues]
    vox = res.clips[1]
    assert vox.out_start_beat == 16
    assert vox.src_beats == 32
    assert vox.stretch_pct == __import__("pytest").approx(124 / 122 * 100 - 100, abs=0.05)


def test_missing_track_and_stem_are_errors(workspace):
    write_fake_track("song-b", bpm=124, key="C", bars=32, stems=())
    res = resolve(_plan(sources={"a": {"track": "nope"}, "b": {"track": "song-b"}}))
    assert not res.ok
    plan = _plan()
    plan["sources"]["a"]["track"] = "song-b"
    res = resolve(plan)
    assert any("no vocals stem" in i.message for i in res.issues)


def test_bass_clash_warning_and_eq_fix(workspace):
    write_fake_track("song-a", bpm=124, key="Am", bars=32)
    write_fake_track("song-b", bpm=124, key="Am", bars=32)
    clips = [
        {"id": "a", "source": "a", "stem": "mix", "from_bar": 1, "bars": 16, "at_bar": 1},
        {"id": "b", "source": "b", "stem": "mix", "from_bar": 1, "bars": 16, "at_bar": 9},
    ]
    res = resolve(_plan(clips=clips))
    assert any("two basslines" in i.message for i in res.issues)
    clips[1]["automation"] = {"eq_low_db": [[0, -40], [8, -40], [8.01, 0]]}
    clips[0]["automation"] = {"eq_low_db": [[15.99, 0], [16, -40]]}
    res = resolve(_plan(clips=clips))
    assert not any("two basslines" in i.message for i in res.issues)


def test_key_clash_and_stretch_warnings(workspace):
    write_fake_track("song-a", bpm=100, key="8A", bars=32)
    write_fake_track("song-b", bpm=124, key="3A", bars=32)
    res = resolve(_plan())
    messages = " ".join(i.message for i in res.issues)
    assert "Camelot" in messages
    assert "time-stretch" in messages


def test_structural_errors(workspace):
    write_fake_track("song-a", bpm=124, key="Am", bars=32)
    write_fake_track("song-b", bpm=124, key="Am", bars=32)
    bad = _plan()
    bad["clips"][0]["automation"] = {"wobble": [[0, 1]]}
    bad["clips"][1]["fx"] = {"echo": {"mix": 2}}
    del bad["bpm"]
    res = resolve(bad)
    assert not res.ok
    bad = _plan()
    bad["clips"][0]["bars"] = 0
    assert not resolve(bad).ok


def test_automation_interpolation():
    points = [[0, 20], [4, 2000]]
    assert automation_value(points, 2, 0, log_scale=True) == __import__("pytest").approx(200)
    assert automation_value(points, -1, 0) == 20
    assert automation_value(points, 9, 0) == 2000
    assert automation_value(None, 3, 7) == 7


def test_transition_scaffold_blend_for_edm(workspace):
    write_fake_track("house-a", bpm=124, key="Am", bars=96)
    write_fake_track("house-b", bpm=126, key="Em", bars=96)
    plan = scaffold.build_transition("house-a", "house-b")
    res = resolve(plan)
    assert res.ok, [i.to_dict() for i in res.issues]
    assert any("16-bar blend" in note for note in plan["notes"])
    incoming = next(c for c in plan["clips"] if c["source"] == "t2")
    assert incoming["bars"] >= 16 + 8  # b keeps playing after the blend instead of fading with a
    fade_start = incoming["automation"]["gain_db"][-2][0]
    assert fade_start >= 16 + 8
    assert not any("two basslines" in i.message for i in res.issues)
    assert plan["tempo"][-1]["bpm"] == 126


def test_set_scaffold_echo_for_big_tempo_gap_and_halftime(workspace):
    write_fake_track("rap-a", bpm=92, key="Fm", bars=80)
    write_fake_track("edm-b", bpm=128, key="Fm", bars=96)
    write_fake_track("trap-c", bpm=70, key="Fm", bars=80)
    plan = scaffold.build_set(["rap-a", "edm-b", "trap-c"], play_bars=24)
    res = resolve(plan)
    assert res.ok, [i.to_dict() for i in res.issues]
    assert "echo" in plan["notes"][0]
    assert any(c["id"] == "t1-echo" for c in plan["clips"])
    bpms = [p["bpm"] for p in plan["tempo"]]
    assert bpms[0] == 92 and 128 in bpms


def test_mashup_scaffold_picks_tempo_ratio(workspace):
    write_fake_track("acapella", bpm=70, key="Gm", bars=40)
    write_fake_track("trap-beat", bpm=140, key="Gm", bars=64, stems=("instrumental",))
    plan = scaffold.build_mashup("acapella", "trap-beat")
    assert plan["sources"]["vox"].get("tempo_ratio") == 2
    res = resolve(plan)
    assert res.ok, [i.to_dict() for i in res.issues]


def test_automation_is_anchored_at_at_bar_with_pickups(workspace):
    write_fake_track("song-a", bpm=120, key="Am", bars=32)
    write_fake_track("song-b", bpm=120, key="Am", bars=32)
    clips = [
        {"id": "a", "source": "a", "stem": "mix", "from_bar": 1, "bars": 8, "at_bar": 1,
         "automation": {"eq_low_db": [[3.99, 0], [4, -40]]}},
        {"id": "b", "source": "b", "stem": "mix", "from_bar": 5, "bars": 8, "at_bar": 5, "pre_beats": 2,
         "automation": {"eq_low_db": [[0, -40], [4, -40], [4.01, 0]]}},
    ]
    res = resolve(_plan(clips=clips))
    b = res.clips[1]
    assert b.anchor_beat == 16 and b.out_start_beat == 14
    assert not any("two basslines" in i.message for i in res.issues)


def test_reference_stem_is_validated(workspace):
    write_fake_track("song-a", bpm=124, key="Am", bars=32)
    write_fake_track("song-b", bpm=124, key="Am", bars=32)
    plan = _plan(master={"reference": {"track": "song-b", "stem": "drums"}})
    assert any("no drums stem" in i.message for i in resolve(plan).issues)
    plan = _plan(master={"reference": {"track": "song-b", "stem": "piano"}})
    assert not resolve(plan).ok
