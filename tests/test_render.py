import json

import numpy as np
import pytest

from glass_harbor import audio as A
from glass_harbor import library
from glass_harbor.analyze import analyze_track
from glass_harbor.check import check_run
from glass_harbor.render import grid_deviation_ms, render_plan, warp


def _add(synth_files, name, bpm, key, **kwargs):
    paths = synth_files(name, bpm, key, **kwargs)
    stems = {k: v for k, v in paths.items() if k in ("vocals", "instrumental")}
    track_id, _ = library.add_track(paths["mix"], track_id=name, stems=stems)
    audio = library.load_audio(track_id)
    analysis = analyze_track(audio, beat_backend="librosa",
                             stems={s: library.load_audio(track_id, s) for s in library.available_stems(track_id)})
    library.save_analysis(track_id, analysis)
    return analysis


def test_warp_hits_exact_length_and_beats():
    sr = A.SR
    src_beats = np.arange(17) * 0.5  # 120 bpm
    clicks = np.zeros((int(8.5 * sr), 2), dtype=np.float32)
    for t in src_beats[:-1]:
        clicks[int(t * sr): int(t * sr) + 200] = 0.8
    tgt = np.arange(17) * (60 / 126)
    out = warp(clicks[: int(8 * sr)], src_beats, tgt, 0)
    assert out.shape[0] == int(round(tgt[-1] * sr))
    dev, spread, coverage = grid_deviation_ms(out, list(tgt[:-1]))
    assert coverage > 0.8
    assert abs(dev) < 8


def test_analysis_on_synthetic_track(workspace, synth_files):
    analysis = _add(synth_files, "house-a", 124, "Am", bars=24, lead_in=0.31)
    assert analysis["bpm"] == pytest.approx(124, abs=1.0)
    assert analysis["key"]["camelot"] in ("8A", "8B")  # A minor or its relative major
    assert analysis["grid"]["bar_count"] >= 22
    bar1 = analysis["grid"]["beats"][analysis["grid"]["first_downbeat"]]
    assert (bar1 - 0.31) % (60 / 124 * 4) == pytest.approx(0, abs=0.03) or \
        (bar1 - 0.31) % (60 / 124 * 4) == pytest.approx(60 / 124 * 4, abs=0.03)


def test_render_transition_and_qa(workspace, synth_files, tmp_path):
    _add(synth_files, "a", 124, "Am", bars=24, seed=1)
    _add(synth_files, "b", 128, "Em", bars=24, seed=2)
    plan = {
        "version": 1, "title": "test", "kind": "transition", "bpm": 124,
        "sources": {"a": {"track": "a"}, "b": {"track": "b"}},
        "clips": [
            {"id": "a", "source": "a", "from_bar": 1, "bars": 16, "at_bar": 1,
             "automation": {"eq_low_db": [[11.9, 0], [12, -40]], "gain_db": [[14, 0], [16, -40]]}},
            {"id": "b", "source": "b", "from_bar": 1, "bars": 16, "at_bar": 9,
             "automation": {"eq_low_db": [[0, -40], [3.9, -40], [4, 0]], "highpass_hz": [[0, 300], [4, 20]]}},
        ],
        "master": {"lufs": -14, "ceiling_db": -1},
    }
    out = tmp_path / "run"
    report = render_plan(plan, out, mp3=False, write_clips=True, log=lambda m: None)
    expected = (24 * 4) * 60 / 124
    assert report["duration_s"] == pytest.approx(expected, abs=0.1)
    for clip in report["clips"]:
        assert clip["warp_offset_ms"] is not None and abs(clip["warp_offset_ms"]) < 12, clip
        assert 0.0 <= clip["notes"]["warp_coverage"] <= 1.0, clip  # QA's sparse-vocal rule reads it from here
    assert len(list((out / "clips").glob("*.wav"))) == 2
    qa = check_run(out)
    assert qa["loudness_lufs"] == pytest.approx(-14, abs=1.0)
    assert qa["true_peak_db"] <= -0.5
    assert qa["verdict"] != "fail"
    assert json.loads((out / "qa.json").read_text())["verdict"] == qa["verdict"]


def test_render_mashup_with_pitch_and_halftime(workspace, synth_files, tmp_path):
    _add(synth_files, "vox", 75, "Gm", bars=12, with_vocal=True, seed=3)
    _add(synth_files, "beat", 140, "Am", bars=24, seed=4)
    plan = {
        "version": 1, "title": "mash", "kind": "mashup", "bpm": 140,
        "sources": {"vox": {"track": "vox", "semitones": 2, "tempo_ratio": 2}, "bed": {"track": "beat"}},
        "clips": [
            {"id": "bed", "source": "bed", "stem": "instrumental", "from_bar": 1, "bars": 24, "at_bar": 1},
            {"id": "v", "source": "vox", "stem": "vocals", "from_bar": 1, "bars": 8, "at_bar": 5, "pre_beats": 1,
             "fx": {"reverb": {"mix": 0.1}}},
        ],
    }
    report = render_plan(plan, tmp_path / "mash", mp3=False, log=lambda m: None)
    vocal = next(c for c in report["clips"] if c["id"] == "v")
    assert vocal["stretch_pct"] == pytest.approx((140 / 150 - 1) * 100, abs=0.5)
    assert vocal["length_s"] == pytest.approx((8 * 4 + 1) * 2 * 60 / 140, abs=0.01)


def test_range_render_crops(workspace, synth_files, tmp_path):
    _add(synth_files, "a", 120, "C", bars=16, seed=5)
    plan = {"version": 1, "title": "r", "kind": "set", "bpm": 120, "sources": {"a": {"track": "a"}},
            "clips": [{"id": "a", "source": "a", "from_bar": 1, "bars": 16, "at_bar": 1}]}
    report = render_plan(plan, tmp_path / "range", start_bar=5, end_bar=8, mp3=False, log=lambda m: None)
    assert report["duration_s"] == pytest.approx(4 * 4 * 0.5, abs=0.05)


def test_vocal_chops_land_on_steps(workspace, synth_files, tmp_path):
    _add(synth_files, "vox", 120, "Am", bars=8, with_vocal=True, seed=6)
    plan = {
        "version": 1, "title": "chops", "kind": "mashup", "bpm": 124,
        "sources": {"vox": {"track": "vox"}},
        "clips": [{
            "id": "chops", "source": "vox", "stem": "vocals", "at_bar": 1, "bars": 2,
            "chop": {"slices": {"a": {"bar": 1, "beat": 1, "beats": 0.5},
                                "b": {"bar": 1, "beat": 2, "beats": 0.25, "semitones": 5, "reverse": True}},
                     "pattern": "a---a-b-a.--b-a-"},
        }],
    }
    report = render_plan(plan, tmp_path / "chops", mp3=False, log=lambda m: None)
    assert report["duration_s"] == pytest.approx(8 * 60 / 124, abs=0.05)
    audio = A.load(tmp_path / "chops" / "mix.wav")
    step = 60 / 124 / 4
    # Steps 9-11 are a rest ('.') then holds: near silence there.
    rest = audio[int((9 * step + 0.01) * A.SR): int((12 * step - 0.01) * A.SR)]
    hit = audio[int(0.005 * A.SR): int(step * 2 * A.SR)]
    assert np.sqrt(np.mean(rest**2)) < 0.1 * np.sqrt(np.mean(hit**2))


def test_chop_validation_errors(workspace, synth_files):
    from glass_harbor.plan import resolve

    _add(synth_files, "vox", 120, "Am", bars=8, with_vocal=True, seed=7)
    plan = {"version": 1, "kind": "mashup", "bpm": 120, "sources": {"vox": {"track": "vox"}},
            "clips": [{"source": "vox", "stem": "vocals", "at_bar": 1, "bars": 1,
                       "chop": {"slices": {"ab": {"bar": 1, "beat": 1, "beats": 1}}, "pattern": "x---"}}]}
    res = resolve(plan)
    assert not res.ok
    messages = " ".join(i.message for i in res.issues)
    assert "single letter" in messages


def test_short_edit_trims_the_run_up_and_tail_and_drops_a_repeated_hook_section(workspace):
    from glass_harbor.edit import plan_short_edit
    from glass_harbor.plan import resolve
    from conftest import write_fake_track

    write_fake_track("vox", bpm=75, key="Am", bars=48)
    write_fake_track("beat", bpm=150, key="Am", bars=140, stems=("instrumental",))
    hook = {"source": "vox", "stem": "vocals", "from_bar": 9, "bars": 7}
    plan = {"version": 1, "kind": "mashup", "bpm": 150, "sources": {"vox": {"track": "vox", "tempo_ratio": 2.0},
                                                                    "bed": {"track": "beat"}},
            "clips": [{"id": "bed", "source": "bed", "stem": "instrumental", "from_bar": 1, "bars": 134, "at_bar": 1},
                      {"id": "intro1", "source": "vox", "stem": "vocals", "from_bar": 5, "bars": 4, "at_bar": 9},
                      {"id": "hook1", **hook, "at_bar": 17},
                      {"id": "verse1", "source": "vox", "stem": "vocals", "from_bar": 24, "bars": 8, "at_bar": 33},
                      {"id": "hook2", **hook, "at_bar": 66},  # a repeat of hook1 on the second drop
                      {"id": "chant1", "source": "vox", "stem": "vocals", "from_bar": 33, "bars": 11, "at_bar": 82,
                       "pre_beats": 1}]
            + [{"id": f"impact-{d}", "generate": "impact", "at_bar": d, "bars": 2} for d in (17, 66, 82)]}
    res = resolve(plan)
    assert res.ok, [i.message for i in res.issues if i.level == "error"]
    edit = plan_short_edit(plan, res, target_s=150)
    assert edit["start_bar"] == 5 and edit["end_bar"] == 109  # 4 bars of run-up; 4 faded bars after the chant
    assert edit["cuts"] == [(65.5, 81.5)]  # drop 66's repeated hook goes; the chant's pickup into 82 stays
    assert edit["duration_s"] < edit["full_s"] and abs(edit["duration_s"] - (109 - 5 - 16) * 1.6) < 0.01


def test_short_edit_never_cuts_the_last_copy_of_a_hook(workspace):
    from glass_harbor.edit import plan_short_edit
    from glass_harbor.plan import resolve
    from conftest import write_fake_track

    write_fake_track("vox", bpm=75, key="Am", bars=48)
    write_fake_track("beat", bpm=150, key="Am", bars=160, stems=("instrumental",))

    def vox(clip_id, frm, bars, at):
        return {"id": clip_id, "source": "vox", "stem": "vocals", "from_bar": frm, "bars": bars, "at_bar": at}

    plan = {"version": 1, "kind": "mashup", "bpm": 150, "sources": {"vox": {"track": "vox", "tempo_ratio": 2.0},
                                                                    "bed": {"track": "beat"}},
            "clips": [{"id": "bed", "source": "bed", "stem": "instrumental", "from_bar": 1, "bars": 150, "at_bar": 1},
                      vox("verse1", 1, 8, 9),
                      vox("hookA", 20, 8, 33), vox("hookB", 20, 8, 49),  # the only two copies of this hook
                      vox("longer", 30, 8, 65), vox("shorter", 30, 4, 81),  # same start, the first one longer
                      vox("verse2", 40, 8, 97)]
            + [{"id": f"impact-{d}", "generate": "impact", "at_bar": d, "bars": 2} for d in (9, 33, 49, 65, 81, 97)]}
    res = resolve(plan)
    assert res.ok, [i.message for i in res.issues if i.level == "error"]
    edit = plan_short_edit(plan, res, target_s=60)

    def cut(bar):
        return any(a <= bar < b for a, b in edit["cuts"])

    assert edit["cuts"] and not (cut(33) and cut(49))  # one copy of the hook stays
    assert not cut(65)  # "longer" carries material "shorter" does not


def test_grid_warning_trusts_drums_not_sustained_bass(tmp_path):
    rng = np.random.default_rng(5)
    A.save(tmp_path / "mix.wav", (0.1 * rng.standard_normal((8 * A.SR, 2))).astype(np.float32))
    (tmp_path / "plan.json").write_text(json.dumps({"bpm": 130, "beats_per_bar": 4, "clips": []}))
    clips = [{"id": f"loop-{stem}", "track": "beat", "stem": stem, "start_s": 0.0, "length_s": 8.0,
              "stretch_pct": 0.0, "semitones": 0, "source_grid_offset_ms": -62.0} for stem in ("bass", "drums")]
    (tmp_path / "render.json").write_text(json.dumps({"files": {"wav": "mix.wav"}, "clips": clips}))
    grid = [f["where"] for f in check_run(tmp_path)["flags"] if "source beat grid" in f["message"]]
    assert grid == ["loop-drums"]  # an off-beat bassline's decaying notes say nothing about the grid


def test_warp_warning_needs_enough_onsets_on_a_vocal(tmp_path):
    rng = np.random.default_rng(6)
    A.save(tmp_path / "mix.wav", (0.1 * rng.standard_normal((8 * A.SR, 2))).astype(np.float32))
    (tmp_path / "plan.json").write_text(json.dumps({"bpm": 93, "beats_per_bar": 4, "clips": []}))
    clips = [{"id": name, "track": "vox", "stem": stem, "start_s": 0.0, "length_s": 8.0, "stretch_pct": -2.1,
              "semitones": 2, "warp_offset_ms": 48.0, "notes": {"warp_coverage": coverage}}
             for name, stem, coverage in (("sparse-verse", "vocals", 0.346), ("crisp-verse", "vocals", 0.5),
                                          ("sparse-drums", "drums", 0.25))]
    (tmp_path / "render.json").write_text(json.dumps({"files": {"wav": "mix.wav"}, "clips": clips}))
    warned = [f["where"] for f in check_run(tmp_path)["flags"] if "off the output grid" in f["message"]]
    assert warned == ["crisp-verse", "sparse-drums"]  # a few soft syllables say little about the warp


def test_vocal_balance_reads_loudness_only_where_the_vocal_sounds(workspace):
    from glass_harbor.render import _balance_lu, record_balance
    from conftest import write_fake_track

    rng = np.random.default_rng(1)
    rest = (0.05 * rng.standard_normal((12 * A.SR, 2))).astype(np.float32)
    vocal = np.zeros_like(rest)
    vocal[: 6 * A.SR] = 0.1 * rng.standard_normal((6 * A.SR, 2))  # sounds for half the time, 6 dB over the rest
    lu, seconds = _balance_lu(vocal, rest)
    assert lu == pytest.approx(6.0, abs=0.3) and seconds == pytest.approx(6.0, abs=0.2)  # the gaps do not count
    assert _balance_lu(vocal[: 2 * A.SR], rest) is None  # too little vocal to judge
    write_fake_track("song", bpm=120, key="Am", bars=8, stems=("vocals", "instrumental"))
    A.save(library.stem_path("song", "vocals"), vocal)
    A.save(library.stem_path("song", "instrumental"), rest)
    assert record_balance("song") == pytest.approx(6.0, abs=0.3)


def test_range_renders_measure_vocal_balance_only_inside_the_range():
    from types import SimpleNamespace

    from glass_harbor.render import vocal_balance

    rng = np.random.default_rng(4)
    beat = (0.05 * rng.standard_normal((20 * A.SR, 2))).astype(np.float32)
    rap = np.zeros_like(beat)
    rap[: 8 * A.SR] = 0.1 * rng.standard_normal((8 * A.SR, 2))  # the vocal only sounds in the first 8 s

    def clip(cid, stem, audio):
        return SimpleNamespace(clip=SimpleNamespace(id=cid, stem=stem, chop=None, track=cid), start_sample=0,
                               audio=audio)

    rendered = [clip("bed", "instrumental", beat), clip("rap", "vocals", rap)]
    assert [b["track"] for b in vocal_balance(rendered, beat.shape[0])] == ["rap"]
    assert vocal_balance(rendered, beat.shape[0], keep=(10 * A.SR, 20 * A.SR)) == []  # not in the preview


def test_qa_flags_a_vocal_far_louder_than_on_its_own_record(tmp_path):
    rng = np.random.default_rng(2)
    A.save(tmp_path / "mix.wav", (0.1 * rng.standard_normal((8 * A.SR, 2))).astype(np.float32))
    (tmp_path / "plan.json").write_text(json.dumps({"bpm": 120, "beats_per_bar": 4, "clips": []}))
    balance = [{"track": "rap", "clips": ["verse"], "mix_lu": 6.2, "record_lu": -3.9, "active_s": 90.0},
               {"track": "singer", "clips": ["hook"], "mix_lu": -2.8, "record_lu": -4.6, "active_s": 40.0}]
    (tmp_path / "render.json").write_text(json.dumps({"files": {"wav": "mix.wav"}, "clips": [],
                                                      "vocal_balance": balance}))
    flags = [f for f in check_run(tmp_path)["flags"] if "own record" in f["message"]]
    assert [f["where"] for f in flags] == ["rap"]  # 10.1 LU over its record; the singer's 1.8 LU is fine
