import json

import numpy as np
import pytest
from conftest import write_fake_track

from glass_harbor import audio as A
from glass_harbor import library
from glass_harbor.lyrics import lyrics_path
from glass_harbor.plan import resolve
from glass_harbor.scaffold import arrange_bed_stems, build_mashup
from glass_harbor.spectral import pump_curve, spectral_duck
from glass_harbor.vocals import apply_chain

SR = A.SR


def _sine(freq, seconds, amp, phase_r=0.0):
    t = np.arange(int(seconds * SR)) / SR
    left = amp * np.sin(2 * np.pi * freq * t)
    right = amp * np.sin(2 * np.pi * freq * t + phase_r)
    return np.stack([left, right], axis=1).astype(np.float32)


def _band_db(x, lo, hi):
    spec = np.abs(np.fft.rfft(A.mono(x)))
    f = np.fft.rfftfreq(x.shape[0], 1 / SR)
    return 20 * np.log10(np.sqrt(np.mean(spec[(f >= lo) & (f < hi)] ** 2)) + 1e-12)


def test_spectral_duck_cuts_only_where_the_vocal_competes():
    bed = _sine(1000, 3.0, 0.3) + _sine(60, 3.0, 0.3) + _sine(5000, 3.0, 0.1, phase_r=np.pi)  # 5k mostly side
    vocal = _sine(1000, 3.0, 0.3)
    out = spectral_duck(bed, vocal, max_db=6.0, level_db=0.0)
    mid = slice(SR // 2, int(2.5 * SR))
    assert _band_db(out[mid], 900, 1100) - _band_db(bed[mid], 900, 1100) < -4.0  # competing band ducked
    assert abs(_band_db(out[mid], 50, 70) - _band_db(bed[mid], 50, 70)) < 0.5  # low end untouched
    side = lambda x: np.repeat(((x[:, 0] - x[:, 1]) / 2)[:, None], 2, axis=1)  # noqa: E731
    assert abs(_band_db(side(out[mid]), 4900, 5100) - _band_db(side(bed[mid]), 4900, 5100)) < 0.5  # side untouched
    silent = spectral_duck(bed, np.zeros_like(bed), max_db=6.0, level_db=0.0)
    assert np.allclose(silent[mid], bed[mid], atol=2e-3)


def test_pump_curve_dips_on_the_beat_and_recovers():
    beats = np.linspace(0, 4, 4001)
    gain = pump_curve(beats, db=6.0, release=0.5)
    on = gain[(beats % 1 > 0.025) & (beats % 1 < 0.05)]
    late = gain[(beats % 1 > 0.6)]
    assert 20 * np.log10(on.min()) < -4.5 and np.allclose(late, 1.0)
    assert gain[0] == pytest.approx(1.0)  # no instant drop at the exact beat (short attack)


def test_chain_split_returns_dry_and_wet():
    voice = np.pad(_sine(300, 1.0, 0.2), ((0, SR), (0, 0)))
    dry, wet = apply_chain(voice, "hook", beat_seconds=0.5, split=True)
    assert np.sqrt(np.mean(wet[int(1.2 * SR):] ** 2)) > 1e-4 and np.max(np.abs(dry[int(1.2 * SR):])) < 1e-3


def _mashup_plan():
    return {"version": 1, "kind": "mashup", "bpm": 124, "sources": {"vox": {"track": "vox"}, "bed": {"track": "bed"}},
            "clips": [{"id": "bed", "source": "bed", "stem": "instrumental", "from_bar": 1, "bars": 40, "at_bar": 1,
                       "duck": {"under": "vocals", "db": 5}},
                      {"id": "verse", "source": "vox", "stem": "vocals", "from_bar": 1, "bars": 8, "at_bar": 9},
                      {"id": "hook", "source": "vox", "stem": "vocals", "from_bar": 9, "bars": 8, "at_bar": 17,
                       "chain": "hook"}]}


def test_arrange_bed_stems(workspace):
    write_fake_track("vox", bpm=124, key="Am", bars=24)
    write_fake_track("bed", bpm=124, key="Am", bars=48, stems=("instrumental", "drums", "bass", "other"))
    plan = arrange_bed_stems(_mashup_plan(), pump={"db": 3, "release": 0.5})
    ids = [c["id"] for c in plan["clips"]]
    assert ids[:3] == ["bed-drums", "bed-bass", "bed-other"]
    other = next(c for c in plan["clips"] if c["id"] == "bed-other")
    bass = next(c for c in plan["clips"] if c["id"] == "bed-bass")
    assert other["duck"]["db"] == 5 and other["pump"]["db"] == 3
    # Verse at bars 9-16 strips the melodic layer; bar 16 (before the hook) is drums only; the hook is full.
    points = other["automation"]["arrange_db"]
    assert [8.0, -60.0] in points and points[-1] == [16.0, 0.0]
    assert [15.0, -60.0] in bass["automation"]["arrange_db"]
    res = resolve(plan)
    assert res.ok, [i.to_dict() for i in res.issues]
    assert not any("two basslines" in i.message for i in res.issues)


def test_arrange_requires_stems(workspace):
    write_fake_track("vox", bpm=124, key="Am", bars=24)
    write_fake_track("bed", bpm=124, key="Am", bars=48, stems=("instrumental",))
    with pytest.raises(ValueError, match="drums"):
        arrange_bed_stems(_mashup_plan())


def test_mashup_scaffold_defaults(workspace):
    write_fake_track("vox", bpm=124, key="Am", bars=40)
    write_fake_track("bed", bpm=126, key="Am", bars=64, stems=("instrumental", "drums", "bass", "other"))
    analysis = library.load_analysis("vox")
    analysis["stems"]["vocals"]["phrases"] = [{"start_bar": 1, "bars": 8}, {"start_bar": 9, "bars": 8}]
    analysis["hooks"] = [{"count": 2, "words": 4, "occurrences": [{"start_bar": 9.1, "end_bar": 12}]}]
    library.save_analysis("vox", analysis)
    plan = build_mashup("vox", "bed")
    assert plan["master"]["reference"] == "bed"
    assert plan["groove"]["pump_fx"]["db"] == 5.0
    chains = {c["from_bar"]: c.get("chain") for c in plan["clips"] if c.get("stem") == "vocals"}
    assert chains[9] == "hook" and chains[1] is None
    assert any(c["id"].endswith("-other") for c in plan["clips"])
    assert resolve(plan).ok


def test_vocal_on_a_drop_gets_the_full_beat(workspace):
    write_fake_track("vox", bpm=124, key="Am", bars=24)
    write_fake_track("bed", bpm=124, key="Am", bars=48, stems=("instrumental", "drums", "bass", "other"))
    plan = _mashup_plan()
    plan["clips"].append({"id": "impact", "generate": "impact", "at_bar": 9, "bars": 2})
    plan = arrange_bed_stems(plan)
    other = next(c for c in plan["clips"] if c["id"] == "bed-other")
    assert "arrange_db" not in other.get("automation", {}) or all(
        v == 0 or not (8 <= x < 16) for x, v in other["automation"]["arrange_db"])
