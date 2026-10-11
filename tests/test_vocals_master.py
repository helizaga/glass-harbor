import numpy as np
import pytest

from glass_harbor import audio as A
from glass_harbor import vocals
from glass_harbor.check import low_end_correlation, tonal_balance
from glass_harbor.render import low_band_clip, master, mono_bass, reference_match, soft_clipper

SR = A.SR


def _tone(seconds, freq=220.0, amp=0.3):
    t = np.arange(int(seconds * SR)) / SR
    return np.repeat((amp * np.sin(2 * np.pi * freq * t))[:, None], 2, axis=1).astype(np.float32)


def test_word_safe_edges_never_cut_a_word():
    words = [{"word": "call", "start": 0.90, "end": 1.20}, {"word": "phone", "start": 3.80, "end": 4.40}]
    beat = 0.5
    # Start lands inside "call" shortly after it began -> pull it in; end lands in "phone" early -> stop before.
    edges = vocals.word_safe_edges(1.0, 4.0, words, beat)
    assert edges.start == pytest.approx(0.88) and "before 'call'" in edges.start_note
    assert edges.end == pytest.approx(3.78) and "before 'phone'" in edges.end_note
    assert edges.words_cut == 0
    # End lands near the end of a word -> cut after it.
    edges = vocals.word_safe_edges(1.5, 4.2, words, beat)
    assert edges.end == pytest.approx(4.43) and edges.words_cut == 0
    # Touching words (continuous rap): the cut lands on a junction, never inside a word.
    rap = [{"word": f"w{i}", "start": 1.0 + 0.25 * i, "end": 1.25 + 0.25 * i} for i in range(12)]
    edges = vocals.word_safe_edges(1.6, 3.1, rap, beat)
    assert edges.words_cut == 0


def test_word_safe_edges_energy_fallback_moves_to_quiet_point():
    loud = _tone(2.0)
    quiet = np.zeros((int(0.1 * SR), 2), dtype=np.float32)
    signal = np.concatenate([loud, quiet, loud])  # gap at 2.0-2.1 s
    edges = vocals.word_safe_edges(0.0, 2.15, None, 0.5, vocal=signal)
    assert 1.99 <= edges.end <= 2.11


def test_ride_evens_phrase_levels():
    phrase_a = _tone(2.0, amp=0.4)
    phrase_b = _tone(2.0, amp=0.1)  # 12 dB quieter
    ridden, most = vocals.ride(np.concatenate([phrase_a, phrase_b]))
    a = np.sqrt(np.mean(ridden[int(0.5 * SR):int(1.5 * SR)] ** 2))
    b = np.sqrt(np.mean(ridden[int(2.5 * SR):int(3.5 * SR)] ** 2))
    assert abs(20 * np.log10(a / b)) < 7.0 and most > 3  # a 12 dB gap closes to about 6 dB (boost capped at +4)


def test_chain_keeps_level_and_adds_tails():
    rng = np.random.default_rng(0)
    voice = (_tone(2.0, 300, 0.2) + 0.02 * rng.standard_normal((2 * SR, 2))).astype(np.float32)
    padded = np.pad(voice, ((0, SR), (0, 0)))
    out = vocals.apply_chain(padded, "hook", beat_seconds=0.5, throw_regions=[(1.6, 2.0)])
    before, after = vocals._active_rms_db(voice), vocals._active_rms_db(out[: 2 * SR])
    assert abs(before - after) < 1.5
    assert np.sqrt(np.mean(out[int(2.2 * SR):] ** 2)) > 1e-3  # reverb + delay throw ring after the words
    assert np.allclose(vocals.apply_chain(padded, "none", beat_seconds=0.5), padded)


def test_mono_bass_and_soft_clip():
    t = np.arange(SR) / SR
    low = np.stack([np.sin(2 * np.pi * 50 * t), -np.sin(2 * np.pi * 50 * t)], axis=1).astype(np.float32)
    assert low_end_correlation(low) < -0.9
    side_in = np.sqrt(np.mean(((low[:, 0] - low[:, 1]) / 2) ** 2))
    out = mono_bass(low)[SR // 4: -SR // 4]  # steady state (filter edges excluded)
    side_out = np.sqrt(np.mean(((out[:, 0] - out[:, 1]) / 2) ** 2))
    assert 20 * np.log10(side_out / side_in) < -30
    loud = np.clip(_tone(1.0, amp=2.0), -5, 5)
    assert np.max(np.abs(soft_clipper(loud, -1.0))) <= A.db_to_gain(-1.0) + 1e-6


def test_master_with_soft_clip_hits_target():
    rng = np.random.default_rng(1)
    x = (0.1 * rng.standard_normal((10 * SR, 2))).astype(np.float32)
    x[::SR // 2] = 0.9  # spiky transients
    out, stats = master(x, lufs=-10, ceiling_db=-1)
    assert stats["output_lufs"] == pytest.approx(-10, abs=0.6)
    assert stats["true_peak_db"] <= -0.9


def test_reference_match_moves_tone_toward_reference():
    pytest.importorskip("matchering")
    rng = np.random.default_rng(2)
    noise = rng.standard_normal((20 * SR, 2)).astype(np.float32) * 0.1
    from scipy.signal import butter, sosfiltfilt

    dark = sosfiltfilt(butter(2, 1500, "lowpass", fs=SR, output="sos"), noise, axis=0).astype(np.float32)
    bright = sosfiltfilt(butter(2, 1500, "highpass", fs=SR, output="sos"), noise, axis=0).astype(np.float32)
    matched = reference_match(dark, bright + 0.3 * dark)
    ref = tonal_balance(bright + 0.3 * dark)
    gap_before = abs(tonal_balance(dark)["presence"] - ref["presence"])
    gap_after = abs(tonal_balance(matched)["presence"] - ref["presence"])
    assert gap_after < gap_before - 3


def _band_db(x, lo, hi):
    from scipy.signal import welch

    f, p = welch(x.mean(axis=1), SR, nperseg=8192)
    return 10 * np.log10(p[(f >= lo) & (f < hi)].sum())


def test_low_band_clip_leaves_the_mids_clean():
    # 808-style sub sine plus a 1 kHz "vocal": the sub sets the peaks, the vocal must stay clean.
    x = _tone(4.0, freq=35.0, amp=0.8) + _tone(4.0, freq=1000.0, amp=0.15)
    clipped = low_band_clip(x, clip_db=3.0)
    assert np.abs(clipped).max() < np.abs(x).max()
    assert abs(_band_db(clipped, 900, 1100) - _band_db(x, 900, 1100)) < 0.2
    _, low = master(x, lufs=-8, ceiling_db=-1, soft_clip="low")
    _, full = master(x, lufs=-8, ceiling_db=-1, soft_clip="full")
    assert low["clip"] == "low" and full["clip"] == "full"
    assert low["clip_products_db"] < full["clip_products_db"] - 10
    _, off = master(x, lufs=-8, ceiling_db=-1, soft_clip=False)
    assert off["clip"] == "off" and "clip_products_db" not in off


def test_auto_clip_falls_back_to_full_only_when_the_target_is_out_of_reach():
    x = _tone(4.0, freq=35.0, amp=0.8) + _tone(4.0, freq=1000.0, amp=0.15)
    _, moderate = master(x, lufs=-14, ceiling_db=-1)
    assert moderate["clip"] == "low" and "clip_fallback" not in moderate
    _, club = master(x, lufs=-5, ceiling_db=-1)
    low_only, _ = master(x, lufs=-5, ceiling_db=-1, soft_clip="low")
    assert A.integrated_lufs(low_only) < -6.0  # low-band clipping alone cannot get there...
    assert club["clip"] == "full" and "clip_fallback" in club  # ...so auto clips the full mix
