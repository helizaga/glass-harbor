import numpy as np
import pytest
from conftest import write_fake_track

from glass_harbor import audio as A
from glass_harbor import bassline, library

SR = A.SR


def _hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def _bass(notes, seconds_each, *, plucks_per_s=4.0):
    """Plucked bass (fundamental + 2nd harmonic) playing ``notes`` (MIDI) back to back."""
    parts = []
    for note in notes:
        t = np.arange(int(seconds_each * SR)) / SR
        pluck = np.exp(-(t % (1 / plucks_per_s)) * 9)
        tone = np.sin(2 * np.pi * _hz(note) * t) + 0.4 * np.sin(4 * np.pi * _hz(note) * t)
        parts.append(0.4 * pluck * tone)
    sig = np.concatenate(parts)
    return np.repeat(sig[:, None], 2, axis=1).astype(np.float32)


def _voice(midi, seconds, beat=0.5):
    t = np.arange(int(seconds * SR)) / SR
    gate = ((t % beat) < 0.8 * beat).astype(float)
    sig = 0.2 * gate * (np.sin(2 * np.pi * _hz(midi) * t) + 0.3 * np.sin(4 * np.pi * _hz(midi) * t))
    return np.repeat(sig[:, None], 2, axis=1).astype(np.float32)


def test_roots_reads_the_bass_note_per_window():
    bass = _bass([28, 33], 1.0)  # E1 then A1
    assert bassline.roots(bass, [(0.1, 0.9), (1.1, 1.9)]) == [28, 33]


def test_clash_rate_counts_flat_ninths_and_tritones():
    rate, frames = bassline.clash_rate([[4, 4], [9], []], [27, 27, 27])  # E and A over D#
    assert frames == 3 and rate == pytest.approx(1.0)
    assert bassline.clash_rate([[1, 4, 8]], [25])[0] == 0.0  # C#, E, G# over C#: a chord


def test_follow_replaces_notes_but_keeps_rhythm_and_level():
    bass = _bass([27], 4.0)  # D#1 for 4 s
    span = bassline.Span([(int(s * SR), int((s + 0.25) * SR)) for s in np.arange(1.0, 3.0, 0.25)], [25] * 8)
    out = bassline.follow(bass, [span])
    assert bassline.roots(out, [(1.2, 2.8), (3.2, 3.9)]) == [25, 27]  # C#1 inside, D#1 untouched outside
    inside = slice(int(1.1 * SR), int(2.9 * SR))
    level = 20 * np.log10(np.sqrt(np.mean(out[inside] ** 2)) / np.sqrt(np.mean(bass[inside] ** 2)))
    assert abs(level) < 1.5
    env = lambda x: np.abs(A.mono(x[inside])).reshape(-1, 441).max(axis=1)
    assert np.corrcoef(env(out), env(bass))[0, 1] > 0.8  # same plucks


def _follow_library(workspace):
    write_fake_track("vox", bpm=120, key="C#m", bars=4, stems=("vocals", "bass"))
    write_fake_track("bed", bpm=120, key="C#m", bars=4, stems=("bass",))
    A.save(library.stem_path("vox", "vocals"), _voice(52, 8.5))  # sings E3 ...
    A.save(library.stem_path("vox", "bass"), _bass([25], 8.5))  # ... over a C# bass (a minor third: fine)
    A.save(library.stem_path("bed", "bass"), _bass([27], 8.5))  # the new beat holds D#: E is a flat ninth
    return {"version": 1, "title": "follow", "kind": "mashup", "bpm": 120,
            "sources": {"vox": {"track": "vox"}, "bed": {"track": "bed"}},
            "clips": [{"id": "bed-bass", "source": "bed", "stem": "bass", "from_bar": 1, "bars": 4, "at_bar": 1},
                      {"id": "sung", "source": "vox", "stem": "vocals", "from_bar": 1, "bars": 4, "at_bar": 1,
                       "word_safe": False}]}


def test_scaffold_follows_a_clashing_vocal_and_render_fixes_it(workspace, tmp_path):
    from glass_harbor.render import render_plan
    from glass_harbor.scaffold import follow_vocal_roots

    plan = _follow_library(workspace)
    before = render_plan(plan, tmp_path / "before", mp3=False, log=lambda m: None, use_cache=False)
    assert before["bass_clash"][0]["pct"] > 50
    plan, findings = follow_vocal_roots(plan)
    assert findings[0]["follow"] and findings[0]["over_bed_bass_pct"] > 50 and findings[0]["over_own_bass_pct"] < 5
    assert plan["clips"][0]["follow_roots"] == ["sung"]
    after = render_plan(plan, tmp_path / "after", mp3=False, log=lambda m: None, use_cache=False)
    assert after["bass_clash"][0]["pct"] < 5
    assert "sung" in next(c for c in after["clips"] if c["id"] == "bed-bass")["notes"]["followed_roots"]


def test_follow_roots_only_on_bass_clips(workspace):
    from glass_harbor.plan import resolve

    plan = _follow_library(workspace)
    plan["clips"][1]["follow_roots"] = True
    assert any("only works on a bass stem" in i.message for i in resolve(plan).issues)
    plan["clips"][1].pop("follow_roots")
    plan["clips"][0]["follow_roots"] = ["nope"]
    assert any("unknown vocal clips" in i.message for i in resolve(plan).issues)


def test_overlapping_spans_are_level_matched_on_their_own_windows():
    bass = _bass([27], 4.0)
    bass[int(2 * SR):] *= 0.25  # quieter second half
    first = bassline.Span([(int(s * SR), int((s + 0.25) * SR)) for s in np.arange(0.0, 2.0, 0.25)], [25] * 8)
    second = bassline.Span([(int(s * SR), int((s + 0.25) * SR)) for s in np.arange(1.5, 4.0, 0.25)], [25] * 10)
    out = bassline.follow(bass, [first, second])
    for a, b in ((0.1, 1.4), (2.1, 3.9)):
        part = slice(int(a * SR), int(b * SR))
        level = 20 * np.log10(np.sqrt(np.mean(out[part] ** 2)) / np.sqrt(np.mean(bass[part] ** 2)))
        assert abs(level) < 2.0  # neither half picks up the other span's gain
