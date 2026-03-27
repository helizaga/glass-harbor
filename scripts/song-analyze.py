#!/usr/bin/env python3

import argparse
import json
import math
import os
import struct
import wave


def read_wav(path):
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


def compute_metrics(samples, sample_rate):
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--song", required=True)
    parser.add_argument("--bpm", default="0")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    mix_path = os.path.join(args.run_dir, "mix.wav")
    sections_dir = os.path.join(args.run_dir, "sections")

    mix_samples, mix_rate, mix_channels = read_wav(mix_path)
    mix_metrics = compute_metrics(mix_samples, mix_rate)
    mix_metrics["channels"] = mix_channels

    section_metrics = {}
    if os.path.isdir(sections_dir):
        for name in sorted(os.listdir(sections_dir)):
            if not name.endswith(".wav"):
                continue
            section_path = os.path.join(sections_dir, name)
            section_samples, section_rate, section_channels = read_wav(section_path)
            metrics = compute_metrics(section_samples, section_rate)
            metrics["channels"] = section_channels
            section_metrics[name.replace(".wav", "")] = metrics

    payload = {
        "song": args.song,
        "declared_bpm": float(args.bpm),
        "mix": mix_metrics,
        "sections": section_metrics,
    }

    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()
