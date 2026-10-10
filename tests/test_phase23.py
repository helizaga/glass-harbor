import json

import numpy as np
import pytest

from glass_harbor import audio as A
from glass_harbor import library
from glass_harbor.analyze import analyze_track
from glass_harbor.grid import build_grid
from glass_harbor.lyrics import find_word, hooks, lyrics_path, phrases_from_lyrics
from glass_harbor.plan import resolve
from glass_harbor.render import _band, render_plan


def _fake_lyrics():
    seg = lambda s, e, text: {"start": s, "end": e, "text": text,  # noqa: E731
                              "words": [{"word": w, "start": s + i * 0.2, "end": s + i * 0.2 + 0.18, "prob": 0.9}
                                        for i, w in enumerate(text.split())]}
    return {"segments": [seg(2.0, 3.5, "call my phone baby"), seg(4.0, 5.6, "hey janice shut up"),
                         seg(10.0, 11.5, "call my phone baby"), seg(20.0, 21.0, "for real")]}


def test_lyrics_phrases_hooks_and_words():
    beats = np.arange(0, 40, 0.5)
    grid = build_grid(beats, beats[::4], duration=40)
    lyrics = _fake_lyrics()
    phrases = phrases_from_lyrics(lyrics, grid)
    # bars are 2 s long here: lines at 2.0-5.6 s merge into one phrase covering bars 2-3
    assert phrases == [{"start_bar": 2, "bars": 2}, {"start_bar": 6, "bars": 1}, {"start_bar": 11, "bars": 1}]
    found = hooks(lyrics, grid)
    assert found[0]["text"] == "call my phone baby" and found[0]["count"] == 2
    assert find_word(lyrics, "Janice")["start"] == pytest.approx(4.2)
    with pytest.raises(ValueError):
        find_word(lyrics, "janice", occurrence=2)


def _add(synth_files, name, bpm, key, **kwargs):
    paths = synth_files(name, bpm, key, **kwargs)
    stems = {k: v for k, v in paths.items() if k in ("vocals", "instrumental")}
    library.add_track(paths["mix"], track_id=name, stems=stems)
    library.save_analysis(name, analyze_track(library.load_audio(name), beat_backend="librosa",
                                              stems={s: library.load_audio(name, s) for s in stems}))


def test_word_chops_resolve(workspace, synth_files):
    _add(synth_files, "vox", 120, "Am", bars=8, with_vocal=True, seed=2)
    lyrics_path("vox").write_text(json.dumps(_fake_lyrics()))
    plan = {"version": 1, "kind": "mashup", "bpm": 120, "sources": {"vox": {"track": "vox"}},
            "clips": [{"id": "c", "source": "vox", "stem": "vocals", "at_bar": 1, "bars": 1,
                       "chop": {"slices": {"j": {"word": "janice", "semitones": 3}}, "pattern": "j---j---j---j---"}}]}
    res = resolve(plan)
    assert res.ok, [i.to_dict() for i in res.issues]
    piece = res.clips[0].chop["slices"]["j"]
    assert piece["start"] == pytest.approx(4.19) and piece["semitones"] == 3


def test_ducking_dips_bed_mids_and_presence_is_reported(workspace, synth_files, tmp_path):
    _add(synth_files, "vox", 120, "Am", bars=8, with_vocal=True, seed=3)
    _add(synth_files, "bed", 120, "Am", bars=8, seed=4)
    base = {"version": 1, "kind": "mashup", "bpm": 120, "master": {"glue": False},
            "sources": {"vox": {"track": "vox"}, "bed": {"track": "bed"}}}
    clips = [{"id": "bed", "source": "bed", "stem": "instrumental", "from_bar": 1, "bars": 8, "at_bar": 1},
             {"id": "v", "source": "vox", "stem": "vocals", "from_bar": 1, "bars": 4, "at_bar": 3}]
    dry = render_plan({**base, "clips": clips}, tmp_path / "dry", mp3=False, write_clips=True, log=lambda m: None)
    clips[0]["duck"] = {"under": "vocals", "db": 9}
    ducked = render_plan({**base, "clips": clips}, tmp_path / "ducked", mp3=False, write_clips=True,
                         log=lambda m: None)
    assert ducked["vocal_presence"] and dry["vocal_presence"]
    a = A.load(tmp_path / "dry" / "clips" / "01-bed.wav")
    b = A.load(tmp_path / "ducked" / "clips" / "01-bed.wav")
    window = slice(int(4.3 * A.SR), int(5.8 * A.SR))  # synthetic vocal sings in output bar 3 (4-6 s)
    dip = 20 * np.log10(np.sqrt(np.mean(_band(b[window]) ** 2)) / np.sqrt(np.mean(_band(a[window]) ** 2)))
    assert dip < -3
    early = slice(int(0.5 * A.SR), int(3.0 * A.SR))  # before the vocal: untouched
    assert np.allclose(a[early], b[early], atol=1e-4)
    by_bar = {p["bar"]: p["db"] for p in ducked["vocal_presence"]}
    by_bar_dry = {p["bar"]: p["db"] for p in dry["vocal_presence"]}
    assert by_bar[4] > by_bar_dry[4]


def test_duck_validation(workspace, synth_files):
    _add(synth_files, "bed", 120, "Am", bars=8, seed=5)
    plan = {"version": 1, "kind": "mashup", "bpm": 120, "sources": {"bed": {"track": "bed"}},
            "clips": [{"source": "bed", "from_bar": 1, "bars": 4, "at_bar": 1, "duck": {"under": 3, "db": 40}}]}
    assert not resolve(plan).ok
