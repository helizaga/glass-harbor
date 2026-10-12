import numpy as np
import pytest

from glass_harbor.grid import build_grid, shift_downbeat
from glass_harbor.keys import (Key, _KK_MINOR, camelot_distance, estimate_key_from_chroma, harmonic_relation,
                               parse_key)
from glass_harbor.tempo import TempoMap, validate_tempo


@pytest.mark.parametrize("text,camelot", [
    ("C major", "8B"), ("A minor", "8A"), ("Am", "8A"), ("G", "9B"), ("F# major", "2B"), ("Bb", "6B"),
    ("Ebm", "2A"), ("C#m", "12A"), ("8A", "8A"), ("11B", "11B"),
])
def test_parse_and_camelot(text, camelot):
    assert parse_key(text).camelot == camelot


def test_camelot_round_trip_for_every_key():
    for tonic in range(12):
        for mode in ("major", "minor"):
            key = Key(tonic, mode)
            assert parse_key(key.camelot) == key
            assert parse_key(key.name) == key


def test_camelot_distance_and_relation():
    assert camelot_distance(parse_key("Am"), parse_key("C")) == 1
    assert harmonic_relation(parse_key("Am"), parse_key("C")) == "relative major/minor"
    assert camelot_distance(parse_key("8A"), parse_key("9A")) == 1
    assert camelot_distance(parse_key("12A"), parse_key("1A")) == 1
    assert harmonic_relation(parse_key("8A"), parse_key("3A")) == "clash"


def test_key_estimate_recovers_profile_key():
    chroma = np.roll(_KK_MINOR, 4)  # E minor
    key, confidence, _ = estimate_key_from_chroma(chroma / chroma.sum())
    assert key == Key(4, "minor")
    assert confidence > 0


def test_fixed_grid_from_jittery_beats():
    rng = np.random.default_rng(1)
    period = 60 / 124
    beats = 0.37 + period * np.arange(200) + rng.normal(0, 0.004, 200)
    downbeats = beats[2::4]  # downbeat lands on the third detected beat
    grid = build_grid(beats, downbeats, duration=beats[-1] + 0.3)
    assert grid.mode == "fixed"
    assert grid.bpm == pytest.approx(124, abs=0.05)
    bar1 = grid.bar_time(1)
    assert min(abs(bar1 - d) for d in downbeats) < 0.01
    assert grid.bar_time(2) - bar1 == pytest.approx(4 * period, abs=0.002)
    assert grid.bar_at_time(grid.bar_time(9)) == pytest.approx(9)


def test_variable_grid_follows_drift():
    times = np.cumsum(np.linspace(0.5, 0.44, 160))  # accelerating performance
    grid = build_grid(times, times[::4], duration=times[-1] + 0.5)
    assert grid.mode == "variable"
    assert grid.beat_time(grid.first_downbeat + 40) == pytest.approx(times[40], abs=1e-6)


def test_shift_downbeat_moves_bar_one():
    period = 0.5
    beats = period * np.arange(64)
    grid = build_grid(beats, beats[::4], duration=32.2)
    shifted = shift_downbeat(grid, 1)
    assert shifted.bar_time(1) - grid.bar_time(1) == pytest.approx(period)


def test_tempo_map_steps_and_ramps():
    constant = TempoMap.from_plan({"bpm": 120}, 4)
    assert constant.time_at(8) == pytest.approx(4.0)
    stepped = TempoMap.from_plan({"tempo": [{"bar": 1, "bpm": 90}, {"bar": 3, "bpm": 140}]}, 4)
    assert stepped.time_at(8) == pytest.approx(8 * 60 / 90)
    assert stepped.time_at(12) == pytest.approx(8 * 60 / 90 + 4 * 60 / 140)
    ramp = TempoMap.from_plan({"tempo": [{"bar": 1, "bpm": 120}, {"bar": 3, "bpm": 130, "ramp": True}]}, 4)
    assert 8 * 60 / 130 < ramp.time_at(8) < 8 * 60 / 120
    assert ramp.bpm_at(4) == pytest.approx(125)
    samples = [ramp.time_at(b) for b in np.linspace(0, 16, 65)]
    assert all(b > a for a, b in zip(samples, samples[1:]))


def test_validate_tempo_messages():
    assert validate_tempo({"bpm": 120}) == []
    assert validate_tempo({}) != []
    assert validate_tempo({"bpm": 120, "tempo": []}) != []
    assert validate_tempo({"tempo": [{"bar": 2, "bpm": 120}]}) == ["tempo[0].bar must be 1"]
    assert validate_tempo({"tempo": [{"bar": 1, "bpm": 120}, {"bar": 1, "bpm": 125}]}) != []


def test_frame_quantized_beats_stay_fixed():
    # beat_this reports on a 20 ms grid: a steady 110 bpm comes out as alternating 0.54/0.56 s intervals.
    true = 0.2 + (60 / 110) * np.arange(280)
    quantized = np.round(true / 0.02) * 0.02
    grid = build_grid(quantized, quantized[::4], duration=true[-1] + 0.5)
    assert grid.mode == "fixed"
    assert grid.bpm == pytest.approx(110, abs=0.02)


def test_metrical_level_flip_is_normalized():
    period = 60 / 126
    fast = np.arange(400) * period
    # Tracker reports the middle of the song at half tempo (every other beat).
    beats = np.concatenate([fast[:60], fast[60:320:2], fast[320:]])
    grid = build_grid(beats, beats[::4], duration=fast[-1] + 0.3)
    assert grid.mode == "fixed"
    assert grid.bpm == pytest.approx(126, abs=0.05)
    assert any("metrical level" in note for note in grid.notes)


def test_tracker_drift_in_a_breakdown_keeps_a_fixed_grid():
    period = 60 / 175
    grid_beats = np.arange(0, 120, period)
    # Through a breakdown the tracker emits 49 beats across 50 real ones (each 2% late), then locks back on:
    # one beat goes missing without any single interval looking wrong.
    drifted = grid_beats[200] + np.arange(49) * period * 50 / 49
    beats = np.concatenate([grid_beats[:200], drifted, grid_beats[250:]])
    grid = build_grid(beats, beats[::4], 120.0)
    assert grid.mode == "fixed" and abs(grid.bpm - 175) < 0.05
    assert any("fixed tempo" in note for note in grid.notes)
    assert np.abs(np.asarray(grid.beats) - grid_beats[300]).min() < 0.005  # back on the real beats after it


def test_real_tempo_change_stays_variable():
    first = np.arange(0, 60, 60 / 120)
    second = first[-1] + np.cumsum(np.full(120, 60 / 132))
    grid = build_grid(np.concatenate([first, second]), np.concatenate([first, second])[::4], 120.0)
    assert grid.mode == "variable"


def test_beat_a_hair_before_zero_stays_bar_one():
    period = 60 / 175
    beats = -0.006 + period * np.arange(1, 400)  # tracker misses the very first beat, fit lands 6 ms before 0 s
    grid = build_grid(beats, beats[3::4], 140.0)
    assert grid.beats[0] == 0.0 and grid.bar_time(1) == pytest.approx(0.0, abs=1e-9)


def test_raw_beats_locked_to_half_time_still_find_the_fixed_pulse():
    from glass_harbor.grid import hinted_fit

    period = 0.4  # 150 bpm
    intro = list(np.arange(0.15, 0.15 + 32 * period, period))
    # Through the drop the tracker reports every other beat, some of them pulled 90 ms late by a syncopated 808.
    drop = [intro[-1] + 2 * period * (i + 1) + (0.09 if i % 5 == 0 else 0.0) for i in range(40)]
    t0, found, share = hinted_fit(intro + drop)
    assert abs(found - period) < 0.0005 and share > 0.7


def test_parallel_keys_beat_a_big_vocal_shift():
    from glass_harbor.compat import key_score

    same_home_note = key_score(3, 0.6, 0, 0.7, parallel=True)  # E major vocal over E minor beat, unshifted
    shifted_up_three = key_score(0, 0.6, 3, 0.7)  # G major over E minor: relative, but a +3 vocal shift
    assert same_home_note > shifted_up_three


def test_drum_hits_confirm_a_fixed_grid_when_the_tracker_pulse_is_garbage():
    from conftest import synth_track

    from glass_harbor.analyze import confirm_fixed_tempo

    drums = synth_track(150, parse_key("E"), 24)["drums"]
    garbage = np.arange(0.0, 38.0, 0.36)  # a steady but wrong 166.7 bpm pulse, as through Stay With Me's drops
    assert confirm_fixed_tempo(drums, garbage) is None
    t0, period = confirm_fixed_tempo(drums, garbage, period_hint=0.4)
    assert abs(period - 0.4) < 0.0005 and min(t0 % period, period - t0 % period) < 0.015  # kicks on the beat
