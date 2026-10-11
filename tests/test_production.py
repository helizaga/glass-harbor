import numpy as np
import pytest
from conftest import synth_track, write_fake_track

from glass_harbor import audio as A
from glass_harbor import drums, vocals
from glass_harbor.keys import parse_key

SR = A.SR


def _db(x):
    return 20 * np.log10(np.sqrt(np.mean(np.asarray(x) ** 2)) + 1e-12)


def _voice(seconds, freq=220.0, amp=0.3):
    t = np.arange(int(seconds * SR)) / SR
    sig = amp * (np.sin(2 * np.pi * freq * t) + 0.4 * np.sin(4 * np.pi * freq * t))
    return np.repeat(sig[:, None], 2, axis=1).astype(np.float32)


def test_gate_turns_down_bleed_between_words_but_keeps_words_and_loud_adlibs():
    rng = np.random.default_rng(0)
    audio = (rng.standard_normal((4 * SR, 2)) * 0.02).astype(np.float32)  # hat/808 bleed everywhere
    audio[int(0.5 * SR):int(1.0 * SR)] += _voice(0.5)  # transcribed word
    audio[int(2.5 * SR):int(2.9 * SR)] += _voice(0.4)  # loud ad-lib Whisper missed
    gated, closed = vocals.gate_between_words(audio, [(0.5, 1.0)], depth_db=14)
    word, adlib, gap = slice(int(0.6 * SR), int(0.9 * SR)), slice(int(2.6 * SR), int(2.8 * SR)), slice(int(1.6 * SR), int(2.2 * SR))
    assert abs(_db(gated[word]) - _db(audio[word])) < 0.5
    assert abs(_db(gated[adlib]) - _db(audio[adlib])) < 0.5
    assert _db(gated[gap]) - _db(audio[gap]) == pytest.approx(-14, abs=1)
    assert 0.4 < closed < 0.9


def test_groove_keyframes_pull_late_onsets_toward_the_16th_grid():
    src = np.array([0.0, 0.5, 1.0])
    out = np.array([0.0, 0.6, 1.2])  # stretched 20%
    late = 0.125 + 0.02  # a 16th, 20 ms late in the source
    triplet = 0.5 + 0.5 / 3  # a triplet: leave it alone
    s, o, shifts = vocals.groove_keyframes(src, out, [late, triplet], 0.5)
    assert len(shifts) == 1 and list(s) == sorted(s) and list(o) == sorted(o)
    natural = 0.6 * (late / 0.5)
    assert o[1] == pytest.approx(natural - 0.5 * 0.02 * 1.2, abs=1e-6)  # half the way back, in output time


def test_density_keeps_the_level_but_lifts_presence():
    rng = np.random.default_rng(1)
    t = np.arange(2 * SR) / SR
    env = 0.5 + 0.5 * np.sin(2 * np.pi * 3 * t) ** 2
    vox = (_voice(2.0) * env[:, None] + rng.standard_normal((2 * SR, 2)) * 0.003).astype(np.float32)
    plain = vocals.apply_chain(vox, "rap", beat_seconds=0.5, density=0.0)
    dense = vocals.apply_chain(vox, "rap", beat_seconds=0.5, density=1.0)
    assert abs(vocals._active_rms_db(plain) - vocals._active_rms_db(dense)) < 0.5
    from glass_harbor.render import _band

    assert _db(_band(dense, 2000, 6000)) > _db(_band(plain, 2000, 6000)) + 1


def test_halftime_plays_the_records_own_kit_on_half_time_steps():
    from glass_harbor.grid import build_grid

    stems = synth_track(120, parse_key("Am"), 8)
    kit = stems["drums"]
    beats = np.arange(0, 16, 0.5)
    grid = build_grid(beats, beats[::4], kit.shape[0] / SR)
    kick, hat = drums.find_kick(kit, grid), drums.find_hat(kit, grid)
    assert kick is not None and hat is not None
    assert abs((kick.start / 0.5) - round(kick.start / 0.5)) < 0.02  # on a beat
    assert abs((hat.start / 0.25) % 2 - 1) < 0.05  # on an off-beat 8th
    click = np.zeros((2000, 2), dtype=np.float32)
    click[:50] = 1.0
    out = drums.sequence({"kick": click}, {"kick": "x.........x....."}, 4.0, 0.5)  # two bars
    hits = np.flatnonzero(np.abs(out[:, 0]) > 0.5)
    starts = sorted({int(round(h / SR / 0.125)) for h in hits})
    assert starts == [0, 10, 16, 26]  # steps 0 and 10 of each bar


def test_drum_clipping_lowers_peaks_and_loud_beds_get_louder_masters(workspace, synth_files, tmp_path):
    from glass_harbor import library
    from glass_harbor.analyze import analyze_track
    from glass_harbor.render import render_plan

    paths = synth_files("loud", 120, "Am", bars=8, seed=2)
    library.add_track(paths["mix"], track_id="loud", stems={"drums": paths["drums"]})
    library.save_analysis("loud", analyze_track(library.load_audio("loud"), beat_backend="librosa"))
    analysis = library.load_analysis("loud")
    library.save_analysis("loud", {**analysis, "loudness_lufs": -4.7})
    base = {"version": 1, "kind": "mashup", "bpm": 120, "sources": {"d": {"track": "loud"}},
            "master": {"reference": "loud"}, "clips": [{"id": "drums", "source": "d", "stem": "drums",
                                                        "from_bar": 1, "bars": 4, "at_bar": 1}]}
    plain = render_plan(base, tmp_path / "plain", mp3=False, write_clips=True, log=lambda m: None, use_cache=False)
    base["clips"][0]["clip_db"] = 4
    clipped = render_plan(base, tmp_path / "clipped", mp3=False, write_clips=True, log=lambda m: None,
                          use_cache=False)
    peak = lambda run: np.max(np.abs(A.load(tmp_path / run / "clips" / "01-drums.wav")))
    assert 20 * np.log10(peak("plain") / peak("clipped")) > 2.5
    assert clipped["master"]["target_lufs"] == pytest.approx(-6.0)


def test_instrumental_pass_keeps_the_beats_own_vocal(workspace, monkeypatch, tmp_path):
    from glass_harbor import library, separate

    write_fake_track("beat", bpm=120, key="Am", bars=8, stems=())
    fake = {name: A.save(tmp_path / f"{name}.flac", np.full((SR, 2), 0.1 if name == "vocals" else 0.2, np.float32))
            for name in ("vocals", "instrumental")}
    monkeypatch.setattr(separate, "_run_audio_separator", lambda *a, **k: fake)
    produced = separate.separate_track("beat", stems=["instrumental"], quality="balanced", log=lambda m: None)
    assert {"instrumental", "vocals"} <= set(produced)
    assert library.stem_path("beat", "vocals").exists()


def test_render_writes_a_phone_version(workspace, synth_files, tmp_path):
    import shutil
    import subprocess

    from glass_harbor import library
    from glass_harbor.analyze import analyze_track
    from glass_harbor.render import render_plan

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    paths = synth_files("p", 120, "Am", bars=8, seed=4)
    library.add_track(paths["mix"], track_id="p")
    library.save_analysis("p", analyze_track(library.load_audio("p"), beat_backend="librosa"))
    plan = {"version": 1, "title": "Phone Test", "kind": "mashup", "bpm": 120, "sources": {"a": {"track": "p"}},
            "master": {"lufs": -6.5}, "clips": [{"id": "a", "source": "a", "from_bar": 1, "bars": 4, "at_bar": 1}]}
    report = render_plan(plan, tmp_path / "run", log=lambda m: None, use_cache=False)
    assert report["files"]["phone"] == "mix-phone.m4a"
    assert report["phone_master"]["output_lufs"] < report["master"]["output_lufs"]  # -8, not the -6.5 club master
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name:format_tags=title",
                            "-of", "default=nw=1", str(tmp_path / "run" / "mix-phone.m4a")],
                           capture_output=True, text=True, check=True).stdout
    assert "codec_name=aac" in probe and "Phone Test" in probe
    assert not (tmp_path / "run" / "mix-phone.wav").exists()
