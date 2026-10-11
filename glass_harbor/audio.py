"""Audio I/O and level helpers. All internal audio is float32, shape (frames, channels), 44.1 kHz stereo."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44100
CHANNELS = 2
REFERENCE_LUFS = -14.0  # level every source is matched to before plan gains apply


def _to_stereo(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        audio = audio[:, None]
    if audio.shape[1] == 1:
        return np.repeat(audio, 2, axis=1)
    if audio.shape[1] > 2:
        return audio[:, :2]
    return audio


def _resample(audio: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return audio
    import soxr

    return soxr.resample(audio, sr_in, sr_out, quality="HQ").astype(np.float32)


def _decode_ffmpeg(path: Path) -> np.ndarray:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError(f"ffmpeg is required to decode {path.suffix} files; install it (brew install ffmpeg).")
    result = subprocess.run(
        [ffmpeg, "-v", "error", "-nostdin", "-i", str(path), "-f", "f32le", "-acodec", "pcm_f32le",
         "-ac", str(CHANNELS), "-ar", str(SR), "-"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed to decode {path}: {result.stderr.decode(errors='replace').strip()}")
    return np.frombuffer(result.stdout, dtype=np.float32).reshape(-1, CHANNELS).copy()


def load(path: str | Path) -> np.ndarray:
    """Decode any audio file to float32 stereo at SR."""
    path = Path(path)
    try:
        data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    except sf.LibsndfileError:
        return _decode_ffmpeg(path)
    return np.ascontiguousarray(_resample(_to_stereo(data), sr, SR), dtype=np.float32)


def save(path: str | Path, audio: np.ndarray, subtype: str | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if subtype is None:
        subtype = "PCM_24"
    sf.write(str(path), audio, SR, subtype=subtype)
    return path


def encode_mp3(wav_path: Path, mp3_path: Path, bitrate: str = "320k") -> Path | None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    subprocess.run(
        [ffmpeg, "-v", "error", "-nostdin", "-y", "-i", str(wav_path), "-codec:a", "libmp3lame", "-b:a", bitrate,
         str(mp3_path)],
        check=True,
    )
    return mp3_path


def _aac_encoder(ffmpeg: str) -> str:
    """Apple's AudioToolbox AAC on macOS (the encoder iPhones use), else ffmpeg's built-in one."""
    listing = subprocess.run([ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True, check=False).stdout
    return "aac_at" if " aac_at " in listing else "aac"


def encode_m4a(wav_path: Path, m4a_path: Path, *, bitrate: str = "256k", title: str = "") -> Path | None:
    """AAC in an MP4 container: plays natively on iPhone and Android and is smaller than a 320k MP3."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    cmd = [ffmpeg, "-v", "error", "-nostdin", "-y", "-i", str(wav_path), "-codec:a", _aac_encoder(ffmpeg),
           "-b:a", bitrate, "-movflags", "+faststart"]
    if title:
        cmd += ["-metadata", f"title={title}"]
    subprocess.run([*cmd, str(m4a_path)], check=True)
    return m4a_path


def mono(audio: np.ndarray) -> np.ndarray:
    return audio.mean(axis=1) if audio.ndim == 2 else audio


def db_to_gain(db: float) -> float:
    return float(10.0 ** (db / 20.0))


def gain_to_db(gain: float, floor: float = -120.0) -> float:
    return float(max(floor, 20.0 * np.log10(max(gain, 1e-12))))


def integrated_lufs(audio: np.ndarray) -> float:
    import pyloudnorm

    if audio.shape[0] < SR // 2:
        return float("-inf")
    value = pyloudnorm.Meter(SR).integrated_loudness(audio.astype(np.float64))
    return float(value)


def true_peak_db(audio: np.ndarray) -> float:
    """Approximate true peak via 4x oversampling (ITU-R BS.1770 style)."""
    from scipy.signal import resample_poly

    if audio.size == 0:
        return float("-inf")
    oversampled = resample_poly(audio, 4, 1, axis=0)
    return gain_to_db(float(np.max(np.abs(oversampled))))


def sample_peak_db(audio: np.ndarray) -> float:
    return gain_to_db(float(np.max(np.abs(audio)))) if audio.size else float("-inf")
