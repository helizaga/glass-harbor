import numpy as np
import pytest
from conftest import synth_track, write_fake_track

from glass_harbor import audio as A
from glass_harbor import fx, key_model
from glass_harbor.analyze import detect_drops
from glass_harbor.keys import parse_key
from glass_harbor.plan import resolve
from glass_harbor.render import render_plan
from glass_harbor.scaffold import add_drop


def test_generators_have_exact_length_and_shape():
    for kind in fx.TYPES:
        out = fx.generate(kind, 1.5)
        assert out.shape == (int(round(1.5 * A.SR)), 2)
        assert np.max(np.abs(out)) <= 1.0
    rise = A.mono(fx.riser(4.0))
    first, last = rise[: A.SR], rise[-A.SR:]
    assert np.sqrt(np.mean(last ** 2)) > 4 * np.sqrt(np.mean(first ** 2))  # it actually rises


def test_detect_drops():
    low = [-30] * 8 + [-12] * 8 + [-28] * 8 + [-11] * 8
    assert detect_drops(low) == [9, 25]
    assert detect_drops([-12] * 32) == []


def test_drop_macro_adds_build_silence_and_fx(workspace):
    write_fake_track("bed", bpm=124, key="Am", bars=48, stems=("instrumental",))
    plan = {"version": 1, "kind": "mashup", "bpm": 124, "sources": {"bed": {"track": "bed"}},
            "clips": [{"id": "bed", "source": "bed", "stem": "instrumental", "from_bar": 1, "bars": 40, "at_bar": 1,
                       "automation": {"gain_db": [[32, 0], [40, -40]]}}]}
    add_drop(plan, 25, build_bars=8)
    res = resolve(plan)
    assert res.ok, [i.to_dict() for i in res.issues]
    auto = plan["clips"][0]["automation"]
    assert auto["highpass_hz"][0] == [16, 20] and auto["highpass_hz"][-1] == [24, 20]
    assert [32, 0] in auto["gain_db"] and any(p[1] == -60 for p in auto["gain_db"])
    ids = {c["id"] for c in plan["clips"]}
    assert {"riser-25", "impact-25"} <= ids
    with pytest.raises(ValueError):
        add_drop(plan, 4, build_bars=8)


def test_generated_clips_render(workspace, synth_files, tmp_path):
    from glass_harbor import library
    from glass_harbor.analyze import analyze_track

    paths = synth_files("bed", 120, "Am", bars=16, seed=9)
    library.add_track(paths["mix"], track_id="bed")
    library.save_analysis("bed", analyze_track(library.load_audio("bed"), beat_backend="librosa", key_backend="template"))
    plan = {"version": 1, "kind": "mashup", "bpm": 120, "master": {"glue": False},
            "sources": {"bed": {"track": "bed"}},
            "clips": [{"id": "bed", "source": "bed", "from_bar": 1, "bars": 16, "at_bar": 1}]}
    add_drop(plan, 9, build_bars=4)
    report = render_plan(plan, tmp_path / "drop", mp3=False, write_clips=True, log=lambda m: None)
    ids = [c["id"] for c in report["clips"]]
    assert "riser-9" in ids and "impact-9" in ids
    bed = A.mono(A.load(tmp_path / "drop" / "clips" / "01-bed.wav"))
    beat = int(0.5 * A.SR)
    silence = bed[31 * beat + 200: 32 * beat - 200]  # the last beat before bar 9 (bar 9 = beat 32)
    assert np.sqrt(np.mean(silence ** 2)) < 0.01


@pytest.mark.skipif(not key_model.available(), reason="S-KEY needs torch + nnAudio")
def test_skey_finds_synthetic_key_or_relative():
    key, prob, top = key_model.estimate_key(synth_track(120, parse_key("E"), 16)["mix"])
    assert key.camelot in ("12B", "12A") and prob > 0.3 and len(top) == 3
