"""Prepare locally downloaded Goldbaby free archives; never redistribute their samples.

Requires the optional analysis requirements (numpy, scipy, soundfile). Reads just
the root/tuning fields in the included EXS presets, not a general EXS importer.
"""
from pathlib import Path
from fractions import Fraction
from io import BytesIO
import argparse
import hashlib
import json
import struct
import zipfile

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "private-packs/vendor-sources/goldbaby"
NOTES = {
    "bass_pitched": "f1 g1 a1 c2 d2 e2 g2".split(),
    "stab_pitched": "c3 f3 g3 a3 b3 c4 d4 e4 g4 a4".split(),
    "pluck_pitched": "c4 d4 e4 f4 g4 a4 b4 c5 d5 e5 g5".split(),
}


def midi(note):
    return (int(note[-1]) + 1) * 12 + {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}[note[0]]


def preset_zones(archive, preset):
    matches = [name for name in archive.namelist() if name.endswith("/" + preset + ".exs") and not name.startswith("__MACOSX/")]
    if len(matches) != 1:
        raise ValueError(f"Expected one {preset} preset")
    data = archive.read(matches[0])
    zones, offset = [], 0
    while offset + 84 <= len(data):
        kind, length = struct.unpack_from("<II", data, offset)
        end = offset + 84 + length
        if end > len(data):
            raise ValueError("Truncated EXS block")
        if kind == 0x01000101:
            if length < 96:
                raise ValueError("Truncated EXS zone")
            body = data[offset + 84:end]
            label = data[offset + 20:offset + 84].split(b"\0")[0].decode().split(" ")[0]
            key, fine = struct.unpack_from("<Bb", body, 1)
            coarse = struct.unpack_from("<b", body, 80)[0]
            zones.append({"stem": label, "key": key, "fine": fine, "coarse": coarse})
        offset = end
    if not zones:
        raise ValueError("No pitch zones in preset")
    return zones


def read_audio(archive, filename):
    matches = [name for name in archive.namelist() if name.endswith("/" + filename) and not name.startswith("__MACOSX/")]
    if len(matches) != 1:
        raise ValueError(f"Expected one audio source: {filename}")
    audio, rate = sf.read(BytesIO(archive.read(matches[0])), always_2d=True)
    if not np.isfinite(audio).all() or not np.any(audio):
        raise ValueError(f"Invalid audio: {filename}")
    return audio, rate


def sustain_pad(audio, rate, seconds=5.2):
    """Extend a stable interior region, with overlaps rather than a hard loop seam."""
    end = int(rate * 1.9)
    segment = audio[int(rate * 0.9):end]
    overlap = int(rate * 0.08)
    result = audio[:end].copy()
    fade = np.linspace(0, 1, overlap)[:, None]
    while len(result) < rate * seconds:
        blend = result[-overlap:] * (1 - fade) + segment[:overlap] * fade
        result = np.concatenate([result[:-overlap], blend, segment[overlap:]])
    return result[:int(rate * seconds)]


def write_audio(path, audio, rate, peak, fade_in, fade_out, duration=None):
    audio = resample_poly(audio, 44100, rate, axis=0) if rate != 44100 else audio.copy()
    rate = 44100
    if duration:
        audio = audio[:int(rate * duration)]
    # Attenuate to a ceiling; do not boost quiet hits or flatten natural dynamics.
    audio *= min(1, peak / float(np.abs(audio).max()))
    attack = min(len(audio), max(2, int(rate * fade_in)))
    release = min(len(audio), max(2, int(rate * fade_out)))
    audio[:attack] *= np.linspace(0, 1, attack)[:, None]
    audio[-release:] *= np.linspace(1, 0, release)[:, None]
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, audio, rate, subtype="PCM_24")
    return {"seconds": len(audio) / rate, "peak": float(np.abs(audio).max()), "channels": audio.shape[1]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archives", type=Path, default=BASE / "archives")
    args = parser.parse_args()
    for name in ["PPG_Wave2_Free.zip", "GB_Hapi_vs_Xylophone.zip", "MPC60vsMDvsRytm.zip"]:
        if not zipfile.is_zipfile(args.archives / name):
            raise ValueError(f"Missing or invalid local archive: {name}")
    output = BASE / "prepared"
    families, evidence = {}, []
    archive_specs = [
        ("bass_pitched", "PPG_Wave2_Free.zip", "PPGw2_NiceA", 0.72),
        ("stab_pitched", "PPG_Wave2_Free.zip", "PPG_Simple3", 0.66),
        ("pluck_pitched", "GB_Hapi_vs_Xylophone.zip", "GB_Hapi_vs_Xylophone", 0.62),
    ]
    for family, filename, preset, peak in archive_specs:
        with zipfile.ZipFile(args.archives / filename) as archive:
            zones = preset_zones(archive, preset)
            families[family] = {}
            for note in NOTES[family]:
                key = midi(note)
                zone = min(zones, key=lambda candidate: abs(candidate["key"] - key))
                semitones = key - zone["key"] + zone["coarse"] + zone["fine"] / 100
                audio, rate = read_audio(archive, zone["stem"] + ".wav")
                ratio = Fraction(2 ** (-semitones / 12)).limit_denominator(2048)
                audio = resample_poly(audio, ratio.numerator, ratio.denominator, axis=0)
                if family == "stab_pitched":
                    audio = sustain_pad(audio, rate)
                elif family == "bass_pitched":
                    audio = audio.mean(axis=1, keepdims=True)
                relative = f"{family}/{note}.wav"
                stats = write_audio(output / relative, audio, rate, peak,
                                    0.08 if family == "stab_pitched" else 0.002,
                                    0.4 if family == "stab_pitched" else 0.08,
                                    None if family == "stab_pitched" else 1.8 if family == "pluck_pitched" else 1.2)
                families[family][note] = [relative]
                evidence.append({"family": family, "note": note, "source": zone["stem"],
                                 "source_root_midi": zone["key"], "fine_cents": zone["fine"],
                                 "transpose_semitones": semitones, **stats})
    drum_sources = {
        "kick_main": (["BD_RytmMPC60_003a", "BD_RytmMPC60_005a"], 0.85),
        "clap_main": (["Clap_RytmMPC60_3st", "Clap_RytmMPC60_2st"], 0.7),
        "hat_closed": (["HH_RytmMPC60_1", "HH_RytmMPC60_3", "HH_RytmMPC60_5", "HH_RytmMPC60_8"], 0.55),
        "hat_open": (["HHo_RytmMPC60_1", "HHo_RytmMPC60_3"], 0.5),
        "perc_top": (["Conga_MD_MPC60_1", "Rim_RytmMPC60_1"], 0.5),
    }
    with zipfile.ZipFile(args.archives / "MPC60vsMDvsRytm.zip") as archive:
        for family, (stems, peak) in drum_sources.items():
            families[family] = []
            for index, stem in enumerate(stems):
                audio, rate = read_audio(archive, stem + ".wav")
                relative = f"{family}/{index}.wav"
                stats = write_audio(output / relative, audio, rate, peak, 0.0003, 0.006)
                families[family].append(relative)
                evidence.append({"family": family, "source": stem, **stats})
    BASE.mkdir(parents=True, exist_ok=True)
    (BASE / "import-map.json").write_text(json.dumps({"families": families}, indent=2) + "\n")
    report = {"source": "https://www.goldbaby.co.nz/freestuff.html",
              "license": "https://www.goldbaby.co.nz/termsandconditio.html",
              "private_only": True,
              "archives": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(args.archives.glob("*.zip"))},
              "assets": evidence}
    (BASE / "prep-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Prepared {len(evidence)} private samples; original stereo retained for pad, hook and clap.")


if __name__ == "__main__":
    main()
