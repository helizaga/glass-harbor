import json
from pathlib import Path

import numpy as np
import pytest

from glass_harbor import audio as A
from glass_harbor.keys import Key

SR = A.SR


@pytest.fixture(autouse=True)
def offline_popularity(monkeypatch):
    """Tests never reach Deezer; a test that wants popularity data stubs ``potential._get`` itself."""
    from glass_harbor import potential

    def offline(*args, **kwargs):
        raise OSError("no network in tests")

    monkeypatch.setattr(potential, "_get", offline)


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("GLASS_HARBOR_HOME", str(tmp_path))
    return tmp_path


def _tone(freq: float, seconds: float, amp: float) -> np.ndarray:
    t = np.arange(int(seconds * SR)) / SR
    env = np.minimum(1.0, t / 0.01) * np.exp(-t * 1.5)
    return amp * env * (np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(4 * np.pi * freq * t))


def _kick(amp: float) -> np.ndarray:
    t = np.arange(int(0.18 * SR)) / SR
    freq = 50 + 90 * np.exp(-t * 35)
    return amp * np.exp(-t * 18) * np.sin(2 * np.pi * np.cumsum(freq) / SR)


def _hat(amp: float, rng: np.random.Generator) -> np.ndarray:
    n = int(0.04 * SR)
    return amp * rng.standard_normal(n) * np.exp(-np.arange(n) / SR * 120)


def synth_track(bpm: float, key: Key, bars: int, *, lead_in: float = 0.0, seed: int = 0,
                with_vocal: bool = False) -> dict[str, np.ndarray]:
    """Drums on the grid plus i-VI-III-VII (minor) or I-V-vi-IV (major) chords; returns stems and mix."""
    rng = np.random.default_rng(seed)
    beat = 60.0 / bpm
    total = int((lead_in + bars * 4 * beat + 1.0) * SR)
    drums = np.zeros(total)
    harmony = np.zeros(total)
    vocal = np.zeros(total)
    degrees = [[0, 3, 7], [8, 12, 15], [3, 7, 10], [10, 14, 17]] if key.mode == "minor" else \
        [[0, 4, 7], [7, 11, 14], [9, 12, 16], [5, 9, 12]]
    root = 220.0 * 2 ** ((key.tonic - 9) / 12)
    for bar in range(bars):
        chord = degrees[bar % 4]
        start = int((lead_in + bar * 4 * beat) * SR)
        for semis in chord:
            tone = _tone(root * 2 ** (semis / 12), 4 * beat, 0.08)
            harmony[start: start + tone.size] += tone[: total - start]
        bass = _tone(root / 2 * 2 ** (chord[0] / 12), 4 * beat, 0.15)
        harmony[start: start + bass.size] += bass[: total - start]
        for b in range(4):
            pos = int((lead_in + (bar * 4 + b) * beat) * SR)
            kick = _kick(0.9 if b == 0 else 0.6)
            drums[pos: pos + kick.size] += kick[: total - pos]
            off = int((lead_in + (bar * 4 + b + 0.5) * beat) * SR)
            hat = _hat(0.15, rng)
            drums[off: off + hat.size] += hat[: total - off]
            if with_vocal and bar % 2 == 0:
                note = _tone(root * 2 * 2 ** (chord[b % 3] / 12), beat * 0.9, 0.12)
                vocal[pos: pos + note.size] += note[: total - pos]
    stems = {"drums": drums, "instrumental": drums + harmony}
    if with_vocal:
        stems["vocals"] = vocal
    stems["mix"] = stems["instrumental"] + vocal
    return {name: np.repeat(sig[:, None], 2, axis=1).astype(np.float32) for name, sig in stems.items()}


@pytest.fixture()
def synth_files(tmp_path):
    def make(name: str, bpm: float, key: str, bars: int = 24, **kwargs) -> dict[str, Path]:
        from glass_harbor.keys import parse_key

        stems = synth_track(bpm, parse_key(key), bars, **kwargs)
        folder = tmp_path / "sources"
        paths = {}
        for stem, audio in stems.items():
            paths[stem] = A.save(folder / f"{name}-{stem}.wav", audio, subtype="FLOAT")
        return paths

    return make


def write_fake_track(track_id: str, *, bpm: float, key: str, bars: int, stems=("vocals",)) -> None:
    """Library entry with analysis but tiny placeholder audio, for plan-only tests."""
    from glass_harbor import library
    from glass_harbor.grid import build_grid
    from glass_harbor.keys import parse_key

    period = 60.0 / bpm
    duration = bars * 4 * period + 0.5
    beats = np.arange(0, duration, period)
    grid = build_grid(beats, beats[::4], duration)
    key_obj = parse_key(key)
    folder = library.track_dir(track_id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "track.json").write_text(json.dumps({"id": track_id, "title": track_id, "stems": {}}))
    silence = np.zeros((SR, 2), dtype=np.float32)
    A.save(library.audio_path(track_id), silence)
    stem_info = {}
    for stem in stems:
        A.save(library.stem_path(track_id, stem), silence)
        stem_info[stem] = {"bar_db": [-10.0] * grid.bar_count, "chroma": [1.0 / 12] * 12,
                           **({"phrases": [{"start_bar": 1, "bars": grid.bar_count}]} if stem == "vocals" else {})}
    analysis = {
        "version": 1, "duration": duration, "bpm": bpm, "beat_backend": "test",
        "key": {**key_obj.to_dict(), "confidence": 0.8, "source": "test"},
        "loudness_lufs": -14.0, "chroma": [1.0 / 12] * 12, "grid": grid.to_dict(),
        "bar_db": [-12.0] * grid.bar_count,
        "sections": [{"start_bar": 1, "bars": grid.bar_count, "label": "A", "energy": "mid", "mean_db": -12.0}],
        "stems": stem_info,
    }
    library.save_analysis(track_id, analysis)
