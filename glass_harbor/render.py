"""Render a resolved mix plan to audio: beat-accurate warping, pitch shifting, DJ-mixer automation, and mastering."""

from __future__ import annotations

import datetime as dt
import json
import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
import soundfile as sf

from glass_harbor import audio as A
from glass_harbor import library
from glass_harbor.plan import (AUTOMATABLE, CHOP_HOLD, CHOP_REST, FREQUENCY_PARAMS, Resolution, ResolvedClip,
                               automation_value, resolve)

BLOCK = 512
DECLICK_SECONDS = 0.004
LOUDNESS_MATCH_LIMIT_DB = 12.0
MAX_LIMITING_DB = 6.0

Log = Callable[[str], None]


@dataclass
class RenderedClip:
    clip: ResolvedClip
    start_sample: int
    audio: np.ndarray  # post-fx, pre-master, starting at start_sample
    dry: np.ndarray  # warped audio before fx (for alignment checks)
    target_beats: list[float]  # output beat times relative to the clip start
    source_offset_ms: float | None
    warp_offset_ms: float | None
    warp_jitter_ms: float | None


def _segment(audio: np.ndarray, start: float, end: float) -> np.ndarray:
    """Slice [start, end) seconds with zero padding outside the track."""
    s0, s1 = int(round(start * A.SR)), int(round(end * A.SR))
    out = np.zeros((max(0, s1 - s0), audio.shape[1]), dtype=np.float32)
    lo, hi = max(s0, 0), min(s1, audio.shape[0])
    if hi > lo:
        out[lo - s0: hi - s0] = audio[lo:hi]
    return out


def _fit_length(audio: np.ndarray, frames: int) -> np.ndarray:
    if audio.shape[0] >= frames:
        return audio[:frames]
    return np.pad(audio, ((0, frames - audio.shape[0]), (0, 0)))


def _rubberband_cli(segment: np.ndarray, src_bounds: np.ndarray, tgt_bounds: np.ndarray, semitones: float,
                    vocal: bool) -> np.ndarray:
    """Rubber Band R3 (offline CLI) with a per-beat key-frame map: sub-millisecond beat placement."""
    binary = shutil.which("rubberband")
    assert binary
    src_len = segment.shape[0]
    ratio = (tgt_bounds[-1] - tgt_bounds[0]) / (src_bounds[-1] - src_bounds[0])
    with tempfile.TemporaryDirectory(prefix="gh-rb-") as tmp:
        tmp_dir = Path(tmp)
        sf.write(tmp_dir / "in.wav", segment, A.SR, subtype="FLOAT")
        cmd = [binary, "-q", "--fine", "-t", f"{ratio:.10f}"]
        inner = zip(src_bounds[1:-1] - src_bounds[0], tgt_bounds[1:-1] - tgt_bounds[0])
        keyframes = [(int(round(s * A.SR)), int(round(t * A.SR))) for s, t in inner]
        if keyframes and not np.allclose(np.diff(src_bounds) / np.diff(tgt_bounds), 1 / ratio, rtol=1e-4):
            (tmp_dir / "map.txt").write_text("".join(f"{s} {t}\n" for s, t in keyframes if 0 < s < src_len))
            cmd += ["-M", str(tmp_dir / "map.txt")]
        if semitones:
            cmd += ["-p", f"{semitones:g}"]
            if vocal:
                cmd.append("-F")
        cmd += [str(tmp_dir / "in.wav"), str(tmp_dir / "out.wav")]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"rubberband failed: {result.stderr.strip()[-500:]}")
        out, _ = sf.read(tmp_dir / "out.wav", dtype="float32", always_2d=True)
    return out


def _pedalboard_r2(segment: np.ndarray, src_bounds: np.ndarray, tgt_bounds: np.ndarray, semitones: float,
                   vocal: bool) -> np.ndarray:
    """Fallback: pedalboard's R2 engine, bar by bar so tempo drift cannot accumulate."""
    import pedalboard

    def stretch(chunk: np.ndarray, factor: float) -> np.ndarray:
        out = pedalboard.time_stretch(np.ascontiguousarray(chunk.T, dtype=np.float32), A.SR,
                                      stretch_factor=factor, pitch_shift_in_semitones=float(semitones),
                                      high_quality=False, transient_mode="mixed" if vocal else "crisp",
                                      preserve_formants=True)
        return np.ascontiguousarray(out.T, dtype=np.float32)

    factors = np.diff(src_bounds) / np.diff(tgt_bounds)
    if np.allclose(factors, factors[0], rtol=1e-4):
        return stretch(segment, float(factors[0]))
    pieces = []
    step = 4
    for i in range(0, len(factors), step):
        j = min(i + step, len(factors))
        s0 = int(round((src_bounds[i] - src_bounds[0]) * A.SR))
        s1 = int(round((src_bounds[j] - src_bounds[0]) * A.SR))
        frames = int(round((tgt_bounds[j] - tgt_bounds[i]) * A.SR))
        factor = (src_bounds[j] - src_bounds[i]) / (tgt_bounds[j] - tgt_bounds[i])
        pieces.append(_fit_length(stretch(segment[s0:s1], factor), frames))
    return np.concatenate(pieces)


def warp(segment: np.ndarray, src_bounds: np.ndarray, tgt_bounds: np.ndarray, semitones: float,
         *, vocal: bool = False) -> np.ndarray:
    """Stretch ``segment`` so each source beat interval lasts exactly its target interval, then pitch shift."""
    target_frames = int(round((tgt_bounds[-1] - tgt_bounds[0]) * A.SR))
    factors = np.diff(src_bounds) / np.diff(tgt_bounds)
    if np.allclose(factors, 1.0, atol=1e-5) and semitones == 0:
        return _fit_length(segment, target_frames)
    engine = _rubberband_cli if shutil.which("rubberband") else _pedalboard_r2
    return _fit_length(engine(segment, src_bounds, tgt_bounds, semitones, vocal), target_frames)


def _fade(audio: np.ndarray, fade_in: float, fade_out: float) -> np.ndarray:
    n = audio.shape[0]
    fi = min(n, max(int(fade_in * A.SR), int(DECLICK_SECONDS * A.SR)))
    fo = min(n, max(int(fade_out * A.SR), int(DECLICK_SECONDS * A.SR)))
    if fi:
        audio[:fi] *= np.sin(np.linspace(0, np.pi / 2, fi))[:, None] ** 2
    if fo:
        audio[n - fo:] *= np.cos(np.linspace(0, np.pi / 2, fo))[:, None] ** 2
    return audio


def _beat_of_time(res: Resolution, seconds: np.ndarray, lo_beat: float, hi_beat: float) -> np.ndarray:
    """Invert the tempo map numerically on a beat grid (fine enough for automation)."""
    beats = np.linspace(lo_beat, hi_beat, max(2, int((hi_beat - lo_beat) * 16) + 1))
    times = np.array([res.tempo.time_at(b) for b in beats])
    return np.interp(seconds, times, beats)


def _apply_mixer(res: Resolution, clip: ResolvedClip, audio: np.ndarray, clip_start_time: float) -> np.ndarray:
    """DJ-mixer channel strip: HP/LP filters, 3-band EQ, gain automation, then echo/reverb sends."""
    import pedalboard

    bpb = res.beats_per_bar
    automation = clip.spec.get("automation") or {}
    n = audio.shape[0]
    tail_beats = float(clip.spec.get("tail_beats", 0))
    end_beat = clip.out_end_beat + tail_beats + 1
    block_times = clip_start_time + (np.arange(0, n, BLOCK) + BLOCK / 2) / A.SR
    block_bars = (_beat_of_time(res, block_times, clip.out_start_beat - 8, end_beat) - clip.anchor_beat) / bpb

    def series(param: str) -> np.ndarray:
        points = automation.get(param)
        return np.array([automation_value(points, b, AUTOMATABLE[param], log_scale=param in FREQUENCY_PARAMS)
                         for b in block_bars])

    filters: list[tuple[str, Any, Callable[[Any, float], None]]] = []
    if "highpass_hz" in automation:
        filters.append(("highpass_hz", pedalboard.HighpassFilter(cutoff_frequency_hz=20.0),
                        lambda p, v: setattr(p, "cutoff_frequency_hz", v)))
    if "lowpass_hz" in automation:
        filters.append(("lowpass_hz", pedalboard.LowpassFilter(cutoff_frequency_hz=20000.0),
                        lambda p, v: setattr(p, "cutoff_frequency_hz", v)))
    if "eq_low_db" in automation:
        filters.append(("eq_low_db", pedalboard.LowShelfFilter(cutoff_frequency_hz=180.0, gain_db=0.0, q=0.7),
                        lambda p, v: setattr(p, "gain_db", v)))
    if "eq_mid_db" in automation:
        filters.append(("eq_mid_db", pedalboard.PeakFilter(cutoff_frequency_hz=1000.0, gain_db=0.0, q=0.7),
                        lambda p, v: setattr(p, "gain_db", v)))
    if "eq_high_db" in automation:
        filters.append(("eq_high_db", pedalboard.HighShelfFilter(cutoff_frequency_hz=4500.0, gain_db=0.0, q=0.7),
                        lambda p, v: setattr(p, "gain_db", v)))

    if filters:
        values = {name: series(name) for name, _, _ in filters}
        board = pedalboard.Pedalboard([plugin for _, plugin, _ in filters])
        constant = all(np.allclose(v, v[0]) for v in values.values())
        if constant:
            for name, plugin, setter in filters:
                setter(plugin, float(values[name][0]))
            audio = board(audio.T, A.SR).T
        else:
            out = np.empty_like(audio)
            for i, start in enumerate(range(0, n, BLOCK)):
                for name, plugin, setter in filters:
                    setter(plugin, float(values[name][i]))
                out[start: start + BLOCK] = board(audio[start: start + BLOCK].T, A.SR, reset=False).T
            audio = out

    if "gain_db" in automation:
        sample_bars = np.interp(np.arange(n), np.arange(0, n, BLOCK) + BLOCK / 2, block_bars)
        points = automation["gain_db"]
        xs = np.array([p[0] for p in points], dtype=float)
        ys = np.array([p[1] for p in points], dtype=float)
        audio = audio * (10.0 ** (np.interp(sample_bars, xs, ys) / 20.0))[:, None]

    fx = clip.spec.get("fx") or {}
    plugins = []
    if "echo" in fx:
        echo = fx["echo"]
        beat_seconds = 60.0 / res.tempo.bpm_at(clip.out_end_beat - 1)
        plugins.append(pedalboard.Delay(delay_seconds=float(echo.get("beats", 0.75)) * beat_seconds,
                                        feedback=float(echo.get("feedback", 0.45)), mix=float(echo.get("mix", 0.35))))
    if "reverb" in fx:
        reverb = fx["reverb"]
        mix = float(reverb.get("mix", 0.2))
        plugins.append(pedalboard.Reverb(room_size=float(reverb.get("room", 0.6)), wet_level=mix,
                                         dry_level=1.0 - 0.5 * mix, width=1.0))
    if plugins:
        audio = pedalboard.Pedalboard(plugins)(audio.T, A.SR).T
    return np.ascontiguousarray(audio, dtype=np.float32)


def _onset_env(audio: np.ndarray) -> tuple[np.ndarray, float]:
    import librosa

    y = librosa.resample(A.mono(audio), orig_sr=A.SR, target_sr=22050)
    hop = 64
    env = librosa.onset.onset_strength(y=y, sr=22050, hop_length=hop, aggregate=np.median, lag=1, max_size=1)
    return env, hop / 22050


def grid_deviation_ms(audio: np.ndarray, beat_times: list[float]) -> tuple[float | None, float | None, float]:
    """Median and spread of (strong onset - expected beat) in ms; None if the material has no clear beat onsets."""
    if audio.shape[0] < A.SR:
        return None, None, 0.0
    env, frame_seconds = _onset_env(audio)
    if not env.size or env.max() <= 0:
        return None, None, 0.0
    threshold = np.median(env) + 2.0 * np.std(env)
    deviations = []
    for beat in beat_times:
        center = int(round(beat / frame_seconds))
        radius = int(round(0.06 / frame_seconds))
        lo, hi = max(0, center - radius), min(env.size, center + radius + 1)
        if hi <= lo:
            continue
        window = env[lo:hi]
        peak = int(np.argmax(window))
        if window[peak] >= threshold:
            deviations.append(((lo + peak) * frame_seconds - beat) * 1000.0)
    coverage = len(deviations) / max(1, len(beat_times))
    if len(deviations) < 4 or coverage < 0.2:
        return None, None, coverage
    deviations = np.array(deviations)
    median = float(np.median(deviations))
    spread = float(np.median(np.abs(deviations - median)))
    return median, spread, coverage


def render_clip(res: Resolution, clip: ResolvedClip, source_audio: np.ndarray, loudness_offset_db: float,
                timeline_offset: float) -> RenderedClip:
    src_bounds = np.array(clip.src_beat_times)
    ratio = clip.out_beats_per_src_beat
    segment = _segment(source_audio, src_bounds[0], src_bounds[-1])
    pieces = []
    out_beat = clip.out_start_beat
    cached: tuple[np.ndarray, np.ndarray] | None = None
    for _ in range(clip.loop):
        out_bounds = np.array([res.tempo.time_at(out_beat + i * ratio) for i in range(clip.src_beats + 1)])
        durations = np.diff(out_bounds)
        if cached is not None and np.allclose(cached[0], durations, atol=1.0 / A.SR):
            piece = cached[1]
        else:
            piece = warp(segment, src_bounds, out_bounds, clip.semitones, vocal=clip.stem == "vocals")
            cached = (durations, piece)
        pieces.append(piece.copy())
        out_beat += clip.src_beats * ratio
    if len(pieces) > 1:
        xfade = int(0.003 * A.SR)
        for piece in pieces[1:]:
            piece[:xfade] *= np.linspace(0, 1, xfade)[:, None]
        dry = np.concatenate(pieces)
    else:
        dry = pieces[0]

    start_time = res.tempo.time_at(clip.out_start_beat)
    first_beat = math.ceil(clip.out_start_beat - 1e-9)
    target_beats = [res.tempo.time_at(b) - start_time
                    for b in range(first_beat, int(math.floor(clip.out_end_beat)) + 1)]
    spec = clip.spec
    bpm_in = res.tempo.bpm_at(clip.out_start_beat)
    bpm_out = res.tempo.bpm_at(max(clip.out_start_beat, clip.out_end_beat - 1))
    audio = dry * A.db_to_gain(clip.gain_db + loudness_offset_db)
    audio = _fade(audio, float(spec.get("fade_in_beats", 0)) * 60.0 / bpm_in,
                  float(spec.get("fade_out_beats", 0)) * 60.0 / bpm_out)
    tail_beats = float(spec.get("tail_beats", 8 if spec.get("fx") else 0))
    if tail_beats:
        audio = np.pad(audio, ((0, int(tail_beats * 60.0 / bpm_out * A.SR)), (0, 0)))
    audio = _apply_mixer(res, clip, audio, start_time)

    source_dev, _, _ = grid_deviation_ms(segment, list(src_bounds[: clip.src_beats] - src_bounds[0]))
    warp_dev, jitter, _ = grid_deviation_ms(dry, target_beats)
    warp_offset = None if warp_dev is None or source_dev is None else warp_dev - source_dev
    return RenderedClip(
        clip=clip,
        start_sample=int(round((start_time + timeline_offset) * A.SR)),
        audio=audio,
        dry=dry,
        target_beats=target_beats,
        source_offset_ms=source_dev,
        warp_offset_ms=warp_offset,
        warp_jitter_ms=jitter,
    )


def _band(signal: np.ndarray, low: float = 1000.0, high: float = 4000.0) -> np.ndarray:
    from scipy.signal import butter, sosfiltfilt

    sos = butter(2, [low, high], btype="bandpass", fs=A.SR, output="sos")
    return sosfiltfilt(sos, signal, axis=0).astype(np.float32)


def _envelope_amount(side: np.ndarray, *, floor_db: float = -45.0, full_db: float = -25.0,
                     attack: float = 0.015, release: float = 0.25) -> np.ndarray:
    """0..1 sidechain amount from a mono trigger signal (block RMS, asymmetric smoothing)."""
    hop = 256
    blocks = int(math.ceil(side.size / hop))
    padded = np.pad(side, (0, blocks * hop - side.size))
    rms_db = 20 * np.log10(np.sqrt(np.mean(padded.reshape(blocks, hop) ** 2, axis=1)) + 1e-9)
    target = np.clip((rms_db - floor_db) / (full_db - floor_db), 0.0, 1.0)
    up = 1 - math.exp(-hop / (attack * A.SR))
    down = 1 - math.exp(-hop / (release * A.SR))
    out = np.empty(blocks)
    current = 0.0
    for i, value in enumerate(target):
        current += (value - current) * (up if value > current else down)
        out[i] = current
    return np.interp(np.arange(side.size), np.arange(blocks) * hop + hop / 2, out)


def apply_ducking(rendered: list["RenderedClip"]) -> None:
    """Bed clips with ``duck`` dip their 1-4 kHz band (and a little level) while the vocal plays."""
    for bed in rendered:
        spec = bed.clip.spec.get("duck")
        if not spec:
            continue
        under = spec.get("under", "vocals")
        triggers = [o for o in rendered if o is not bed and (
            (under == "vocals" and o.clip.stem == "vocals") or (isinstance(under, list) and o.clip.id in under))]
        if not triggers:
            continue
        n = bed.audio.shape[0]
        side = np.zeros(n, dtype=np.float32)
        for other in triggers:
            mono = A.mono(other.audio)
            offset = other.start_sample - bed.start_sample
            lo, hi = max(0, offset), min(n, offset + mono.size)
            if hi > lo:
                side[lo:hi] += mono[lo - offset: hi - offset]
        amount = _envelope_amount(side)
        mid_db = float(spec.get("db", 3.0))
        level_db = float(spec.get("level_db", mid_db * 0.35))
        mid = _band(bed.audio)
        cut = (1.0 - 10.0 ** (-mid_db * amount / 20.0))[:, None]
        level = (10.0 ** (-level_db * amount / 20.0))[:, None]
        bed.audio = ((bed.audio - mid * cut) * level).astype(np.float32)


def vocal_presence(rendered: list["RenderedClip"], total: int, bar_starts: list[tuple[int, int]]) -> list[dict]:
    """Per bar: vocal vs everything else in the 1-4 kHz band where intelligibility lives (dB)."""
    vocal = np.zeros(total, dtype=np.float32)
    rest = np.zeros(total, dtype=np.float32)
    for r in rendered:
        target = vocal if r.clip.stem == "vocals" else rest
        mono = A.mono(r.audio)
        target[r.start_sample: r.start_sample + mono.size] += mono[: max(0, total - r.start_sample)]
    if not np.any(vocal):
        return []
    vocal_band, rest_band = _band(vocal), _band(rest)
    out = []
    for bar, (s0, s1) in bar_starts:
        v = float(np.sqrt(np.mean(vocal_band[s0:s1] ** 2))) if s1 > s0 else 0.0
        if v < 1e-3:
            continue
        b = float(np.sqrt(np.mean(rest_band[s0:s1] ** 2))) if s1 > s0 else 0.0
        out.append({"bar": bar, "db": round(20 * math.log10((v + 1e-9) / (b + 1e-9)), 1)})
    return out


def glue(mix: np.ndarray) -> np.ndarray:
    """Gentle bus compression (about 1-2 dB) so stems from different records sit together."""
    import pedalboard

    level = A.integrated_lufs(mix)
    if not math.isfinite(level):
        return mix
    pre = A.db_to_gain(-16.0 - level)
    comp = pedalboard.Compressor(threshold_db=-12.0, ratio=1.5, attack_ms=10.0, release_ms=150.0)
    return (comp((mix * pre).T, A.SR).T / pre).astype(np.float32)


def _true_peak_envelope(mix: np.ndarray) -> np.ndarray:
    """Per-sample peak including inter-sample overs (4x oversampling), so the ceiling holds as true peak."""
    from scipy.signal import resample_poly

    over = np.abs(resample_poly(mix, 4, 1, axis=0)).max(axis=1)
    frames = mix.shape[0]
    over = np.pad(over, (0, max(0, frames * 4 - over.size)))[: frames * 4]
    return np.maximum(over.reshape(frames, 4).max(axis=1), np.abs(mix).max(axis=1))


def limit(mix: np.ndarray, ceiling_db: float, *, release_ms: float = 80.0, lookahead_ms: float = 3.0) -> np.ndarray:
    """Lookahead brickwall limiter on sample peaks (gain computed at a 32-sample control rate)."""
    from scipy.ndimage import minimum_filter1d, uniform_filter1d

    block = 32
    ceiling = A.db_to_gain(ceiling_db)
    peak = _true_peak_envelope(mix)
    need = np.minimum(1.0, ceiling / np.maximum(peak, 1e-9))
    blocks = int(math.ceil(need.size / block))
    need = np.pad(need, (0, blocks * block - need.size), constant_values=1.0).reshape(blocks, block).min(axis=1)
    reach = max(1, int(math.ceil(lookahead_ms / 1000.0 * A.SR / block)))
    smooth = uniform_filter1d(minimum_filter1d(need, size=2 * reach + 1, mode="nearest"), size=reach + 1,
                              mode="nearest")
    coeff = math.exp(-block / (release_ms / 1000.0 * A.SR))
    gains = np.empty(blocks)
    current = 1.0
    for i, target in enumerate(smooth):
        current = target if target < current else target + (current - target) * coeff
        gains[i] = current
    centers = np.arange(blocks) * block + block / 2
    curve = np.interp(np.arange(mix.shape[0]), centers, gains)
    return (mix * curve[:, None]).astype(np.float32)


def render_chop(res: Resolution, clip: ResolvedClip, source_audio: np.ndarray, loudness_offset_db: float,
                timeline_offset: float) -> RenderedClip:
    """Vocal chops: trigger named slices on a step pattern; each hit is warped to tempo, pitched, optionally
    reversed, and choked by the next hit or rest."""
    chop = clip.chop or {}
    step, steps = chop["step"], chop["steps"]
    ratio = clip.out_beats_per_src_beat
    anchor = clip.anchor_beat
    start_time = res.tempo.time_at(anchor)
    frames = int(round((res.tempo.time_at(anchor + clip.out_beats) - start_time) * A.SR))
    dry = np.zeros((frames, 2), dtype=np.float32)
    count = int(round(clip.out_beats / step))
    events = [(i, steps[i % len(steps)]) for i in range(count) if steps[i % len(steps)] != CHOP_HOLD]
    pieces: dict[tuple[str, int], np.ndarray] = {}
    for k, (i, name) in enumerate(events):
        if name == CHOP_REST:
            continue
        piece_spec = chop["slices"][name]
        beat = anchor + i * step
        t0 = res.tempo.time_at(beat) - start_time
        natural = res.tempo.time_at(beat + piece_spec["beats"] * ratio) - start_time
        next_step = events[k + 1][0] if k + 1 < len(events) else count
        choke = res.tempo.time_at(anchor + next_step * step) - start_time
        target = natural - t0
        key = (name, int(round(target * A.SR)))
        if key not in pieces:
            segment = _segment(source_audio, piece_spec["start"], piece_spec["end"])
            piece = warp(segment, np.array([piece_spec["start"], piece_spec["end"]]), np.array([0.0, target]),
                         clip.semitones + piece_spec["semitones"], vocal=clip.stem == "vocals")
            pieces[key] = piece[::-1].copy() if piece_spec["reverse"] else piece
        hit = _fade(pieces[key][: max(0, int(round((min(natural, choke) - t0) * A.SR)))].copy(), 0.002, 0.006)
        s0 = int(round(t0 * A.SR))
        room = max(0, min(hit.shape[0], frames - s0))
        dry[s0: s0 + room] += hit[:room]
    spec = clip.spec
    audio = dry * A.db_to_gain(clip.gain_db + loudness_offset_db)
    tail_beats = float(spec.get("tail_beats", 8 if spec.get("fx") else 0))
    if tail_beats:
        bpm_out = res.tempo.bpm_at(max(anchor, clip.out_end_beat - 1))
        audio = np.pad(audio, ((0, int(tail_beats * 60.0 / bpm_out * A.SR)), (0, 0)))
    audio = _apply_mixer(res, clip, audio, start_time)
    return RenderedClip(clip=clip, start_sample=int(round((start_time + timeline_offset) * A.SR)), audio=audio,
                        dry=dry, target_beats=[], source_offset_ms=None, warp_offset_ms=None, warp_jitter_ms=None)


def render_generated(res: Resolution, clip: ResolvedClip, timeline_offset: float) -> RenderedClip:
    from glass_harbor import fx as generators

    start_time = res.tempo.time_at(clip.anchor_beat)
    seconds = res.tempo.time_at(clip.anchor_beat + clip.out_beats) - start_time
    dry = generators.generate(clip.spec["generate"], seconds)
    audio = dry * A.db_to_gain(clip.gain_db)
    tail_beats = float(clip.spec.get("tail_beats", 8 if clip.spec.get("fx") else 0))
    if tail_beats:
        audio = np.pad(audio, ((0, int(tail_beats * 60.0 / res.tempo.bpm_at(clip.out_end_beat - 1) * A.SR)), (0, 0)))
    audio = _apply_mixer(res, clip, audio, start_time)
    return RenderedClip(clip=clip, start_sample=int(round((start_time + timeline_offset) * A.SR)), audio=audio,
                        dry=dry, target_beats=[], source_offset_ms=None, warp_offset_ms=None, warp_jitter_ms=None)


def master(mix: np.ndarray, *, lufs: float, ceiling_db: float,
           max_limiting_db: float = MAX_LIMITING_DB) -> tuple[np.ndarray, dict[str, float]]:
    """Gain to the loudness target through the limiter, but never squash more than ``max_limiting_db``."""
    measured = A.integrated_lufs(mix)
    if not math.isfinite(measured):
        return mix, {"input_lufs": measured, "output_lufs": measured, "gain_db": 0.0}
    gain_db = lufs - measured
    out = mix
    for _ in range(5):
        out = limit(mix * A.db_to_gain(gain_db), ceiling_db - 0.2)
        achieved = A.integrated_lufs(out)
        reduction = gain_db - (achieved - measured)
        if reduction > max_limiting_db:
            gain_db -= reduction - max_limiting_db
            out = limit(mix * A.db_to_gain(gain_db), ceiling_db - 0.2)
            break
        if abs(achieved - lufs) < 0.2:
            break
        gain_db += lufs - achieved
    peak = A.true_peak_db(out)
    if peak > ceiling_db:
        out = out * A.db_to_gain(ceiling_db - peak)
    out = np.clip(out, -1.0, 1.0).astype(np.float32)
    return out, {"input_lufs": round(measured, 2), "gain_db": round(gain_db, 2),
                 "output_lufs": round(A.integrated_lufs(out), 2), "true_peak_db": round(A.true_peak_db(out), 2),
                 "limiting_db": round(gain_db - (A.integrated_lufs(out) - measured), 2)}


def render_plan(plan: dict[str, Any], out_dir: Path, *, start_bar: float | None = None,
                end_bar: float | None = None, write_clips: bool = False, mp3: bool = True,
                log: Log = print) -> dict[str, Any]:
    res = resolve(plan)
    if not res.ok:
        errors = "\n".join(f"- {i.where}: {i.message}" for i in res.issues if i.level == "error")
        raise ValueError(f"Plan has errors:\n{errors}")
    bpb = res.beats_per_bar
    clips = res.clips
    if start_bar is not None or end_bar is not None:
        lo = ((start_bar or 1) - 1) * bpb
        hi = (end_bar * bpb) if end_bar is not None else math.inf
        clips = [c for c in clips if c.out_end_beat > lo and c.out_start_beat < hi]
        if not clips:
            raise ValueError("No clips intersect the requested bar range.")

    master_spec = plan.get("master") or {}
    match_loudness = master_spec.get("match_loudness", True)
    earliest = min(res.tempo.time_at(c.out_start_beat) for c in clips)
    timeline_offset = max(0.0, -earliest)

    cache: dict[tuple[str, str], np.ndarray] = {}
    rendered: list[RenderedClip] = []
    for clip in clips:
        if clip.spec.get("generate"):
            log(f"rendering {clip.id}: generated {clip.spec['generate']} -> bars {clip.spec['at_bar']}+{clip.spec['bars']}")
            rendered.append(render_generated(res, clip, timeline_offset))
            continue
        key = (clip.track, clip.stem)
        if key not in cache:
            cache[key] = library.load_audio(clip.track, clip.stem)
        offset_db = 0.0
        if match_loudness:
            track_lufs = float(res.analyses[clip.track].get("loudness_lufs", A.REFERENCE_LUFS))
            if math.isfinite(track_lufs):
                offset_db = float(np.clip(A.REFERENCE_LUFS - track_lufs, -LOUDNESS_MATCH_LIMIT_DB,
                                          LOUDNESS_MATCH_LIMIT_DB))
        if clip.chop is not None:
            log(f"rendering {clip.id}: {len(clip.chop['slices'])} chop slices from {clip.track}/{clip.stem}"
                f" -> bars {clip.spec['at_bar']}+{clip.spec['bars']}")
            rendered.append(render_chop(res, clip, cache[key], offset_db, timeline_offset))
            continue
        log(f"rendering {clip.id}: {clip.track}/{clip.stem} bars {clip.spec['from_bar']}+{clip.spec['bars']}"
            f" -> bar {clip.spec['at_bar']} ({clip.stretch_pct:+.1f}% stretch, {clip.semitones:+d} st)")
        rendered.append(render_clip(res, clip, cache[key], offset_db, timeline_offset))

    apply_ducking(rendered)
    total = max(r.start_sample + r.audio.shape[0] for r in rendered)
    mix = np.zeros((total, 2), dtype=np.float32)
    for r in rendered:
        mix[r.start_sample: r.start_sample + r.audio.shape[0]] += r.audio
    last_bar = int(max(c.out_end_beat for c in clips) // bpb) + 1
    bar_spans = []
    for bar in range(1, last_bar + 1):
        s0 = int(round((res.tempo.time_at((bar - 1) * bpb) + timeline_offset) * A.SR))
        s1 = int(round((res.tempo.time_at(bar * bpb) + timeline_offset) * A.SR))
        if 0 <= s0 < total:
            bar_spans.append((bar, (s0, min(s1, total))))
    presence = vocal_presence(rendered, total, bar_spans)
    if master_spec.get("glue", True):
        mix = glue(mix)

    crop_start = 0
    if start_bar is not None or end_bar is not None:
        lo_t = res.tempo.time_at(((start_bar or 1) - 1) * bpb) + timeline_offset
        crop_start = max(0, int(round(lo_t * A.SR)))
        crop_end = total if end_bar is None else min(total, int(round(
            (res.tempo.time_at(end_bar * bpb) + timeline_offset) * A.SR)))
        mix = mix[crop_start:crop_end]

    mastered, master_stats = master(mix, lufs=float(master_spec.get("lufs", -9.0)),
                                    ceiling_db=float(master_spec.get("ceiling_db", -1.0)))

    out_dir.mkdir(parents=True, exist_ok=True)
    wav_path = A.save(out_dir / "mix.wav", mastered, subtype="PCM_24")
    mp3_path = A.encode_mp3(wav_path, out_dir / "mix.mp3") if mp3 else None
    if write_clips:
        clip_dir = out_dir / "clips"
        for n, r in enumerate(rendered, start=1):
            full = np.zeros((total, 2), dtype=np.float32)
            full[r.start_sample: r.start_sample + r.audio.shape[0]] = r.audio
            A.save(clip_dir / f"{n:02d}-{r.clip.id}.wav", full[crop_start: crop_start + mix.shape[0]],
                   subtype="FLOAT")

    report = {
        "rendered_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "title": plan.get("title", ""),
        "tempo": res.tempo.describe(bpb),
        "range": {"start_bar": start_bar, "end_bar": end_bar},
        "timeline_offset_s": round(timeline_offset, 4),
        "duration_s": round(mastered.shape[0] / A.SR, 3),
        "files": {"wav": wav_path.name, "mp3": mp3_path.name if mp3_path else None},
        "master": master_stats,
        "issues": [i.to_dict() for i in res.issues],
        "vocal_presence": presence,
        "clips": [
            {
                "id": r.clip.id,
                "track": r.clip.track,
                "stem": r.clip.stem,
                "start_s": round(r.start_sample / A.SR - crop_start / A.SR, 4),
                "length_s": round(r.dry.shape[0] / A.SR, 4),
                "stretch_pct": round(r.clip.stretch_pct, 2),
                "semitones": r.clip.semitones,
                "source_grid_offset_ms": None if r.source_offset_ms is None else round(r.source_offset_ms, 1),
                "warp_offset_ms": None if r.warp_offset_ms is None else round(r.warp_offset_ms, 1),
                "warp_jitter_ms": None if r.warp_jitter_ms is None else round(r.warp_jitter_ms, 1),
            }
            for r in rendered
        ],
    }
    (out_dir / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    (out_dir / "render.json").write_text(json.dumps(report, indent=2) + "\n")
    return report
