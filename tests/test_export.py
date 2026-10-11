import json

import numpy as np
import pytest
from conftest import write_fake_track

from glass_harbor import audio as A
from glass_harbor import library
from glass_harbor.analyze import analyze_track
from glass_harbor.export import export_daw, order_tracks, render_video, tempo_midi
from glass_harbor.render import render_plan


def test_order_prefers_harmonic_tempo_path(workspace):
    write_fake_track("a", bpm=124, key="8A", bars=32)
    write_fake_track("b", bpm=125, key="9A", bars=32)
    write_fake_track("c", bpm=126, key="10A", bars=32)
    write_fake_track("z", bpm=90, key="3B", bars=32)
    order, cost = order_tracks(["c", "z", "a", "b"], start="a")
    assert order[:3] == ["a", "b", "c"] and order[-1] == "z"


def test_tempo_midi_has_steps():
    data = tempo_midi({"beats_per_bar": 4, "tempo": [{"bar": 1, "bpm": 92}, {"bar": 9, "bpm": 128}]})
    assert data.startswith(b"MThd") and data.count(b"\xff\x51\x03") == 2
    ramp = tempo_midi({"beats_per_bar": 4, "tempo": [{"bar": 1, "bpm": 120}, {"bar": 3, "bpm": 128, "ramp": True}]})
    assert ramp.count(b"\xff\x51\x03") >= 8


@pytest.fixture()
def run(workspace, synth_files, tmp_path):
    paths = synth_files("a", 120, "Am", bars=8, seed=1)
    library.add_track(paths["mix"], track_id="a")
    library.save_analysis("a", analyze_track(library.load_audio("a"), beat_backend="librosa", key_backend="template"))
    plan = {"version": 1, "title": "Export test", "kind": "set", "bpm": 120, "sources": {"a": {"track": "a"}},
            "clips": [{"id": "one", "source": "a", "from_bar": 2, "bars": 4, "at_bar": 1, "pre_beats": 2}]}
    out = tmp_path / "run"
    render_plan(plan, out, mp3=False, write_clips=True, log=lambda m: None)
    return out


def test_daw_export_pads_pickups_to_a_bar_line(run):
    out = export_daw(run)
    wav = A.load(next(out.glob("*.wav")))
    report = json.loads((run / "render.json").read_text())
    assert report["timeline_offset_s"] == pytest.approx(1.0, abs=0.01)  # 2 pickup beats at 120 bpm
    original = A.load(next((run / "clips").glob("*.wav")))
    assert wav.shape[0] - original.shape[0] == pytest.approx(1.0 * A.SR, abs=2)  # padded to a full bar (2 s)
    assert (out / "tempo.mid").exists() and "bar(s) before bar 1" in (out / "README.txt").read_text()


def test_video_render(run):
    path = render_video(run, vertical=False)
    assert path.exists() and path.stat().st_size > 10_000
