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
GATE_DB = 14.0  # acapella level between words (separation bleed from the original beat)
GROOVE_LOCK = 0.4  # share of the way word onsets move onto the flow's 16th grid
PHONE_LUFS = -8.0  # sent as a file, nothing normalizes it: loud like a release, a little less squashed than the club master
LOUDEST_TARGET_LUFS = -6.0  # club masters for loud genres (DnB, EDM); reached with drum clipping + limiting
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
    notes: dict[str, Any] | None = None

    @property
    def dry_frames(self) -> int:
        return int(self.notes.get("_dry_frames", self.dry.shape[0])) if self.notes else int(self.dry.shape[0])


_CODE_HASH: str | None = None


def _code_hash() -> str:
    """Changes whenever the rendering code changes, so stale cached clips are never reused."""
    global _CODE_HASH
    if _CODE_HASH is None:
        import hashlib

        digest = hashlib.sha256()
        here = Path(__file__).parent
        for name in ("render.py", "vocals.py", "drums.py", "fx.py", "spectral.py", "plan.py", "tempo.py", "grid.py"):
            digest.update((here / name).read_bytes())
        _CODE_HASH = digest.hexdigest()[:16]
    return _CODE_HASH


class ClipCache:
    """Rendered clips keyed by everything that shapes them: the clip and source spec, the source files, the tempo
    map, the groove settings, and the rendering code. An edit to one clip re-renders only that clip."""

    def __init__(self, folder: Path, plan: dict[str, Any], timeline_offset: float):
        self.folder = folder
        self.plan = plan
        self.base = {"code": _code_hash(), "tempo": plan.get("tempo"), "bpm": plan.get("bpm"),
                     "bpb": plan.get("beats_per_bar", 4), "groove": plan.get("groove"),
                     "offset": round(timeline_offset, 6)}

    def _files(self, clip: ResolvedClip) -> list[Any]:
        if not clip.track:
            src = (self.plan.get("sources") or {}).get(clip.spec.get("source", ""), {})
            track = src.get("track")
        else:
            track = clip.track
        if not track:
            return []
        stats = []
        folder = library.track_dir(track)
        for path in sorted(folder.glob("**/*")):
            if path.is_file() and path.suffix in (".flac", ".json"):
                st = path.stat()
                stats.append([str(path.relative_to(folder)), st.st_size, st.st_mtime_ns])
        return stats

    def key(self, clip: ResolvedClip, offset_db: float) -> str:
        import hashlib

        source = (self.plan.get("sources") or {}).get(clip.spec.get("source", ""), {})
        payload = {**self.base, "clip": clip.spec, "source": source, "offset_db": round(offset_db, 4),
                   "files": self._files(clip)}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:32]

    def load(self, clip: ResolvedClip, offset_db: float) -> RenderedClip | None:
        key = self.key(clip, offset_db)
        meta_path, audio_path = self.folder / f"{key}.json", self.folder / f"{key}.npy"
        if not (meta_path.exists() and audio_path.exists()):
            return None
        meta = json.loads(meta_path.read_text())
        return RenderedClip(clip=clip, start_sample=int(meta["start_sample"]), audio=np.load(audio_path),
                            dry=np.zeros((0, 2), dtype=np.float32), target_beats=[],
                            source_offset_ms=meta["source_offset_ms"], warp_offset_ms=meta["warp_offset_ms"],
                            warp_jitter_ms=meta["warp_jitter_ms"], notes={**(meta.get("notes") or {}),
                                                                         "_dry_frames": meta["dry_frames"]})

    def store(self, clip: ResolvedClip, offset_db: float, rendered: RenderedClip) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        key = self.key(clip, offset_db)
        np.save(self.folder / f"{key}.npy", rendered.audio)
        notes = {k: v for k, v in (rendered.notes or {}).items() if not k.startswith("_")}
        (self.folder / f"{key}.json").write_text(json.dumps({
            "start_sample": rendered.start_sample, "dry_frames": rendered.dry_frames,
            "source_offset_ms": rendered.source_offset_ms, "warp_offset_ms": rendered.warp_offset_ms,
            "warp_jitter_ms": rendered.warp_jitter_ms, "notes": notes}))


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


def _pump_gain(res: Resolution, start_time: float, frames: int, spec: dict[str, Any],
               lo_beat: float, hi_beat: float) -> np.ndarray:
    from glass_harbor.spectral import pump_curve

    step = 32
    times = start_time + np.arange(0, frames, step) / A.SR
    beats = _beat_of_time(res, times, lo_beat - 8, hi_beat + 16)
    coarse = pump_curve(beats, db=float(spec.get("db", 4.0)), release=float(spec.get("release", 0.5)))
    return np.interp(np.arange(frames), np.arange(0, frames, step), coarse).astype(np.float32)


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

    if "width" in automation:
        sample_bars = np.interp(np.arange(n), np.arange(0, n, BLOCK) + BLOCK / 2, block_bars)
        xs = np.array([p[0] for p in automation["width"]], dtype=float)
        ys = np.array([p[1] for p in automation["width"]], dtype=float)
        width = np.interp(sample_bars, xs, ys)
        mid = (audio[:, 0] + audio[:, 1]) / 2
        side = (audio[:, 0] - audio[:, 1]) / 2 * width
        audio = np.stack([mid + side, mid - side], axis=1)
    for lane in ("gain_db", "arrange_db"):
        if lane not in automation:
            continue
        sample_bars = np.interp(np.arange(n), np.arange(0, n, BLOCK) + BLOCK / 2, block_bars)
        points = automation[lane]
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
    if clip.spec.get("pump"):
        audio = audio * _pump_gain(res, clip_start_time, audio.shape[0], clip.spec["pump"], clip.out_start_beat,
                                   clip.out_end_beat)[:, None]
    return np.ascontiguousarray(audio, dtype=np.float32)


def _onset_env(audio: np.ndarray) -> tuple[np.ndarray, float]:
    import librosa

    y = librosa.resample(A.mono(audio), orig_sr=A.SR, target_sr=22050)
    hop = 64
    env = librosa.onset.onset_strength(y=y, sr=22050, hop_length=hop, aggregate=np.median, lag=1, max_size=1)
    return env, hop / 22050


def grid_deviation_ms(audio: np.ndarray, beat_times: list[float], *, max_beats: int = 48
                      ) -> tuple[float | None, float | None, float]:
    """Median and spread of (strong onset - expected beat) in ms; None if the material has no clear beat onsets.
    Only the first ``max_beats`` beats are checked: plenty to catch an offset grid, a fraction of the cost."""
    beat_times = list(beat_times)[:max_beats]
    if beat_times:
        audio = audio[: int((beat_times[-1] + 1.0) * A.SR)]
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


def clip_tail_beats(clip: ResolvedClip) -> float:
    """Beats of effect tail (reverb, echo, delay throws) rendered past a clip's end. One policy for rendering and
    for choosing which clips a bar-range preview needs."""
    from glass_harbor import vocals

    spec = clip.spec
    if spec.get("generate") or clip.chop is not None:
        default = 8 if spec.get("fx") else 0
    else:
        chain = spec.get("chain", vocals.default_chain(clip.stem, False))
        default = 8 if spec.get("fx") else (4 if chain in ("rap", "hook") else 0)
    return float(spec.get("tail_beats", default))


def render_clip(res: Resolution, clip: ResolvedClip, source_audio: np.ndarray, loudness_offset_db: float,
                timeline_offset: float, lyrics: dict[str, Any] | None = None) -> RenderedClip:
    from glass_harbor import vocals

    spec = clip.spec
    ratio = clip.out_beats_per_src_beat
    src_bounds = np.array(clip.src_beat_times)
    out_start = clip.out_start_beat
    is_vocal = clip.stem == "vocals" and clip.loop == 1
    chain = spec.get("chain", vocals.default_chain(clip.stem, False))
    notes: dict[str, Any] = {}

    edges = None
    if is_vocal and spec.get("word_safe", True):
        beat = (src_bounds[-1] - src_bounds[0]) / clip.src_beats
        words = [w for seg in lyrics["segments"] for w in seg["words"]] if lyrics else None
        edges = vocals.word_safe_edges(src_bounds[0], src_bounds[-1], words, beat,
                                       vocal=None if words else source_audio)
        pre = vocals.beats_needed(src_bounds[0] - edges.start, beat)
        post = vocals.beats_needed(edges.end - src_bounds[-1], beat)
        if pre or post:
            src_bounds = np.concatenate([src_bounds[0] - beat * np.arange(pre, 0, -1), src_bounds,
                                         src_bounds[-1] + beat * np.arange(1, post + 1)])
            out_start -= pre * ratio
        notes["edges"] = vocals.describe_edges(edges, (clip.src_beat_times[0], clip.src_beat_times[-1]))

    src_beats = len(src_bounds) - 1
    segment = _segment(source_audio, src_bounds[0], src_bounds[-1])
    beat_src = src_bounds.copy()  # beat boundaries only (groove keyframes get added below)
    words = [w for seg in lyrics["segments"] for w in seg["words"]] if (is_vocal and lyrics) else []
    lock = float(spec.get("groove_lock", GROOVE_LOCK)) if is_vocal and clip.loop == 1 else 0.0
    pieces = []
    out_beat = out_start
    cached: tuple[np.ndarray, np.ndarray] | None = None
    out_bounds = np.array([])
    for _ in range(clip.loop):
        out_bounds = np.array([res.tempo.time_at(out_beat + i * ratio) for i in range(src_beats + 1)])
        if lock > 0 and words:
            # Pull word onsets part of the way onto the flow's 16th grid: extra warp keyframes between the beats.
            onsets = [w["start"] for w in words if src_bounds[0] < w["start"] < src_bounds[-1]]
            src_bounds, out_bounds, shifts = vocals.groove_keyframes(src_bounds, out_bounds, onsets, lock)
            if shifts:
                notes["groove_lock"] = {"moved": len(shifts),
                                        "mean_ms": round(1000 * float(np.mean(np.abs(shifts))), 1)}
        durations = np.diff(out_bounds)
        if cached is not None and np.allclose(cached[0], durations, atol=1.0 / A.SR):
            piece = cached[1]
        else:
            piece = warp(segment, src_bounds, out_bounds, clip.semitones, vocal=clip.stem == "vocals")
            cached = (durations, piece)
        pieces.append(piece.copy())
        out_beat += src_beats * ratio
    if len(pieces) > 1:
        xfade = int(0.003 * A.SR)
        for piece in pieces[1:]:
            piece[:xfade] *= np.linspace(0, 1, xfade)[:, None]
        dry = np.concatenate(pieces)
    else:
        dry = pieces[0]

    start_time = res.tempo.time_at(out_start)
    out_end = out_start + src_beats * ratio * clip.loop
    first_beat = math.ceil(out_start - 1e-9)
    target_beats = [res.tempo.time_at(b) - start_time for b in range(first_beat, int(math.floor(out_end)) + 1)]
    bpm_in = res.tempo.bpm_at(clip.out_start_beat)
    bpm_out = res.tempo.bpm_at(max(clip.out_start_beat, clip.out_end_beat - 1))

    def to_clip_time(src_seconds: float) -> float:
        return float(np.interp(src_seconds, src_bounds, out_bounds - out_bounds[0]))

    processed = dry
    if edges is not None:
        processed = vocals.mask(processed, to_clip_time(edges.start), to_clip_time(edges.end))
    gate = spec.get("gate", True)
    if is_vocal and words and gate is not False:
        spans = [(to_clip_time(w["start"]), to_clip_time(w["end"])) for w in words
                 if w["end"] > src_bounds[0] and w["start"] < src_bounds[-1]]
        processed, closed = vocals.gate_between_words(processed, spans,
                                                      depth_db=GATE_DB if gate is True else float(gate))
        notes["gate_closed_pct"] = round(100 * closed, 1)
    if is_vocal and spec.get("ride", True):
        processed, notes["ride_max_db"] = vocals.ride(processed)
        notes["ride_max_db"] = round(notes["ride_max_db"], 1)
    if is_vocal and float(spec.get("tune", 0)) > 0:
        key = res.analyses[clip.track]["key"]
        processed, cents = vocals.tune(processed, (int(key["tonic"]) + clip.semitones) % 12, key["mode"],
                                       float(spec["tune"]))
        notes["tune_cents"] = round(cents, 1)
    processed = _fade(processed, float(spec.get("fade_in_beats", 0)) * 60.0 / bpm_in,
                      float(spec.get("fade_out_beats", 0)) * 60.0 / bpm_out)
    if spec.get("punch") and not is_vocal:
        from glass_harbor.drums import punch

        processed = punch(processed, attack_db=float(spec["punch"].get("attack_db", 3.0)),
                          parallel=float(spec["punch"].get("parallel", 0.3)))
    if spec.get("clip_db") and not is_vocal:
        # Clip the drum bus: the sharpest transients give up a few dB so the master gets louder before limiting.
        peak = float(np.max(np.abs(processed))) if processed.size else 0.0
        if peak > 0:
            processed = soft_clipper(processed, A.gain_to_db(peak) - float(spec["clip_db"]), knee=0.7)
            notes["clipped_db"] = float(spec["clip_db"])
    tail_beats = clip_tail_beats(clip)
    if tail_beats:
        processed = np.pad(processed, ((0, int(tail_beats * 60.0 / bpm_out * A.SR)), (0, 0)))
    if chain != "none":
        window = (edges.start, edges.end) if edges is not None else (src_bounds[0], src_bounds[-1])
        throws = vocals.throw_regions_from_words(lyrics["segments"], to_clip_time, window) if lyrics else []
        dry_part, wet_part = vocals.apply_chain(processed, chain, beat_seconds=60.0 / bpm_out, throw_regions=throws,
                                                split=True, doubles=spec.get("doubles"),
                                                octave=bool(spec.get("octave", False)),
                                                density=spec.get("density"))
        pump_fx = (res.plan.get("groove") or {}).get("pump_fx")
        if pump_fx and np.any(wet_part):
            wet_part = wet_part * _pump_gain(res, start_time, wet_part.shape[0], pump_fx, out_start, out_end)[:, None]
            notes["pumped_fx"] = True
        processed = dry_part + wet_part
        notes["chain"] = chain
        notes["throws"] = len(throws)
    audio = processed * A.db_to_gain(clip.gain_db + loudness_offset_db)
    audio = _apply_mixer(res, clip, audio, start_time)

    source_dev, _, _ = grid_deviation_ms(segment, list(beat_src[:src_beats] - beat_src[0]))
    warp_dev, jitter, warp_coverage = grid_deviation_ms(dry, target_beats)
    notes["warp_coverage"] = round(warp_coverage, 2)  # share of beats with a clear onset: how much QA can judge
    warp_offset = None if warp_dev is None or source_dev is None else warp_dev - source_dev
    nudge = float(spec.get("nudge_ms", 0.0)) / 1000.0
    if nudge:
        notes["nudge_ms"] = spec["nudge_ms"]
    return RenderedClip(
        clip=clip,
        start_sample=max(0, int(round((start_time + timeline_offset + nudge) * A.SR))),
        audio=audio,
        dry=dry,
        target_beats=target_beats,
        source_offset_ms=source_dev,
        warp_offset_ms=warp_offset,
        warp_jitter_ms=jitter,
        notes=notes,
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
        mid_db = float(spec.get("db", 3.0))
        if spec.get("mode", "spectral") == "spectral":
            from glass_harbor.spectral import spectral_duck

            bed.audio = spectral_duck(bed.audio, np.repeat(side[:, None], 2, axis=1), max_db=mid_db,
                                      level_db=float(spec.get("level_db", 1.0)))
            continue
        amount = _envelope_amount(side)
        level_db = float(spec.get("level_db", mid_db * 0.35))
        mid = _band(bed.audio)
        cut = (1.0 - 10.0 ** (-mid_db * amount / 20.0))[:, None]
        level = (10.0 ** (-level_db * amount / 20.0))[:, None]
        bed.audio = ((bed.audio - mid * cut) * level).astype(np.float32)


# A bar whose vocal sounds this far under the vocal's usual level is a fading tail, not a line. Rapped lines sat
# within 3 dB of each other in 1 Umbrella over Starboy; the decay of its last "yeah" sat 17 dB under the median.
VOCAL_TAIL_DB = 12.0


def vocal_presence(rendered: list["RenderedClip"], total: int, bar_starts: list[tuple[int, int]]) -> list[dict]:
    """Per bar: vocal vs everything else in the 1-4 kHz band where intelligibility lives (dB). Bars where the vocal
    is only a tail (the reverb or breath after a song's last word, ``VOCAL_TAIL_DB`` under its usual level) are left
    out: the beat over a fading "yeah" is not burying a line (1 Umbrella's last bar read -3.8 dB that way). The usual
    level is the upper quartile over the bars where the vocal sounds, so a tail longer than the lines cannot lower
    it."""
    vocal = np.zeros(total, dtype=np.float32)
    rest = np.zeros(total, dtype=np.float32)
    for r in rendered:
        target = vocal if r.clip.stem == "vocals" else rest
        mono = A.mono(r.audio)
        target[r.start_sample: r.start_sample + mono.size] += mono[: max(0, total - r.start_sample)]
    if not np.any(vocal):
        return []
    vocal_band, rest_band = _band(vocal), _band(rest)
    block = int(0.05 * A.SR)
    levels = []
    for bar, (s0, s1) in bar_starts:
        n = (s1 - s0) // block
        if n < 1:
            continue
        v_blocks = np.sqrt(np.mean(vocal_band[s0:s0 + n * block].reshape(n, block) ** 2, axis=1))
        if v_blocks.max() < 1e-3:
            continue
        # Only while the vocal sounds: a chant bar is mostly gaps, and the beat in those gaps is not masking it.
        active = v_blocks > max(1e-3, v_blocks.max() * 10 ** (-15 / 20))
        r_blocks = np.sqrt(np.mean(rest_band[s0:s0 + n * block].reshape(n, block) ** 2, axis=1))
        levels.append((bar, float(np.sqrt(np.mean(v_blocks[active] ** 2))), float(np.sqrt(np.mean(r_blocks[active] ** 2)))))
    if not levels:
        return []
    usual = float(np.percentile([v for _, v, _ in levels], 75))
    return [{"bar": bar, "db": round(20 * math.log10((v + 1e-9) / (b + 1e-9)), 1)}
            for bar, v, b in levels if v >= usual * 10 ** (-VOCAL_TAIL_DB / 20)]


def _balance_lu(vocal: np.ndarray, rest: np.ndarray, min_seconds: float = 5.0) -> tuple[float, float] | None:
    """Loudness of ``vocal`` over ``rest`` (LU, BS.1770) on the 100 ms frames where the vocal sounds (within 30 dB of
    its loudest frame), and how long that is. None when the vocal sounds for less than ``min_seconds``."""
    frame = int(0.1 * A.SR)
    k = min(vocal.shape[0], rest.shape[0]) // frame
    if k == 0:
        return None
    v = vocal[: k * frame].reshape(k, frame, -1)
    r = rest[: k * frame].reshape(k, frame, -1)
    level = np.sqrt(np.mean(v**2, axis=(1, 2)))
    active = level > max(1e-6, level.max() * 10 ** (-30 / 20))
    seconds = float(active.sum() * frame / A.SR)
    if seconds < min_seconds:
        return None
    v_lufs = A.integrated_lufs(v[active].reshape(-1, v.shape[2]))
    r_lufs = A.integrated_lufs(r[active].reshape(-1, r.shape[2]))
    if not (math.isfinite(v_lufs) and math.isfinite(r_lufs)):
        return None
    return round(v_lufs - r_lufs, 1), round(seconds, 1)


def record_balance(track_id: str) -> float | None:
    """The same measure on the vocal's own record: its separated vocals (before any cleanup) over its instrumental."""
    vocals = library.stem_path(track_id, "vocals")
    raw = vocals.parent / "raw" / vocals.name
    instrumental = library.stem_path(track_id, "instrumental")
    if not (vocals.exists() and instrumental.exists()):
        return None
    measured = _balance_lu(A.load(raw if raw.exists() else vocals), A.load(instrumental))
    return measured[0] if measured else None


def vocal_balance(rendered: list["RenderedClip"], total: int, keep: tuple[int, int] | None = None) -> list[dict]:
    """Per vocal track: how loud it sits over everything that is not a vocal, where it sounds (LU), next to the same
    measure on its own record. Hit records keep the lead within a few dB of the band (Gerdes & Siedenburg, JASA
    Express Letters 2023), so a vocal far louder than on its own record buries the beat. ``keep`` limits it to the
    samples a range render keeps."""
    lo, hi = keep or (0, total)
    vocals = [r for r in rendered if r.clip.stem == "vocals" and r.clip.chop is None]
    if not vocals:
        return []
    rest = np.zeros((total, 2), dtype=np.float32)
    for r in rendered:
        if r.clip.stem != "vocals":
            rest[r.start_sample: r.start_sample + r.audio.shape[0]] += r.audio
    out = []
    for track in sorted({r.clip.track for r in vocals}):
        vocal = np.zeros((total, 2), dtype=np.float32)
        ids = []
        for r in vocals:
            if r.clip.track == track:
                vocal[r.start_sample: r.start_sample + r.audio.shape[0]] += r.audio
                ids.append(r.clip.id)
        measured = _balance_lu(vocal[lo:hi], rest[lo:hi])
        if measured is not None:
            out.append({"track": track, "clips": ids, "mix_lu": measured[0], "record_lu": record_balance(track),
                        "active_s": measured[1]})
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


def _reference(master_spec: dict[str, Any]) -> dict[str, Any] | None:
    ref = master_spec.get("reference")
    if not ref:
        return None
    return {"track": ref} if isinstance(ref, str) else dict(ref)


def reference_match(mix: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Matchering: match the mix's tonal balance, loudness, and width to a released master (no limiting here;
    our true-peak limiter runs after)."""
    import contextlib
    import io

    import matchering as mg

    with tempfile.TemporaryDirectory(prefix="gh-ref-") as tmp:
        tmp_dir = Path(tmp)
        sf.write(tmp_dir / "target.wav", mix, A.SR, subtype="FLOAT")
        sf.write(tmp_dir / "reference.wav", reference, A.SR, subtype="FLOAT")
        with contextlib.redirect_stdout(io.StringIO()):
            mg.process(target=str(tmp_dir / "target.wav"), reference=str(tmp_dir / "reference.wav"),
                       results=[mg.Result(str(tmp_dir / "out.wav"), subtype="FLOAT", use_limiter=False,
                                          normalize=False)])
        out, _ = sf.read(tmp_dir / "out.wav", dtype="float32", always_2d=True)
    return _fit_length(out, mix.shape[0])


def mono_bass(mix: np.ndarray, cutoff: float = 120.0) -> np.ndarray:
    """Keep everything below ``cutoff`` in mono (club systems sum the low end)."""
    from scipy.signal import butter, sosfiltfilt

    mid = (mix[:, 0] + mix[:, 1]) / 2
    side = (mix[:, 0] - mix[:, 1]) / 2
    side = sosfiltfilt(butter(4, cutoff, btype="highpass", fs=A.SR, output="sos"), side)
    return np.stack([mid + side, mid - side], axis=1).astype(np.float32)


def soft_clipper(mix: np.ndarray, threshold_db: float, knee: float = 0.6) -> np.ndarray:
    """Round off peaks above ``knee`` x threshold, approaching the threshold asymptotically (tanh)."""
    c = A.db_to_gain(threshold_db)
    k = knee * c
    x = np.abs(mix)
    over = x > k
    shaped = np.where(over, k + (c - k) * np.tanh((x - k) / (c - k)), x)
    return (np.sign(mix) * shaped).astype(np.float32)


MASTER_CLIP_MODES = ("auto", "low", "full", "off")


def master_clip_mode(value: Any) -> str:
    """``master.soft_clip``: true (or unset) is "auto", false is "off", or name a mode."""
    if value is None or value is True:
        return "auto"
    if value is False:
        return "off"
    return str(value)


def low_band_clip(mix: np.ndarray, *, clip_db: float = 2.0, cutoff: float = 120.0, knee: float = 0.8) -> np.ndarray:
    """Soft-clip only the band below ``cutoff`` (kick and 808 peaks set a master's peak level), ``clip_db`` under its
    loudest peaks. The band split is zero-phase and complementary, so everything above the cutoff passes untouched:
    clipping the full mix instead puts distortion on the vocal and synths (about -20 dB of products in 300 Hz-5 kHz
    on a dense vocal song, against about -40 dB for the low band alone)."""
    from scipy.signal import butter, sosfiltfilt

    low = sosfiltfilt(butter(2, cutoff, btype="lowpass", fs=A.SR, output="sos"), mix, axis=0)
    peak = float(np.percentile(np.abs(low), 99.97))
    if peak <= 0:
        return mix
    return (mix - low + soft_clipper(low, A.gain_to_db(peak) - clip_db, knee=knee)).astype(np.float32)


def _clip_products_db(before: np.ndarray, after: np.ndarray, out: np.ndarray) -> float:
    """Level of what the clipper changed in 300 Hz-5 kHz, relative to the master in that band."""
    from scipy.signal import butter, sosfiltfilt

    sos = butter(2, [300, 5000], btype="bandpass", fs=A.SR, output="sos")
    diff = sosfiltfilt(sos, (after - before).mean(axis=1))
    sig = sosfiltfilt(sos, out.mean(axis=1))
    return round(float(10 * np.log10(np.mean(diff ** 2) / (np.mean(sig ** 2) + 1e-30) + 1e-30)), 1)


def tame_harshness(mix: np.ndarray, *, max_cut_db: float = 3.0) -> np.ndarray:
    """Dynamic cut of 2-5 kHz only in moments where that band jumps above its usual share of the mix
    (vocal + hats piling up), at most ``max_cut_db``."""
    from scipy.signal import butter, sosfiltfilt

    band = sosfiltfilt(butter(2, [2000, 5000], btype="bandpass", fs=A.SR, output="sos"), mix, axis=0).astype(np.float32)
    hop = 1024
    frames = mix.shape[0] // hop
    if frames < 8:
        return mix
    full = np.sqrt(np.mean(A.mono(mix)[: frames * hop].reshape(frames, hop) ** 2, axis=1)) + 1e-9
    part = np.sqrt(np.mean(A.mono(band)[: frames * hop].reshape(frames, hop) ** 2, axis=1)) + 1e-9
    share = 20 * np.log10(part / full)
    loud = full > np.percentile(full, 25)
    typical = float(np.median(share[loud])) if loud.any() else float(np.median(share))
    excess = np.clip(share - (typical + 2.0), 0.0, max_cut_db * 2) / 2
    smooth = np.convolve(excess, np.hanning(9) / np.hanning(9).sum(), mode="same")
    cut_db = np.interp(np.arange(mix.shape[0]), np.arange(frames) * hop + hop / 2, smooth)
    cut = 1 - 10 ** (-np.minimum(cut_db, max_cut_db) / 20)
    return (mix - band * cut[:, None]).astype(np.float32)


def small_speaker_bass(mix: np.ndarray, cutoff: float = 120.0, amount: float = 0.25) -> np.ndarray:
    """Add upper harmonics of the bass (saturation above the bass band) so the bassline reads on phones/laptops."""
    from scipy.signal import butter, sosfiltfilt

    low = sosfiltfilt(butter(4, cutoff, btype="lowpass", fs=A.SR, output="sos"), mix, axis=0)
    peak = float(np.max(np.abs(low))) or 1.0
    harmonics = np.tanh(3.0 * low / peak) * peak
    harmonics = sosfiltfilt(butter(2, [cutoff * 1.5, cutoff * 6], btype="bandpass", fs=A.SR, output="sos"),
                            harmonics, axis=0)
    return (mix + amount * harmonics).astype(np.float32)


def _true_peak_envelope(mix: np.ndarray) -> np.ndarray:
    """Per-sample peak including inter-sample overs (4x oversampling), so the ceiling holds as true peak."""
    from scipy.signal import resample_poly

    over = np.abs(resample_poly(mix, 2, 1, axis=0)).max(axis=1)
    frames = mix.shape[0]
    over = np.pad(over, (0, max(0, frames * 2 - over.size)))[: frames * 2]
    return np.maximum(over.reshape(frames, 2).max(axis=1), np.abs(mix).max(axis=1)) * 1.02  # 2x under-reads ~0.2 dB


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
    from glass_harbor import vocals

    spec = clip.spec
    bpm_out = res.tempo.bpm_at(max(anchor, clip.out_end_beat - 1))
    processed = dry
    tail_beats = clip_tail_beats(clip)
    if tail_beats:
        processed = np.pad(processed, ((0, int(tail_beats * 60.0 / bpm_out * A.SR)), (0, 0)))
    chain = spec.get("chain", vocals.default_chain(clip.stem, True))
    if chain != "none":
        processed = vocals.apply_chain(processed, chain, beat_seconds=60.0 / bpm_out)
    audio = processed * A.db_to_gain(clip.gain_db + loudness_offset_db)
    audio = _apply_mixer(res, clip, audio, start_time)
    return RenderedClip(clip=clip, start_sample=int(round((start_time + timeline_offset) * A.SR)), audio=audio,
                        dry=dry, target_beats=[], source_offset_ms=None, warp_offset_ms=None, warp_jitter_ms=None)


def _generate_from_source(res: Resolution, clip: ResolvedClip, kind: str, seconds: float) -> np.ndarray:
    """Fills built from the song's own audio: snare rolls and crashes from the drum stem, vocal risers and reverse
    swells from a lyric word."""
    from glass_harbor import drums as kit
    from glass_harbor import fx as generators

    source = clip.spec["source"]
    track = res.plan["sources"][source]["track"]
    grid = res.grids[source]
    frames = int(round(seconds * A.SR))
    if kind in ("snare_roll", "crash", "halftime"):
        stem = "drums" if "drums" in library.available_stems(track) else "mix"
        kit_audio = library.load_audio(track, stem)
        if kind == "halftime":
            # A half-time beat played on the record's own kick, snare, and hats (the DnB verse switch).
            found = {"kick": kit.find_kick(kit_audio, grid), "snare": kit.find_snare(kit_audio, grid),
                     "hat": kit.find_hat(kit_audio, grid)}
            hits = {name: _fade(_segment(kit_audio, h.start, h.start + h.length), 0.001, 0.02)
                    for name, h in found.items() if h is not None}
            patterns = {**kit.HALFTIME, **(clip.spec.get("pattern") or {})}
            beat = kit.sequence(hits, patterns, seconds, 60.0 / res.tempo.bpm_at(clip.anchor_beat),
                                gains_db={"hat": -6.0})
            # It stands in for the bed's drum clips, so it gets the same loudness matching they do.
            track_lufs = float(res.analyses[track].get("loudness_lufs", A.REFERENCE_LUFS))
            if (res.plan.get("master") or {}).get("match_loudness", True) and math.isfinite(track_lufs):
                beat = beat * A.db_to_gain(float(np.clip(A.REFERENCE_LUFS - track_lufs, -LOUDNESS_MATCH_LIMIT_DB,
                                                         LOUDNESS_MATCH_LIMIT_DB)))
            return beat
        if kind == "snare_roll":
            hit = kit.find_snare(kit_audio, grid)
            if hit is None:
                snare = generators.impact(0.2) * 0.4
            else:
                snare = _segment(kit_audio, hit.start, hit.start + hit.length)
                snare = _fade(snare, 0.001, 0.03)
            return kit.snare_roll(snare, seconds, 60.0 / res.tempo.bpm_at(clip.anchor_beat))
        hit = kit.find_crash(kit_audio, grid)
        crash = kit.synth_crash() if hit is None else _fade(_segment(kit_audio, hit.start, hit.start + 2.5), 0.001, 0.8)
        return _fit_length(crash, frames)
    from glass_harbor.lyrics import find_word, load_lyrics

    word = find_word(load_lyrics(track), str(clip.spec["word"]), int(clip.spec.get("occurrence", 1)))
    vocal = library.load_audio(track, "vocals")
    piece = _fade(_segment(vocal, max(0.0, word["start"] - 0.01), word["end"] + 0.06), 0.003, 0.02)
    if kind == "vocal_riser":
        return generators.vocal_riser(piece, seconds)
    return generators.reverse_swell(piece, seconds)


def render_generated(res: Resolution, clip: ResolvedClip, timeline_offset: float) -> RenderedClip:
    from glass_harbor import fx as generators

    start_time = res.tempo.time_at(clip.anchor_beat)
    seconds = res.tempo.time_at(clip.anchor_beat + clip.out_beats) - start_time
    kind = clip.spec["generate"]
    if kind in generators.SOURCE_TYPES:
        dry = _generate_from_source(res, clip, kind, seconds)
    else:
        dry = generators.generate(kind, seconds)
    audio = dry * A.db_to_gain(clip.gain_db)
    tail_beats = clip_tail_beats(clip)
    if tail_beats:
        audio = np.pad(audio, ((0, int(tail_beats * 60.0 / res.tempo.bpm_at(clip.out_end_beat - 1) * A.SR)), (0, 0)))
    audio = _apply_mixer(res, clip, audio, start_time)
    return RenderedClip(clip=clip, start_sample=int(round((start_time + timeline_offset) * A.SR)), audio=audio,
                        dry=dry, target_beats=[], source_offset_ms=None, warp_offset_ms=None, warp_jitter_ms=None)


def master(mix: np.ndarray, *, lufs: float, ceiling_db: float, soft_clip: bool | str = True,
           max_limiting_db: float = MAX_LIMITING_DB) -> tuple[np.ndarray, dict[str, Any]]:
    """Gain to the loudness target through the clipper and limiter, but never squash more than ``max_limiting_db``.
    ``soft_clip``: "low" clips the low band only; "full" clips the whole mix; "off" skips clipping; "auto" (true, the
    default) clips the low band and falls back to "full" only when the target is otherwise out of reach."""
    mode = master_clip_mode(soft_clip)
    if mode == "auto":
        out, stats = _master(mix, lufs=lufs, ceiling_db=ceiling_db, mode="low", max_limiting_db=max_limiting_db)
        if stats.get("output_lufs", lufs) >= lufs - 1.0:
            return out, stats
        full_out, full_stats = _master(mix, lufs=lufs, ceiling_db=ceiling_db, mode="full", max_limiting_db=max_limiting_db)
        full_stats["clip_fallback"] = (f"low-band clipping reached {stats['output_lufs']} LUFS against a {lufs} target; "
                                       "clipped the full mix instead")
        return full_out, full_stats
    return _master(mix, lufs=lufs, ceiling_db=ceiling_db, mode=mode, max_limiting_db=max_limiting_db)


def _master(mix: np.ndarray, *, lufs: float, ceiling_db: float, mode: str,
            max_limiting_db: float) -> tuple[np.ndarray, dict[str, Any]]:
    measured = A.integrated_lufs(mix)
    if not math.isfinite(measured):
        return mix, {"input_lufs": measured, "output_lufs": measured, "gain_db": 0.0}
    gain_db = lufs - measured
    out = mix

    def clip(staged: np.ndarray) -> np.ndarray:
        if mode == "low":
            return low_band_clip(staged)
        if mode == "full":  # about 1-2 dB off the sharpest transients of the whole mix
            return soft_clipper(staged, ceiling_db + 2.0)
        return staged

    def chain(gain: float) -> np.ndarray:
        return limit(clip(mix * A.db_to_gain(gain)), ceiling_db - 0.2)

    for _ in range(5):
        out = chain(gain_db)
        achieved = A.integrated_lufs(out)
        reduction = gain_db - (achieved - measured)
        if reduction > max_limiting_db:
            gain_db -= reduction - max_limiting_db
            out = chain(gain_db)
            break
        if abs(achieved - lufs) < 0.2:
            break
        gain_db += lufs - achieved
    peak = A.true_peak_db(out)
    if peak > ceiling_db:
        out = out * A.db_to_gain(ceiling_db - peak)
    out = np.clip(out, -1.0, 1.0).astype(np.float32)
    stats: dict[str, Any] = {"input_lufs": round(measured, 2), "gain_db": round(gain_db, 2),
                             "output_lufs": round(A.integrated_lufs(out), 2), "true_peak_db": round(A.true_peak_db(out), 2),
                             "limiting_db": round(gain_db - (A.integrated_lufs(out) - measured), 2), "clip": mode}
    if mode != "off":
        staged = mix * A.db_to_gain(gain_db)
        stats["clip_products_db"] = _clip_products_db(staged, clip(staged), out)
    return out, stats


def _half_beat_samples(res: Resolution, clip: ResolvedClip, timeline_offset: float) -> list[tuple[int, int]]:
    """Output sample windows of each half beat of a clip's source beats (one loop)."""
    from glass_harbor.bassline import half_beats

    beats = [clip.out_start_beat + i * clip.out_beats_per_src_beat for i in range(clip.src_beats + 1)]
    times = [res.tempo.time_at(b) + timeline_offset for b in beats]
    return [(int(round(a * A.SR)), int(round(b * A.SR))) for a, b in half_beats(times)]


def follow_roots(res: Resolution, rendered: list[RenderedClip], timeline_offset: float, log: Log) -> None:
    """Bass stem clips with ``follow_roots`` play, under each vocal, the root notes that vocal was written over
    (read from the vocal track's own bass), in their own rhythm. See ``bassline.py``."""
    from glass_harbor import bassline

    vocal_clips = {r.clip.id: r for r in rendered if r.clip.stem == "vocals" and r.clip.chop is None
                   and r.clip.loop == 1}
    sources: dict[str, tuple[np.ndarray, str]] = {}
    for r in rendered:
        wanted = r.clip.spec.get("follow_roots")
        if r.clip.stem != "bass" or not wanted:
            continue
        targets = list(vocal_clips.values()) if wanted is True else [vocal_clips[i] for i in wanted if i in vocal_clips]
        spans, described = [], {}
        end = r.start_sample + r.audio.shape[0]
        for v in targets:
            windows = _half_beat_samples(res, v.clip, timeline_offset)
            if windows[-1][1] <= r.start_sample or windows[0][0] >= end:
                continue
            if v.clip.track not in sources:
                sources[v.clip.track] = bassline.source_bass(v.clip.track)
            audio, stem = sources[v.clip.track]
            notes = bassline.vocal_roots(v.clip, audio)
            spans.append(bassline.Span([(a - r.start_sample, b - r.start_sample) for a, b in windows], notes))
            described[v.clip.id] = f"{bassline.describe(notes)} (from {v.clip.track}/{stem})"
        if spans:
            r.audio = bassline.follow(r.audio, spans)
            r.notes = {**(r.notes or {}), "followed_roots": described}
            log(f"{r.clip.id} follows the vocal's chords under {', '.join(described)}")


def bass_clash(res: Resolution, rendered: list[RenderedClip], vocal_midi: np.ndarray, bass_bus: np.ndarray,
               timeline_offset: float) -> list[dict[str, Any]]:
    """Per vocal clip: share of sung frames a flat ninth or tritone above the bass note under them."""
    from glass_harbor import bassline

    clips = [r for r in rendered if r.clip.stem == "vocals" and r.clip.chop is None and r.clip.loop == 1]
    per_clip = [[(a / A.SR, b / A.SR) for a, b in _half_beat_samples(res, r.clip, timeline_offset)] for r in clips]
    flat = [w for windows in per_clip for w in windows]
    if not flat or not np.any(bass_bus):
        return []
    notes = bassline.roots(bass_bus, flat)
    out, i = [], 0
    for r, windows in zip(clips, per_clip):
        rate, frames = bassline.clash_rate(bassline.pitch_classes(vocal_midi, windows), notes[i:i + len(windows)])
        i += len(windows)
        if frames:
            out.append({"clip": r.clip.id, "pct": round(100 * rate, 1), "sung_frames": frames})
    return out


def render_plan(plan: dict[str, Any], out_dir: Path, *, start_bar: float | None = None,
                end_bar: float | None = None, write_clips: bool = False, mp3: bool = True,
                log: Log = print, workers: int = 4, use_cache: bool = True) -> dict[str, Any]:
    res = resolve(plan)
    if not res.ok:
        errors = "\n".join(f"- {i.where}: {i.message}" for i in res.issues if i.level == "error")
        raise ValueError(f"Plan has errors:\n{errors}")
    bpb = res.beats_per_bar
    clips = res.clips
    if start_bar is not None or end_bar is not None:
        lo = ((start_bar or 1) - 1) * bpb
        hi = (end_bar * bpb) if end_bar is not None else math.inf
        # A clip that ends just before the window can still ring into it (reverb, echo, delay throws).
        clips = [c for c in clips if c.out_end_beat + clip_tail_beats(c) > lo and c.out_start_beat < hi]
        if not clips:
            raise ValueError("No clips intersect the requested bar range.")

    master_spec = plan.get("master") or {}
    match_loudness = master_spec.get("match_loudness", True)
    earliest = min(res.tempo.time_at(c.out_start_beat) for c in clips)
    timeline_offset = max(0.0, -earliest)

    cache: dict[tuple[str, str], np.ndarray] = {}
    lyrics_cache: dict[str, Any] = {}
    from concurrent.futures import ThreadPoolExecutor

    from glass_harbor.lyrics import load_lyrics

    def offset_for(clip: ResolvedClip) -> float:
        if not match_loudness or not clip.track:
            return 0.0
        track_lufs = float(res.analyses[clip.track].get("loudness_lufs", A.REFERENCE_LUFS))
        if not math.isfinite(track_lufs):
            return 0.0
        return float(np.clip(A.REFERENCE_LUFS - track_lufs, -LOUDNESS_MATCH_LIMIT_DB, LOUDNESS_MATCH_LIMIT_DB))

    # Load shared inputs up front (threads only read them).
    for clip in clips:
        if clip.track and not clip.spec.get("generate") and (clip.track, clip.stem) not in cache:
            cache[(clip.track, clip.stem)] = library.load_audio(clip.track, clip.stem)
        if clip.stem == "vocals" and clip.track not in lyrics_cache:
            lyrics_cache[clip.track] = load_lyrics(clip.track)

    clip_cache = ClipCache(out_dir.parent / ".clip-cache", plan, timeline_offset) if use_cache else None

    def render_one(clip: ResolvedClip) -> RenderedClip:
        if clip_cache is not None:
            hit = clip_cache.load(clip, offset_for(clip))
            if hit is not None:
                log(f"cached {clip.id}")
                return hit
        if clip.spec.get("generate"):
            log(f"rendering {clip.id}: generated {clip.spec['generate']} -> bars {clip.spec['at_bar']}+{clip.spec['bars']}")
            result = render_generated(res, clip, timeline_offset)
        elif clip.chop is not None:
            log(f"rendering {clip.id}: {len(clip.chop['slices'])} chop slices from {clip.track}/{clip.stem}"
                f" -> bars {clip.spec['at_bar']}+{clip.spec['bars']}")
            result = render_chop(res, clip, cache[(clip.track, clip.stem)], offset_for(clip), timeline_offset)
        else:
            log(f"rendering {clip.id}: {clip.track}/{clip.stem} bars {clip.spec['from_bar']}+{clip.spec['bars']}"
                f" -> bar {clip.spec['at_bar']} ({clip.stretch_pct:+.1f}% stretch, {clip.semitones:+d} st)")
            lyrics = lyrics_cache.get(clip.track) if clip.stem == "vocals" else None
            result = render_clip(res, clip, cache[(clip.track, clip.stem)], offset_for(clip), timeline_offset,
                                 lyrics)
        if clip_cache is not None:
            clip_cache.store(clip, offset_for(clip), result)
        return result

    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(clips)))) as pool:
        rendered = list(pool.map(render_one, clips))

    follow_roots(res, rendered, timeline_offset, log)
    # Chord-aware pitch correction needs the beat under each vocal, so it runs once every clip exists.
    total_frames = max(r.start_sample + r.audio.shape[0] for r in rendered)
    bed_sum = np.zeros((total_frames, 2), dtype=np.float32)
    for r in rendered:
        if r.clip.stem not in ("vocals", "fx"):
            bed_sum[r.start_sample: r.start_sample + r.audio.shape[0]] += r.audio
    # Sung hooks only by default: retuning short rap syllables sounds worse than the rub it fixes.
    harmonize_targets = [r for r in rendered if r.clip.stem == "vocals" and r.clip.chop is None
                         and r.clip.spec.get("harmonize", r.clip.spec.get("chain") == "hook")]

    def harmonize_one(r: RenderedClip) -> None:
        from glass_harbor.harmony import harmonize

        segment = bed_sum[r.start_sample: r.start_sample + r.audio.shape[0]]
        r.audio, fixes = harmonize(r.audio, segment)
        if fixes:
            r.notes = {**(r.notes or {}), "harmonized": fixes}
            log(f"harmonized {len(fixes)} held note(s) in {r.clip.id}")

    if np.any(bed_sum) and harmonize_targets:
        with ThreadPoolExecutor(max_workers=max(1, min(workers, len(harmonize_targets)))) as pool:
            list(pool.map(harmonize_one, harmonize_targets))

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
    crop_start, crop_end = 0, total
    if start_bar is not None or end_bar is not None:
        lo_t = res.tempo.time_at(((start_bar or 1) - 1) * bpb) + timeline_offset
        crop_start = max(0, int(round(lo_t * A.SR)))
        crop_end = total if end_bar is None else min(total, int(round(
            (res.tempo.time_at(end_bar * bpb) + timeline_offset) * A.SR)))
    presence = vocal_presence(rendered, total, bar_spans)
    balance = vocal_balance(rendered, total, keep=(crop_start, crop_end))
    vocal_sum = np.zeros((total, 2), dtype=np.float32)
    for r in rendered:
        if r.clip.stem == "vocals" and r.clip.chop is None:
            vocal_sum[r.start_sample: r.start_sample + r.audio.shape[0]] += r.audio
    pitch_clash, vs_bass = [], []
    if np.any(vocal_sum):
        from glass_harbor.harmony import _pitch_track, clash_by_bar

        bed_full = bed_sum[:total] if bed_sum.shape[0] >= total else np.pad(bed_sum, ((0, total - bed_sum.shape[0]),
                                                                                      (0, 0)))
        vocal_midi = _pitch_track(vocal_sum)
        pitch_clash = clash_by_bar(vocal_sum, bed_full, bar_spans, midi=vocal_midi)
        bass_bus = np.zeros((total, 2), dtype=np.float32)
        for r in rendered:
            if r.clip.stem == "bass":
                bass_bus[r.start_sample: r.start_sample + r.audio.shape[0]] += r.audio[: total - r.start_sample]
        vs_bass = bass_clash(res, rendered, vocal_midi, bass_bus if np.any(bass_bus) else bed_full, timeline_offset)
    for edit in plan.get("edits", []):
        if edit.get("type") == "tape_stop":
            from glass_harbor.fx import tape_stop

            a = int(round((res.tempo.time_at((edit["at_bar"] - 1) * bpb) + timeline_offset) * A.SR))
            b = int(round((res.tempo.time_at((edit["at_bar"] - 1) * bpb + edit["beats"]) + timeline_offset) * A.SR))
            if 0 <= a < b <= mix.shape[0]:
                mix[a:b] = tape_stop(mix[a:b])
    if master_spec.get("glue", True):
        mix = glue(mix)
    reference = _reference(master_spec)
    if reference is not None:
        log(f"matching tone to reference {reference['track']}")
        mix = reference_match(mix, library.load_audio(reference["track"], reference.get("stem", "mix")))
    mono_hz = float(master_spec.get("mono_bass_hz", 120))
    if mono_hz:
        mix = mono_bass(mix, mono_hz)
    if master_spec.get("tame_harshness", True):
        mix = tame_harshness(mix)

    if start_bar is not None or end_bar is not None:
        mix = mix[crop_start:crop_end]
    premaster = mix

    target_lufs = master_spec.get("lufs")
    if target_lufs is None:
        ref_analysis = (res.analyses.get(reference["track"]) or library.load_analysis(reference["track"])) if reference else {}
        target_lufs = ref_analysis.get("loudness_lufs", -9.0) if reference else -9.0
        target_lufs = float(np.clip(target_lufs, -14.0, LOUDEST_TARGET_LUFS))
    mastered, master_stats = master(mix, lufs=float(target_lufs), ceiling_db=float(master_spec.get("ceiling_db", -1.0)),
                                    soft_clip=master_spec.get("soft_clip", True))
    master_stats["target_lufs"] = round(float(target_lufs), 2)
    if reference is not None:
        master_stats["reference"] = reference["track"]

    out_dir.mkdir(parents=True, exist_ok=True)
    wav_path = A.save(out_dir / "mix.wav", mastered, subtype="PCM_24")
    mp3_path = A.encode_mp3(wav_path, out_dir / "mix.mp3") if mp3 else None
    stream_stats = None
    if master_spec.get("stream_version", True):
        # Streaming/phone master: -14 LUFS (what Spotify/YouTube normalize to), bass harmonics for small speakers.
        streamed, stream_stats = master(small_speaker_bass(premaster), lufs=-14.0, ceiling_db=-1.0, soft_clip=False)
        stream_wav = A.save(out_dir / "mix-stream.wav", streamed, subtype="PCM_24")
        if mp3:
            A.encode_mp3(stream_wav, out_dir / "mix-stream.mp3")
    phone_stats, phone_file = None, None
    stale = out_dir / "mix-phone.m4a"
    if stale.exists():
        stale.unlink()
    if master_spec.get("phone_version", True):
        # For sending to a phone: about as loud as a release (phones play files as they are), with bass harmonics
        # so small speakers still carry the bassline, as AAC (native on iPhone and Android, smaller than the MP3).
        phone, phone_stats = master(small_speaker_bass(premaster), lufs=min(float(target_lufs), PHONE_LUFS),
                                    ceiling_db=-1.0, soft_clip=True)
        phone_wav = A.save(out_dir / "mix-phone.wav", phone, subtype="PCM_16")
        encoded = A.encode_m4a(phone_wav, out_dir / "mix-phone.m4a", title=str(plan.get("title", "")))
        if encoded:
            phone_wav.unlink()
        phone_file = (encoded or phone_wav).name
    short_file, short_edit = None, None
    for stale_short in (out_dir / "mix-short.m4a", out_dir / "mix-short.wav"):
        stale_short.unlink(missing_ok=True)
    from glass_harbor.feedback import taste_default

    seconds = master_spec.get("short_seconds", taste_default("short_edit_seconds"))
    if phone_stats is not None and start_bar is None and end_bar is None and seconds:
        # A short edit of the phone master (the full render stays the version QA judges).
        from glass_harbor.edit import plan_short_edit, splice

        short_edit = plan_short_edit(plan, res, target_s=float(seconds))
        if short_edit:
            short_wav = A.save(out_dir / "mix-short.wav", splice(phone, short_edit, res, timeline_offset),
                               subtype="PCM_16")
            encoded = A.encode_m4a(short_wav, out_dir / "mix-short.m4a",
                                   title=f"{plan.get('title', '')} (short edit)".strip())
            if encoded:
                short_wav.unlink()
            short_file = (encoded or short_wav).name
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
        "files": {"wav": wav_path.name, "mp3": mp3_path.name if mp3_path else None,
                  "phone": phone_file, "short": short_file},
        "short_edit": short_edit,
        "master": master_stats,
        "stream_master": stream_stats,
        "phone_master": phone_stats,
        "issues": [i.to_dict() for i in res.issues],
        "vocal_presence": presence,
        "vocal_balance": balance,
        "pitch_clash": pitch_clash,
        "bass_clash": vs_bass,
        "clips": [
            {
                "id": r.clip.id,
                "track": r.clip.track,
                "stem": r.clip.stem,
                "start_s": round(r.start_sample / A.SR - crop_start / A.SR, 4),
                "length_s": round(r.dry_frames / A.SR, 4),
                "stretch_pct": round(r.clip.stretch_pct, 2),
                "semitones": r.clip.semitones,
                "source_grid_offset_ms": None if r.source_offset_ms is None else round(r.source_offset_ms, 1),
                "warp_offset_ms": None if r.warp_offset_ms is None else round(r.warp_offset_ms, 1),
                "warp_jitter_ms": None if r.warp_jitter_ms is None else round(r.warp_jitter_ms, 1),
                **({"notes": {k: v for k, v in r.notes.items() if not k.startswith("_")}}
                   if r.notes and any(not k.startswith("_") for k in r.notes) else {}),
            }
            for r in rendered
        ],
    }
    (out_dir / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    (out_dir / "render.json").write_text(json.dumps(report, indent=2) + "\n")
    return report
