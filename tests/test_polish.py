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
