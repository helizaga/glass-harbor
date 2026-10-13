import json

import numpy as np
import pytest
from conftest import write_fake_track

from glass_harbor import audio as A
from glass_harbor import drums as kit
from glass_harbor import fx, library, vocals
from glass_harbor.grid import build_grid
from glass_harbor.lyrics import lyrics_path
from glass_harbor.plan import resolve
from glass_harbor.render import small_speaker_bass, tame_harshness
from glass_harbor.scaffold import add_dj_edges, add_edit, add_fills, build_set

SR = A.SR


def _rms(x):
    return float(np.sqrt(np.mean(np.asarray(x, dtype=np.float64) ** 2)) + 1e-12)


def _kit(bars=8, bpm=120.0):
    beat = 60 / bpm
    n = int((bars * 4 + 1) * beat * SR)
    out = np.zeros(n)
    rng = np.random.default_rng(0)
    t_kick = np.arange(int(0.15 * SR)) / SR
    kick = np.sin(2 * np.pi * np.cumsum(50 + 80 * np.exp(-t_kick * 30)) / SR) * np.exp(-t_kick * 20)
    snare = rng.standard_normal(int(0.15 * SR)) * np.exp(-np.arange(int(0.15 * SR)) / SR * 25) * 0.6
    for b in range(bars * 4):
        pos = int(b * beat * SR)
        hit = kick if b % 2 == 0 else snare
        out[pos:pos + hit.size] += hit
    beats = np.arange(bars * 4 + 1) * beat
    return np.repeat(out[:, None], 2, axis=1).astype(np.float32), build_grid(beats, beats[::4], n / SR)


def test_find_snare_roll_and_crash_fallback():
    drums, grid = _kit()
    hit = kit.find_snare(drums, grid)
    assert hit is not None
    beat_index = round(hit.start / 0.5)
    assert beat_index % 2 == 1 and abs(hit.start - beat_index * 0.5) < 0.02  # on beat 2 or 4
    snare = drums[int(hit.start * SR): int((hit.start + hit.length) * SR)]
    roll = kit.snare_roll(snare, 2.0, 0.5)
    assert roll.shape[0] == 2 * SR
    first, last = roll[: SR // 2], roll[-SR // 2:]
    assert _rms(last) > 2 * _rms(first)  # louder and denser toward the drop
    crash = kit.synth_crash(1.0)
    assert crash.shape == (SR * 1, 2) and _rms(crash[: SR // 10]) > 3 * _rms(crash[-SR // 10:])


def test_punch_sharpens_transients_and_keeps_level():
    drums, _ = _kit()
    out = kit.punch(drums, attack_db=4.0, parallel=0.3)
    crest_in = np.max(np.abs(drums)) / _rms(drums)
    crest_out = np.max(np.abs(out)) / _rms(out)
    assert crest_out > crest_in and abs(20 * np.log10(_rms(out) / _rms(drums))) < 0.5


def test_vocal_riser_swell_and_tape_stop():
    t = np.arange(int(0.4 * SR)) / SR
    word = np.repeat((0.3 * np.sin(2 * np.pi * 300 * t) * np.hanning(t.size))[:, None], 2, axis=1).astype(np.float32)
    riser = fx.vocal_riser(word, 2.0)
    assert riser.shape[0] == 2 * SR and _rms(riser[-SR // 2:]) > 3 * _rms(riser[: SR // 2])
    assert np.max(np.abs(riser[-20:])) < 0.05  # stops dead on the downbeat
    swell = fx.reverse_swell(word, 1.0)
    assert swell.shape[0] == SR and _rms(swell[-SR // 4:]) > 2 * _rms(swell[: SR // 4])
    tone = np.repeat((0.5 * np.sin(2 * np.pi * 220 * np.arange(SR) / SR))[:, None], 2, axis=1).astype(np.float32)
    stopped = fx.tape_stop(tone)
    assert stopped.shape == tone.shape and _rms(stopped[-SR // 8:]) < 0.1 * _rms(stopped[: SR // 8])


def test_harshness_and_small_speaker_bass():
    t = np.arange(4 * SR) / SR
    base = 0.2 * np.sin(2 * np.pi * 200 * t)
    harsh = base + np.where((t > 1.5) & (t < 2.5), 0.3 * np.sin(2 * np.pi * 3000 * t), 0.02 * np.sin(2 * np.pi * 3000 * t))
    mix = np.repeat(harsh[:, None], 2, axis=1).astype(np.float32)
    out = tame_harshness(mix)
    burst = slice(int(1.7 * SR), int(2.3 * SR))
    assert _rms(out[burst]) < _rms(mix[burst]) * 0.85
    assert np.allclose(out[: SR // 2], mix[: SR // 2], atol=0.02)
    sub = np.repeat((0.4 * np.sin(2 * np.pi * 60 * t))[:, None], 2, axis=1).astype(np.float32)
    spec = lambda x: np.abs(np.fft.rfft(A.mono(x)))  # noqa: E731
    f = np.fft.rfftfreq(sub.shape[0], 1 / SR)
    band = (f > 170) & (f < 400)
    assert spec(small_speaker_bass(sub))[band].sum() > 10 * spec(sub)[band].sum()


def test_layers_widen_and_tune_pulls_toward_key():
    t = np.arange(2 * SR) / SR
    voice = np.repeat((0.2 * np.sin(2 * np.pi * 300 * t))[:, None], 2, axis=1).astype(np.float32)
    layered = vocals.add_layers(voice, doubles=True, octave=False)
    side = lambda x: x[:, 0] - x[:, 1]  # noqa: E731
    assert _rms(side(layered)) > 10 * _rms(side(voice)) + 1e-6
    sharp = 440 * 2 ** (40 / 1200)  # A4 + 40 cents
    sung = np.repeat((0.3 * np.sin(2 * np.pi * sharp * t))[:, None], 2, axis=1).astype(np.float32)
    tuned, cents = vocals.tune(sung, 9, "minor", 1.0)
    assert cents > 20
    spectrum = np.abs(np.fft.rfft(A.mono(tuned[SR // 2: -SR // 2])))
    peak = np.fft.rfftfreq(SR, 1 / SR)[np.argmax(spectrum)]
    assert abs(peak - 440) < abs(sharp - 440)


def _mashup(workspace_lyrics=True):
    write_fake_track("vox", bpm=124, key="Am", bars=24)
    write_fake_track("bed", bpm=124, key="Am", bars=48, stems=("instrumental", "drums", "bass", "other"))
    library.save_analysis("bed", {**library.load_analysis("bed"), "drops": [9]})
    if workspace_lyrics:
        segs = [{"start": 4.0 * i, "end": 4.0 * i + 1.0, "text": "call my phone",
                 "words": [{"word": "call", "start": 4.0 * i, "end": 4.0 * i + 0.3, "prob": 1},
                           {"word": "phone", "start": 4.0 * i + 0.4, "end": 4.0 * i + 1.0, "prob": 1}]} for i in range(10)]
        lyrics_path("vox").write_text(json.dumps({"segments": segs}))
    return {"version": 1, "kind": "mashup", "bpm": 124, "sources": {"vox": {"track": "vox"}, "bed": {"track": "bed"}},
            "clips": [{"id": "bed", "source": "bed", "stem": "instrumental", "from_bar": 1, "bars": 32, "at_bar": 1,
                       "automation": {"gain_db": [[24, 0], [32, -40]]}},
                      {"id": "verse", "source": "vox", "stem": "vocals", "from_bar": 1, "bars": 8, "at_bar": 9},
                      {"id": "hook", "source": "vox", "stem": "vocals", "from_bar": 9, "bars": 8, "at_bar": 17,
                       "chain": "hook"}]}


def test_dj_edges_shift_and_wrap_the_edit(workspace):
    plan = add_dj_edges(_mashup(), intro_bars=16, outro_bars=16)
    res = resolve(plan)
    assert res.ok, [i.to_dict() for i in res.issues]
    ids = {c["id"]: c for c in plan["clips"]}
    assert ids["intro-drums"]["at_bar"] == 1 and ids["intro-bass"]["at_bar"] == 9
    assert ids["verse"]["at_bar"] == 25 and ids["bed"]["at_bar"] == 17
    assert ids["outro-drums"]["at_bar"] == 49 and ids["intro-drums"]["from_bar"] == 9
    assert ids["bed"]["automation"]["gain_db"] == [[24, 0]]  # the fade-out gave way to the outro


def _with_levels(silent_bars, breaks):
    """The _mashup bed with its drums and bass silent on ``silent_bars`` and dropping out on ``breaks``."""
    plan = _mashup()
    analysis = library.load_analysis("bed")
    for stem in ("drums", "bass"):
        levels = [-10.0] * 48
        for bar in silent_bars:
            levels[bar - 1] = -70.0
        for bar in breaks:
            levels[bar - 1] = -25.0
        analysis["stems"][stem]["bar_db"] = levels
    library.save_analysis("bed", analysis)
    return plan


def test_dj_edges_loop_skips_the_beats_break_and_bridge_its_dead_air(workspace):
    plan = add_dj_edges(_with_levels(silent_bars=[1], breaks=[15, 16]), intro_bars=16, outro_bars=16)
    assert resolve(plan).ok
    ids = {c["id"]: c for c in plan["clips"]}
    # bars 9-16 run into the break, so the loop is the drop's first 4 bars, played 4 times (bass twice)
    assert (ids["intro-drums"]["from_bar"], ids["intro-drums"]["bars"], ids["intro-drums"]["loop"]) == (9, 4, 4)
    assert (ids["intro-bass"]["loop"], ids["outro-drums"]["loop"], ids["outro-bass"]["loop"]) == (2, 4, 2)
    # the bed's silent first bar (now bar 17) gets the intro's groove instead of a hole
    bridge = ids["intro-drums-bridge"]
    assert (bridge["at_bar"], bridge["bars"], bridge["from_bar"]) == (17, 1, 9) and "intro-bass-bridge" in ids
    assert any("1 silent opening bar" in n for n in plan["notes"])
    # the record's own low end steps aside under the bridge: never two basslines at once
    assert ids["bed"]["automation"]["eq_low_db"] == [[0, -24.0], [0.998, -24.0], [1, 0.0]]
    assert not any("two basslines" in i.message for i in resolve(plan).issues)


def test_dj_outro_starts_where_the_beat_ends_under_a_vocal_that_runs_on(workspace):
    plan = _mashup()
    plan["clips"][2]["at_bar"] = 29  # the hook runs to bar 37, four bars past the beat's end at 33
    plan = add_dj_edges(plan, intro_bars=0, outro_bars=16)
    assert resolve(plan).ok
    ids = {c["id"]: c for c in plan["clips"]}
    assert ids["outro-drums"]["at_bar"] == 33 and ids["outro-bass"]["at_bar"] == 33  # no bars of vocal on silence


def test_dj_edges_loop_moves_past_a_break_inside_the_drop(workspace):
    plan = add_dj_edges(_with_levels(silent_bars=[], breaks=[11]), intro_bars=16, outro_bars=16)
    ids = {c["id"]: c for c in plan["clips"]}
    assert (ids["intro-drums"]["from_bar"], ids["intro-drums"]["bars"]) == (12, 8)  # first clean 8 bars after it
    assert not any(i.endswith("-bridge") for i in ids)


def test_trim_run_up_starts_on_a_section_of_the_beat_and_keeps_the_vocal_on_its_bar(workspace):
    from glass_harbor.scaffold import trim_run_up

    plan = _mashup()
    plan["clips"][1]["at_bar"], plan["clips"][2]["at_bar"] = 13, 21  # 12 bars of beat before the verse
    plan["clips"].append({"id": "early-fx", "generate": "riser", "at_bar": 3, "bars": 2})
    beat = {"sections": [{"start_bar": 1}, {"start_bar": 7}, {"start_bar": 17}], "drops": []}
    trim_run_up(plan, beat, keep_bars=4)
    assert resolve(plan).ok
    ids = {c["id"]: c for c in plan["clips"]}
    # bar 7 is the latest section start at least 4 bars before the verse: the edit starts there
    assert (ids["verse"]["at_bar"], ids["hook"]["at_bar"]) == (7, 15)
    assert (ids["bed"]["at_bar"], ids["bed"]["from_bar"], ids["bed"]["bars"]) == (1, 7, 26)  # same beat bar under it
    assert ids["bed"]["automation"]["gain_db"] == [[0, 0.0], [18, 0], [26, -40]]  # the fade moves with it
    assert "early-fx" not in ids  # it only played in the cut run-up

    plan = _mashup()
    plan["clips"][1]["at_bar"], plan["clips"][2]["at_bar"] = 13, 21
    del plan["bpm"]
    plan["tempo"] = [{"bar": 1, "bpm": 124}, {"bar": 5, "bpm": 120}, {"bar": 9, "bpm": 128, "ramp": True},
                     {"bar": 25, "bpm": 126}]
    plan["clips"] += [
        {"id": "riser", "generate": "riser", "at_bar": 3, "bars": 8},  # runs on past the cut at bar 7
        {"id": "beat-chop", "source": "bed", "stem": "instrumental", "at_bar": 5, "bars": 4,
         "chop": {"slices": {"a": {"bar": 1, "beat": 1, "beats": 1}},
                  "pattern": ["a---............", ".a--............", "..a-............", "...a............"]}}]
    trim_run_up(plan, beat, keep_bars=4)
    assert resolve(plan).ok, [i.to_dict() for i in resolve(plan).issues]
    ids = {c["id"]: c for c in plan["clips"]}
    assert (ids["riser"]["at_bar"], ids["riser"]["bars"]) == (1, 4)  # shorter, not gone
    assert ids["beat-chop"]["bars"] == 2 and ids["beat-chop"]["chop"]["pattern"].startswith("..a-")  # picked up at the cut
    # the map opens on the tempo at the cut, half way up the 120 -> 128 ramp, and keeps what follows
    assert plan["tempo"] == [{"bar": 1, "bpm": 124.0}, {"bar": 3, "bpm": 128, "ramp": True}, {"bar": 19, "bpm": 126}]

    plan = _mashup()  # without a section start in reach, exactly keep_bars before the vocal
    trim_run_up(plan, {"sections": [{"start_bar": 1}]}, keep_bars=4)
    assert {c["id"]: c["at_bar"] for c in plan["clips"]}["verse"] == 5


def test_a_vocal_first_taste_skips_the_dj_intro(workspace):
    from glass_harbor.feedback import load_taste, save_taste
    from glass_harbor.scaffold import build_mashup

    _mashup()  # the tracks
    plan_default = build_mashup("vox", "bed")
    taste = load_taste()
    taste["defaults"]["run_up_bars"] = 4
    save_taste(taste)
    plan = build_mashup("vox", "bed")
    first = lambda p: min(c["at_bar"] for c in p["clips"] if c.get("stem") == "vocals")  # noqa: E731
    assert not any(c["id"].startswith("intro-") for c in plan["clips"])  # no DJ intro
    assert any(c["id"].startswith("outro-") for c in plan["clips"])  # the outro stays
    assert first(plan) <= 5 < first(plan_default)


def test_fills_and_edits(workspace):
    plan = add_fills(_mashup())
    gens = {c["id"]: c for c in plan["clips"] if "generate" in c}
    assert "crash-17" in gens and gens["swell-17"]["word"] == "call" and gens["swell-17"]["at_bar"] == 16
    assert resolve(plan).ok
    plan = add_edit(plan, "mute", 16.5, beats=2)
    bed = next(c for c in plan["clips"] if c["id"] == "bed")
    assert any(p[1] == -60 for p in bed["automation"]["arrange_db"])
    plan = add_edit(plan, "stutter", 24, word="phone", pattern="j-j-jjjj")
    assert any(c["id"] == "stutter-24" for c in plan["clips"])
    plan = add_edit(plan, "tape_stop", 24.5, beats=2)
    assert plan["edits"][-1]["type"] == "tape_stop"
    assert resolve(plan).ok, [i.to_dict() for i in resolve(plan).issues]
    with pytest.raises(ValueError, match="split"):
        add_edit(plan, "lift", 20)


def test_fills_mark_sections_not_every_chant(workspace):
    plan = _mashup()
    plan["clips"][2].update(bars=2)  # short chants at 17, 21, and 33
    plan["clips"] += [{"id": f"chant{bar}", "source": "vox", "stem": "vocals", "from_bar": 9, "bars": 2,
                       "at_bar": bar, "chain": "hook"} for bar in (21, 33)]
    gens = {c["id"] for c in add_fills(plan)["clips"] if "generate" in c}
    assert {"crash-17", "crash-33", "swell-17", "swell-33"} <= gens
    assert "crash-21" not in gens and "swell-21" not in gens


def test_stem_swap_set(workspace):
    for name in ("a", "b"):
        write_fake_track(name, bpm=124, key="Am", bars=64, stems=("vocals", "drums", "bass", "other"))
    plan = build_set(["a", "b"], styles=["stems"], play_bars=32, blend_bars=16)
    res = resolve(plan)
    assert res.ok, [i.to_dict() for i in res.issues]
    ids = [c["id"] for c in plan["clips"]]
    assert {"t1-vocals-out", "t1-bass-out", "t1-other-out", "t2-drums-in", "t2-bass-in", "t2-other-in"} <= set(ids)
    main_b = next(c for c in plan["clips"] if c["id"] == "t2")
    assert main_b["from_bar"] == 17 and not any("two basslines" in i.message for i in res.issues)
