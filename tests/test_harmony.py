import numpy as np

from glass_harbor import audio as A
from glass_harbor.harmony import clash_by_bar, harmonize

SR = A.SR


def _tone(freq, seconds, amp=0.2):
    t = np.arange(int(seconds * SR)) / SR
    sig = amp * (np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(4 * np.pi * freq * t))
    return np.repeat(sig[:, None], 2, axis=1).astype(np.float32)


def _peak_hz(x):
    spec = np.abs(np.fft.rfft(A.mono(x) * np.hanning(x.shape[0])))
    freqs = np.fft.rfftfreq(x.shape[0], 1 / SR)
    band = (freqs > 200) & (freqs < 400)
    return freqs[band][np.argmax(spec[band])]


def test_clashing_held_note_moves_to_the_chord():
    chord = _tone(261.63, 3.0) + _tone(329.63, 3.0) + _tone(392.0, 3.0)  # C major
    sung = _tone(277.18, 3.0, 0.3)  # C#: a semitone above the root
    fixed, fixes = harmonize(sung, chord)
    assert fixes and fixes[0]["from"] % 12 == 1 and fixes[0]["to"] % 12 == 0
    assert abs(_peak_hz(fixed[SR // 2: -SR // 2]) - 261.63) < 4


def test_on_chord_note_and_unpitched_audio_are_left_alone():
    chord = _tone(261.63, 3.0) + _tone(329.63, 3.0) + _tone(392.0, 3.0)
    sung = _tone(329.63, 3.0, 0.3)  # E: a chord tone
    fixed, fixes = harmonize(sung, chord)
    assert fixes == [] and fixed is sung
    noise = (np.random.default_rng(0).standard_normal((3 * SR, 2)) * 0.05).astype(np.float32)
    assert harmonize(noise, chord)[1] == []


def test_clash_by_bar_scores_rubs():
    chord = _tone(261.63, 4.0) + _tone(329.63, 4.0) + _tone(392.0, 4.0)
    sung = np.concatenate([_tone(329.63, 2.0, 0.3), _tone(277.18, 2.0, 0.3)])
    spans = [(1, (0, 2 * SR)), (2, (2 * SR, 4 * SR))]
    scores = {item["bar"]: item["clash"] for item in clash_by_bar(sung, chord, spans)}
    assert scores[1] < 0.2 < scores[2]
