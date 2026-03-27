#!/usr/bin/env python3

import argparse
import json
import math
import os
import struct
import wave


RICH_IMPORT_ERROR = None

try:
    import numpy as np
    import librosa
    import soundfile as sf
    from scipy.signal import find_peaks

    HAVE_RICH_STACK = True
except Exception as error:  # pragma: no cover - fallback path is intentional
    np = None
    librosa = None
    sf = None
    find_peaks = None
    HAVE_RICH_STACK = False
    RICH_IMPORT_ERROR = str(error)


def clamp(value, minimum=0.0, maximum=1.0):
    return max(minimum, min(maximum, float(value)))


def read_wav_stdlib(path):
    with wave.open(path, "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frames = wav_file.getnframes()
        raw = wav_file.readframes(frames)

    if sample_width not in (1, 2, 4):
        raise ValueError(f"Unsupported sample width: {sample_width}")

    if sample_width == 1:
        fmt = "b"
        scale = 128.0
    elif sample_width == 2:
        fmt = "h"
        scale = 32768.0
    else:
        fmt = "i"
        scale = 2147483648.0

    samples = struct.unpack("<" + fmt * (len(raw) // sample_width), raw)
    mono = []
    for index in range(0, len(samples), channels):
        frame = samples[index:index + channels]
        mono.append(sum(frame) / len(frame) / scale)

    return mono, sample_rate, channels


def read_audio(path):
    if not HAVE_RICH_STACK:
        samples, sample_rate, channels = read_wav_stdlib(path)
        return samples, sample_rate, channels

    audio, sample_rate = sf.read(path, always_2d=True)
    channels = audio.shape[1]
    mono = np.mean(audio, axis=1).astype(np.float32)
    return mono, int(sample_rate), channels


def compute_legacy_metrics(samples, sample_rate):
    if not samples:
        return {
            "duration_seconds": 0,
            "sample_rate": sample_rate,
            "channels": 1,
            "rms": 0,
            "peak": 0,
            "crest_factor": 0,
            "dynamic_range_db": 0,
            "zero_crossing_rate": 0,
            "brightness_proxy": 0,
            "low_end_ratio": 0,
            "onset_density": 0,
        }

    count = len(samples)
    duration_seconds = count / sample_rate
    energy = sum(sample * sample for sample in samples)
    rms = math.sqrt(energy / count)
    peak = max(abs(sample) for sample in samples)
    crest_factor = peak / rms if rms else 0
    dynamic_range_db = 20 * math.log10((peak + 1e-9) / (rms + 1e-9))

    zero_crossings = 0
    for index in range(1, count):
        if (samples[index - 1] <= 0 < samples[index]) or (samples[index - 1] >= 0 > samples[index]):
            zero_crossings += 1
    zero_crossing_rate = zero_crossings / duration_seconds if duration_seconds else 0

    abs_mean = sum(abs(sample) for sample in samples) / count
    brightness_proxy = (
        sum(abs(samples[index] - samples[index - 1]) for index in range(1, count)) / max(1, count - 1)
    ) / (abs_mean + 1e-9)

    low_alpha = min(1.0, (2 * math.pi * 180) / sample_rate)
    low = 0.0
    low_energy = 0.0
    high_energy = 0.0
    for sample in samples:
        low = low + low_alpha * (sample - low)
        high = sample - low
        low_energy += low * low
        high_energy += high * high
    low_end_ratio = low_energy / (low_energy + high_energy + 1e-9)

    window_size = max(256, sample_rate // 40)
    hop_size = max(128, window_size // 2)
    window_rms = []
    for start in range(0, count - window_size, hop_size):
        window = samples[start:start + window_size]
        window_energy = sum(sample * sample for sample in window)
        window_rms.append(math.sqrt(window_energy / len(window)))

    onset_count = 0
    if window_rms:
        sorted_windows = sorted(window_rms)
        median_energy = sorted_windows[len(sorted_windows) // 2]
        threshold = max(0.02, median_energy * 0.45)
        for index in range(1, len(window_rms)):
            if window_rms[index] - window_rms[index - 1] > threshold:
                onset_count += 1
    onset_density = onset_count / duration_seconds if duration_seconds else 0

    return {
        "duration_seconds": duration_seconds,
        "sample_rate": sample_rate,
        "channels": 1,
        "rms": rms,
        "peak": peak,
        "crest_factor": crest_factor,
        "dynamic_range_db": dynamic_range_db,
        "zero_crossing_rate": zero_crossing_rate,
        "brightness_proxy": brightness_proxy,
        "low_end_ratio": low_end_ratio,
        "onset_density": onset_density,
    }


def recurrence_strength(feature_matrix):
    if feature_matrix.shape[1] < 4:
        return 0.0

    normalized = librosa.util.normalize(feature_matrix, axis=0)
    similarity = np.dot(normalized.T, normalized)
    mask = ~np.eye(similarity.shape[0], dtype=bool)
    values = similarity[mask]
    return float(np.mean(np.clip(values, 0.0, 1.0))) if values.size else 0.0


def chroma_proxy(power, freqs):
    chroma = np.zeros((12, power.shape[1]), dtype=np.float32)
    mask = freqs >= 27.5
    usable_freqs = freqs[mask]
    usable_power = power[mask]
    midi = 69 + 12 * np.log2(np.maximum(usable_freqs, 27.5) / 440.0)
    pitch_classes = np.mod(np.rint(midi).astype(int), 12)
    for index, pitch_class in enumerate(pitch_classes):
        chroma[pitch_class] += usable_power[index]

    column_sums = np.sum(chroma, axis=0, keepdims=True) + 1e-9
    return chroma / column_sums


def sync_feature_matrix(feature_matrix, frame_boundaries):
    if feature_matrix.shape[1] == 0:
        return feature_matrix
    if frame_boundaries.size < 2:
        return feature_matrix

    clipped = np.unique(np.clip(frame_boundaries.astype(int), 0, feature_matrix.shape[1] - 1))
    if clipped.size < 2:
        return feature_matrix

    boundaries = np.concatenate(([0], clipped, [feature_matrix.shape[1]]))
    slices = []
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        if right <= left:
            continue
        slices.append(np.mean(feature_matrix[:, left:right], axis=1))

    if not slices:
        return feature_matrix

    return np.stack(slices, axis=1)


def analyze_rich(samples, sample_rate):
    if len(samples) == 0:
        legacy = compute_legacy_metrics([], sample_rate)
        return {
            "legacy": legacy,
            "rhythm": {
                "estimated_tempo": 0,
                "tempo_confidence": 0,
                "tempo_stability": 0,
                "onset_to_beat_alignment": 0,
                "syncopation_proxy": 0,
                "inter_beat_loudness_consistency": 0,
                "groove_continuity": 0,
                "onset_strength_mean": 0,
                "onset_strength_std": 0,
                "beats_count": 0,
            },
            "structure": {
                "recurrence_strength": 0,
                "novelty_peak_rate": 0,
                "novelty_mean": 0,
                "repetition_variation_balance": 0,
                "boundary_strength_proxy": 0,
            },
            "tonal": {
                "key_center_stability": 0,
                "harmonic_stability": 0,
                "chord_change_proxy": 0,
                "chroma_entropy": 0,
            },
            "timbre": {
                "spectral_centroid": 0,
                "spectral_rolloff": 0,
                "spectral_bandwidth": 0,
                "spectral_flatness": 0,
                "sub_energy_ratio": 0,
                "bass_energy_ratio": 0,
                "low_mid_energy_ratio": 0,
                "high_band_energy_ratio": 0,
                "dynamic_complexity": 0,
            },
            "notes": ["Empty or unreadable audio payload."],
        }

    y = np.asarray(samples, dtype=np.float32)
    duration_seconds = len(y) / sample_rate
    frame_length = 2048
    hop_length = 512
    notes = []

    rms = float(np.sqrt(np.mean(np.square(y))))
    peak = float(np.max(np.abs(y)))
    crest_factor = peak / (rms + 1e-9)
    dynamic_range_db = float(20 * np.log10((peak + 1e-9) / (rms + 1e-9)))
    zero_crossing_rate = float(np.mean(librosa.feature.zero_crossing_rate(y=y)))

    stft = librosa.stft(y=y, n_fft=frame_length, hop_length=hop_length)
    magnitude = np.abs(stft)
    power = magnitude ** 2
    freqs = librosa.fft_frequencies(sr=sample_rate, n_fft=frame_length)

    spectral_centroid = float(np.mean(librosa.feature.spectral_centroid(S=magnitude, sr=sample_rate)))
    spectral_rolloff = float(np.mean(librosa.feature.spectral_rolloff(S=magnitude, sr=sample_rate)))
    spectral_bandwidth = float(np.mean(librosa.feature.spectral_bandwidth(S=magnitude, sr=sample_rate)))
    spectral_flatness = float(np.mean(librosa.feature.spectral_flatness(S=power + 1e-12)))
    brightness_proxy = spectral_centroid / max(sample_rate / 2, 1)

    total_spectral_energy = float(np.sum(power)) + 1e-9
    sub_energy_ratio = float(np.sum(power[(freqs >= 20) & (freqs < 60)])) / total_spectral_energy
    bass_energy_ratio = float(np.sum(power[(freqs >= 60) & (freqs < 180)])) / total_spectral_energy
    low_mid_energy_ratio = float(np.sum(power[(freqs >= 180) & (freqs < 800)])) / total_spectral_energy
    high_band_energy_ratio = float(np.sum(power[freqs >= 4000])) / total_spectral_energy
    low_end_ratio = sub_energy_ratio + bass_energy_ratio

    onset_env = librosa.onset.onset_strength(y=y, sr=sample_rate, hop_length=hop_length)
    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_env,
        sr=sample_rate,
        hop_length=hop_length,
        units="frames",
        backtrack=False,
    )
    onset_density = len(onset_frames) / max(duration_seconds, 1e-9)
    onset_strength_mean = float(np.mean(onset_env)) if onset_env.size else 0.0
    onset_strength_std = float(np.std(onset_env)) if onset_env.size else 0.0

    min_bpm = 40.0
    max_bpm = 208.0
    min_lag = max(1, int(round((60.0 / max_bpm) * sample_rate / hop_length)))
    max_lag = max(min_lag + 1, int(round((60.0 / min_bpm) * sample_rate / hop_length)))
    ac = librosa.autocorrelate(onset_env, max_size=min(max_lag + 1, onset_env.shape[0])) if onset_env.size else np.array([])
    if ac.size > min_lag:
        search = ac[min_lag : min(max_lag + 1, ac.size)]
        best_lag = int(np.argmax(search) + min_lag)
        tempo = float(60.0 * sample_rate / (best_lag * hop_length))
        tempo_confidence = clamp(ac[best_lag] / (ac[0] + 1e-9))
        first_anchor = int(onset_frames[0]) if onset_frames.size > 0 else 0
        beat_frames = np.arange(first_anchor, onset_env.shape[0], best_lag, dtype=int)
    else:
        best_lag = 0
        tempo = 0.0
        tempo_confidence = 0.0
        beat_frames = np.array([], dtype=int)
    beat_times = librosa.frames_to_time(beat_frames, sr=sample_rate, hop_length=hop_length)
    beat_intervals = np.diff(beat_times) if beat_times.size > 1 else np.array([])

    if beat_intervals.size > 0:
        interval_mean = float(np.mean(beat_intervals))
        interval_std = float(np.std(beat_intervals))
        tempo_stability = clamp(1.0 - (interval_std / (interval_mean + 1e-9)))
    else:
        tempo_stability = 0.0

    if beat_frames.size > 0 and onset_env.size > 0:
        beat_strength = float(np.mean(onset_env[np.clip(beat_frames, 0, onset_env.shape[0] - 1)]))
    else:
        beat_strength = 0.0

    if beat_frames.size > 1 and onset_env.size > 0:
        offbeat_frames = []
        for left, right in zip(beat_frames[:-1], beat_frames[1:]):
            offbeat_frames.append(int(round((left + right) / 2)))
        offbeat_frames = np.asarray(offbeat_frames, dtype=int)
        offbeat_frames = np.clip(offbeat_frames, 0, onset_env.shape[0] - 1)
        offbeat_strength = float(np.mean(onset_env[offbeat_frames])) if offbeat_frames.size else 0.0
    else:
        offbeat_strength = 0.0

    onset_to_beat_alignment = clamp(beat_strength / (beat_strength + offbeat_strength + 1e-9))
    syncopation_proxy = clamp(offbeat_strength / (beat_strength + offbeat_strength + 1e-9))
    syncopation_balance = clamp(1.0 - abs(syncopation_proxy - 0.38) / 0.38)

    frame_rms = librosa.feature.rms(S=magnitude, frame_length=frame_length, hop_length=hop_length)[0]
    if beat_frames.size > 1 and frame_rms.size > 0:
        beat_window_rms = []
        for left, right in zip(beat_frames[:-1], beat_frames[1:]):
            left_index = int(max(0, left))
            right_index = int(min(frame_rms.shape[0], right))
            if right_index <= left_index:
                continue
            beat_window_rms.append(float(np.mean(frame_rms[left_index:right_index])))
        if beat_window_rms:
            beat_window_rms = np.asarray(beat_window_rms)
            loudness_cv = float(np.std(beat_window_rms) / (np.mean(beat_window_rms) + 1e-9))
            inter_beat_loudness_consistency = clamp(1.0 - loudness_cv)
        else:
            inter_beat_loudness_consistency = 0.0
    else:
        inter_beat_loudness_consistency = 0.0

    groove_continuity = float(
        np.mean(
            [
                tempo_confidence,
                tempo_stability,
                onset_to_beat_alignment,
                inter_beat_loudness_consistency,
                syncopation_balance,
            ]
        )
    )

    chroma = chroma_proxy(power, freqs)
    if beat_frames.size > 1:
        beat_frames_for_sync = np.unique(np.clip(beat_frames, 0, chroma.shape[1] - 1))
        chroma_sync = sync_feature_matrix(chroma, beat_frames_for_sync)
    else:
        chroma_sync = chroma

    recurrence = recurrence_strength(chroma_sync)
    if chroma_sync.shape[1] > 1:
        chroma_deltas = np.linalg.norm(np.diff(chroma_sync, axis=1), axis=0)
        novelty_mean = float(np.mean(chroma_deltas))
        peak_threshold = float(np.mean(chroma_deltas) + np.std(chroma_deltas) * 0.5)
        novelty_peaks, _ = find_peaks(chroma_deltas, height=peak_threshold) if chroma_deltas.size else ([], {})
        novelty_peak_rate = len(novelty_peaks) / max(chroma_sync.shape[1], 1)
        harmonic_stability = clamp(1.0 - novelty_mean / 4.0)
        chord_change_proxy = clamp(float(np.mean(chroma_deltas > np.median(chroma_deltas))))
        boundary_strength_proxy = float(np.max(chroma_deltas)) if chroma_deltas.size else 0.0
    else:
        novelty_mean = 0.0
        novelty_peak_rate = 0.0
        harmonic_stability = 0.0
        chord_change_proxy = 0.0
        boundary_strength_proxy = 0.0

    repetition_variation_balance = clamp(1.0 - abs(recurrence - clamp(novelty_mean / 2.5)))
    chroma_mean = np.mean(chroma_sync, axis=1) if chroma_sync.size else np.zeros(12)
    chroma_distribution = chroma_mean / (np.sum(chroma_mean) + 1e-9)
    chroma_entropy = float(-np.sum(chroma_distribution * np.log2(chroma_distribution + 1e-9)))
    key_center_stability = clamp(float(np.max(chroma_distribution)) * 4.0)
    dynamic_complexity = float(np.std(frame_rms)) if frame_rms.size else 0.0

    if beat_frames.size < 4:
        notes.append("Low beat count reduced rhythm-confidence.")
    if duration_seconds < 20:
        notes.append("Short render reduced structure-confidence.")

    legacy = {
        "duration_seconds": duration_seconds,
        "sample_rate": sample_rate,
        "channels": 1,
        "rms": rms,
        "peak": peak,
        "crest_factor": crest_factor,
        "dynamic_range_db": dynamic_range_db,
        "zero_crossing_rate": zero_crossing_rate * sample_rate,
        "brightness_proxy": brightness_proxy,
        "low_end_ratio": low_end_ratio,
        "onset_density": onset_density,
    }

    return {
        "legacy": legacy,
        "rhythm": {
            "estimated_tempo": tempo,
            "tempo_confidence": float(tempo_confidence),
            "tempo_stability": float(tempo_stability),
            "onset_to_beat_alignment": float(onset_to_beat_alignment),
            "syncopation_proxy": float(syncopation_proxy),
            "inter_beat_loudness_consistency": float(inter_beat_loudness_consistency),
            "groove_continuity": float(groove_continuity),
            "onset_strength_mean": float(onset_strength_mean),
            "onset_strength_std": float(onset_strength_std),
            "beats_count": int(len(beat_frames)),
        },
        "structure": {
            "recurrence_strength": float(recurrence),
            "novelty_peak_rate": float(novelty_peak_rate),
            "novelty_mean": float(novelty_mean),
            "repetition_variation_balance": float(repetition_variation_balance),
            "boundary_strength_proxy": float(boundary_strength_proxy),
        },
        "tonal": {
            "key_center_stability": float(key_center_stability),
            "harmonic_stability": float(harmonic_stability),
            "chord_change_proxy": float(chord_change_proxy),
            "chroma_entropy": float(chroma_entropy),
        },
        "timbre": {
            "spectral_centroid": float(spectral_centroid),
            "spectral_rolloff": float(spectral_rolloff),
            "spectral_bandwidth": float(spectral_bandwidth),
            "spectral_flatness": float(spectral_flatness),
            "sub_energy_ratio": float(sub_energy_ratio),
            "bass_energy_ratio": float(bass_energy_ratio),
            "low_mid_energy_ratio": float(low_mid_energy_ratio),
            "high_band_energy_ratio": float(high_band_energy_ratio),
            "dynamic_complexity": float(dynamic_complexity),
        },
        "notes": notes,
    }


def analyze_audio(samples, sample_rate):
    if HAVE_RICH_STACK:
        return analyze_rich(samples, sample_rate)

    legacy = compute_legacy_metrics(samples, sample_rate)
    return {
        "legacy": legacy,
        "rhythm": {
            "estimated_tempo": 0,
            "tempo_confidence": 0,
            "tempo_stability": 0,
            "onset_to_beat_alignment": 0,
            "syncopation_proxy": 0,
            "inter_beat_loudness_consistency": 0,
            "groove_continuity": clamp((legacy["onset_density"] / 10.0) + (legacy["rms"] / 0.2), 0, 1),
            "onset_strength_mean": legacy["onset_density"],
            "onset_strength_std": 0,
            "beats_count": 0,
        },
        "structure": {
            "recurrence_strength": 0,
            "novelty_peak_rate": 0,
            "novelty_mean": 0,
            "repetition_variation_balance": 0,
            "boundary_strength_proxy": 0,
        },
        "tonal": {
            "key_center_stability": 0,
            "harmonic_stability": 0,
            "chord_change_proxy": 0,
            "chroma_entropy": 0,
        },
        "timbre": {
            "spectral_centroid": 0,
            "spectral_rolloff": 0,
            "spectral_bandwidth": 0,
            "spectral_flatness": 0,
            "sub_energy_ratio": 0,
            "bass_energy_ratio": 0,
            "low_mid_energy_ratio": 0,
            "high_band_energy_ratio": 0,
            "dynamic_complexity": 0,
        },
        "notes": [
            "Rich MIR stack unavailable; using stdlib fallback metrics only.",
            f"Import error: {RICH_IMPORT_ERROR}" if RICH_IMPORT_ERROR else "Import error unavailable.",
        ],
    }


def merge_section_payload(analysis, channels):
    legacy = dict(analysis["legacy"])
    legacy["channels"] = channels
    legacy["rhythm"] = analysis["rhythm"]
    legacy["structure"] = analysis["structure"]
    legacy["tonal"] = analysis["tonal"]
    legacy["timbre"] = analysis["timbre"]
    legacy["confidence_notes"] = analysis["notes"]
    return legacy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--song", required=True)
    parser.add_argument("--bpm", default="0")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    mix_path = os.path.join(args.run_dir, "mix.wav")
    sections_dir = os.path.join(args.run_dir, "sections")

    mix_samples, mix_rate, mix_channels = read_audio(mix_path)
    mix_analysis = analyze_audio(mix_samples, mix_rate)

    section_metrics = {}
    if os.path.isdir(sections_dir):
        for name in sorted(os.listdir(sections_dir)):
            if not name.endswith(".wav"):
                continue
            section_path = os.path.join(sections_dir, name)
            section_samples, section_rate, section_channels = read_audio(section_path)
            analysis = analyze_audio(section_samples, section_rate)
            section_metrics[name.replace(".wav", "")] = merge_section_payload(analysis, section_channels)

    payload = {
        "song": args.song,
        "declared_bpm": float(args.bpm),
        "analysis_engine": "librosa-rich" if HAVE_RICH_STACK else "stdlib-fallback",
        "mix": merge_section_payload(mix_analysis, mix_channels),
        "rhythm": mix_analysis["rhythm"],
        "structure": mix_analysis["structure"],
        "tonal": mix_analysis["tonal"],
        "timbre": mix_analysis["timbre"],
        "sections": section_metrics,
        "confidence_notes": mix_analysis["notes"],
    }

    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()
