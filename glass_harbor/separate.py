"""Local stem separation with python-audio-separator (free, runs on the machine).

Quality profiles:
- ``balanced`` (default): unwa's "Resurrection" BS-RoFormer models (the strongest members of the community
  ensembles): one pass for vocals, one for the instrumental, then HT-Demucs (fine-tuned) on the instrumental for
  drums/bass/other. About 4 minutes per pass for a 4-minute song on an M1 Pro.
- ``best``: the community-recommended two-model RoFormer ensembles (deton24 guide presets bundled with
  audio-separator) for vocals and instrumental. Roughly 2.5x slower; use for final acapellas.
- ``fast``: a single HT-Demucs pass for all four stems; instrumental = drums + bass + other.
"""

from __future__ import annotations

import re
import tempfile
import warnings
from pathlib import Path
from typing import Callable

from glass_harbor import audio as A
from glass_harbor import library
from glass_harbor.paths import model_dir

PROFILES = {
    "balanced": {
        "vocals": {"model": "bs_roformer_vocals_resurrection_unwa.ckpt"},
        "instrumental": {"model": "bs_roformer_instrumental_resurrection_unwa.ckpt"},
        "four_stem": {"model": "htdemucs_ft.yaml"},
    },
    "best": {
        "vocals": {"ensemble_preset": "vocal_balanced"},
        "instrumental": {"ensemble_preset": "instrumental_clean"},
        "four_stem": {"model": "htdemucs_ft.yaml"},
    },
    "fast": {"all": {"model": "htdemucs.yaml"}},
}

CLEAN_MODELS = {
    "dereverb": "dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt",
    "dereverb-gentle": "dereverb_mel_band_roformer_less_aggressive_anvuew_sdr_18.8050.ckpt",
    "deecho": "dereverb-echo_mel_band_roformer_sdr_13.4843_v2.ckpt",
    "denoise": "denoise_mel_band_roformer_aufr33_sdr_27.9959.ckpt",
    # Lead vs backing vocals: drops harmonies, ad-lib stacks, and vocal samples that were tuned to the original
    # beat's chords (they are what makes an acapella sound off pitch over a new beat).
    "lead": "mel_band_roformer_karaoke_becruily.ckpt",
}
_MODE_LABELS = {"lead": ("vocals",)}
_CLEAN_LABELS = ("noreverb", "no reverb", "dry", "no echo", "no noise")

_LABELS = {
    "vocals": "vocals",
    "vocal": "vocals",
    "instrumental": "instrumental",
    "instrum": "instrumental",
    "no vocals": "instrumental",
    "other": "other",
    "drums": "drums",
    "bass": "bass",
}

Log = Callable[[str], None]


def _label_of(filename: str) -> str | None:
    lowered = filename.lower()
    for match in re.findall(r"\(([^)]+)\)", lowered)[::-1]:
        if match.strip() in _LABELS:
            return _LABELS[match.strip()]
    for token, label in sorted(_LABELS.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"(^|[_\-\s.]){re.escape(token)}([_\-\s.]|$)", lowered):
            return label
    return None


def _two_stem(outputs: dict[str, Path]) -> dict[str, Path]:
    """Vocal/instrumental models often name the non-vocal output "other"; that stem is the instrumental."""
    if "instrumental" not in outputs and "other" in outputs:
        outputs = {**outputs, "instrumental": outputs["other"]}
    return outputs


MPS_BUDGET_ENV = "AUDIO_SEPARATOR_MPS_BUFFER_BUDGET_GIB"
MPS_RETRY_BUDGET_GIB = "6"


def _free_mps() -> None:
    try:
        import torch

        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
    except Exception:  # noqa: BLE001 - cache release is best effort
        pass


def _separate_once(source: Path, out_dir: Path, model: str | None, ensemble_preset: str | None, *,
                   cpu: bool = False) -> list[str]:
    if cpu:
        # audio-separator picks MPS whenever it is available; hide it so this one pass runs on the CPU.
        from unittest import mock

        with mock.patch("torch.backends.mps.is_available", return_value=False):
            return _separate_once(source, out_dir, model, ensemble_preset)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from audio_separator.separator import Separator

        model_dir().mkdir(parents=True, exist_ok=True)
        separator = Separator(
            log_level=30,
            model_file_dir=str(model_dir()),
            output_dir=str(out_dir),
            output_format="FLAC",
            ensemble_preset=ensemble_preset,
        )
        if ensemble_preset:
            separator.load_model()
        else:
            separator.load_model(model_filename=model)
        return separator.separate(str(source))


def _run_audio_separator(source: Path, out_dir: Path, *, model: str | None = None,
                         ensemble_preset: str | None = None) -> dict[str, Path]:
    import os

    # Models from earlier passes in this process hold GPU memory; release it so audio-separator's memory budget
    # (measured against what is free) does not shrink pass after pass.
    _free_mps()
    try:
        outputs = _separate_once(source, out_dir, model, ensemble_preset)
    except RuntimeError as error:
        # When MPS looks short on memory, audio-separator keeps long-track Demucs buffers on the CPU while the model
        # runs on MPS, and that path mixes devices. Retry with the buffers kept on MPS.
        if "same device" not in str(error) or os.environ.get(MPS_BUDGET_ENV):
            raise
        _free_mps()
        os.environ[MPS_BUDGET_ENV] = MPS_RETRY_BUDGET_GIB
        try:
            outputs = _separate_once(source, out_dir, model, ensemble_preset)
        except RuntimeError as again:
            # Demucs can also mix devices inside its own forward pass on some inputs; the CPU always works.
            if "same device" not in str(again):
                raise
            _free_mps()
            outputs = _separate_once(source, out_dir, model, ensemble_preset, cpu=True)
        finally:
            del os.environ[MPS_BUDGET_ENV]
    found: dict[str, Path] = {}
    for name in outputs:
        path = Path(name) if Path(name).is_absolute() else out_dir / name
        label = _label_of(path.name)
        if label and label not in found:
            found[label] = path
    return found


def _separate_fast(track_id: str, wanted: set[str], tmp_dir: Path, log: Log) -> dict[str, dict]:
    spec = PROFILES["fast"]["all"]
    log(f"separating all stems with {spec}")
    outputs = _run_audio_separator(library.audio_path(track_id), tmp_dir / "fast", **spec)
    produced: dict[str, dict] = {}
    for name in ("vocals", "drums", "bass", "other"):
        if name in wanted:  # never overwrite stems the caller did not ask for (e.g. a cleaned acapella)
            library.copy_stem_file(track_id, name, outputs[name])
            produced[name] = {"quality": "fast", **spec}
    if "instrumental" in wanted:
        parts = [A.load(outputs[name]) for name in ("drums", "bass", "other")]
        frames = min(part.shape[0] for part in parts)
        library.copy_stem_file(track_id, "instrumental", outputs["drums"])  # resets raw/cleaned state
        A.save(library.stem_path(track_id, "instrumental"), sum(part[:frames] for part in parts), subtype="PCM_24")
        produced["instrumental"] = {"quality": "fast", "derived": "drums + bass + other", **spec}
    return produced


def separate_local(track_id: str, wanted: set[str], quality: str, log: Log) -> dict[str, dict]:
    produced: dict[str, dict] = {}
    with tempfile.TemporaryDirectory(prefix="gh-sep-") as tmp:
        tmp_dir = Path(tmp)
        if quality == "fast":
            return _separate_fast(track_id, wanted, tmp_dir, log)
        profile = PROFILES[quality]
        source = library.audio_path(track_id)
        need_instrumental = bool(wanted & {"instrumental", "drums", "bass", "other"})

        if "vocals" in wanted:
            spec = profile["vocals"]
            log(f"separating vocals with {spec}")
            outputs = _two_stem(_run_audio_separator(source, tmp_dir / "vocals", **spec))
            library.copy_stem_file(track_id, "vocals", outputs["vocals"])
            produced["vocals"] = {"quality": quality, **spec}
            if spec == profile["instrumental"] and "instrumental" in outputs and need_instrumental:
                library.copy_stem_file(track_id, "instrumental", outputs["instrumental"])
                produced["instrumental"] = {"quality": quality, **spec}

        reuse = library.stem_path(track_id, "instrumental").exists() and "instrumental" not in wanted
        if need_instrumental and "instrumental" not in produced and not reuse:
            spec = profile["instrumental"]
            log(f"separating instrumental with {spec}")
            outputs = _two_stem(_run_audio_separator(source, tmp_dir / "instrumental", **spec))
            library.copy_stem_file(track_id, "instrumental", outputs["instrumental"])
            produced["instrumental"] = {"quality": quality, **spec}
            if "vocals" in outputs and not library.stem_path(track_id, "vocals").exists():
                # Keep the beat's own vocal too: its hook can answer the acapella (call and response).
                library.copy_stem_file(track_id, "vocals", outputs["vocals"])
                produced["vocals"] = {"quality": quality, "kept_from": "instrumental pass", **spec}

        four = wanted & {"drums", "bass", "other"}
        if four:
            spec = profile["four_stem"]
            log(f"splitting the instrumental into drums/bass/other with {spec}")
            outputs = _run_audio_separator(library.stem_path(track_id, "instrumental"), tmp_dir / "four", **spec)
            for name in sorted(four):
                library.copy_stem_file(track_id, name, outputs[name])
                produced[name] = {"quality": quality, "input": "instrumental", **spec}
    return produced


def clean_stem(track_id: str, stem: str = "vocals", mode: str = "dereverb", log: Log = print,
               restart: bool = False) -> dict[str, str]:
    """Clean a stem in place: strip reverb/echo/noise, or keep only the lead vocal (``lead``). Steps stack in order
    (e.g. dereverb, then lead); the original separation is kept under stems/raw/ and ``restart`` starts over from it."""
    import shutil

    if mode not in CLEAN_MODELS:
        raise ValueError(f"mode must be one of {', '.join(CLEAN_MODELS)}")
    if mode == "lead" and stem != "vocals":
        raise ValueError("lead cleanup splits a vocal into lead and backing vocals; use it on the vocals stem")
    source = library.stem_path(track_id, stem)
    if not source.exists():
        raise FileNotFoundError(f"{track_id} has no {stem} stem to clean")
    raw = source.parent / "raw" / source.name
    raw.parent.mkdir(parents=True, exist_ok=True)
    if not raw.exists():
        shutil.copyfile(source, raw)
    meta = library.load_meta(track_id)
    info = meta.setdefault("stems", {}).setdefault(stem, {})
    legacy = [info["cleaned"]["mode"]] if info.get("cleaned") else []  # cleaned before steps were recorded
    history = [] if restart else list(info.get("cleaned_steps", legacy))
    if mode in history:
        raise ValueError(f"{mode} was already applied to {track_id}/{stem}; pass --restart to redo from the original")
    model = CLEAN_MODELS[mode]
    log(f"cleaning {track_id}/{stem} with {model}")
    with tempfile.TemporaryDirectory(prefix="gh-clean-") as tmp:
        work = Path(tmp) / "input.flac"
        shutil.copyfile(raw if restart else source, work)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from audio_separator.separator import Separator

            separator = Separator(log_level=30, model_file_dir=str(model_dir()), output_dir=tmp, output_format="FLAC")
            separator.load_model(model_filename=model)
            outputs = [Path(o) if Path(o).is_absolute() else Path(tmp) / o for o in separator.separate(str(work))]
        labels = _MODE_LABELS.get(mode, _CLEAN_LABELS)
        cleaned = next((o for o in outputs if any(f"({label})" in o.name.lower() for label in labels)), None)
        if cleaned is None:
            raise RuntimeError(f"could not find the cleaned output among {[o.name for o in outputs]}")
        if mode == "lead":
            removed = next((o for o in outputs if o != cleaned), None)
            if removed is not None:
                shutil.copyfile(removed, raw.parent / f"{stem}-backing.flac")
        shutil.copyfile(cleaned, source)  # in place; the raw copy and history stay
    history.append(mode)
    info["cleaned_steps"] = history
    info["cleaned"] = {"mode": " + ".join(history), "model": model}
    library.save_meta(track_id, meta)
    return {"stem": stem, "mode": " + ".join(history), "model": model, "raw": str(raw)}


def separate_track(track_id: str, *, stems: list[str] | None = None, quality: str = "balanced",
                   force: bool = False, log: Log = print) -> dict[str, dict]:
    wanted = set(stems or library.STEM_NAMES)
    unknown = wanted - set(library.STEM_NAMES)
    if unknown:
        raise ValueError(f"Unknown stems: {', '.join(sorted(unknown))}")
    if not force:
        wanted -= set(library.available_stems(track_id))
    if not wanted:
        return {}
    if quality not in PROFILES:
        raise ValueError(f"quality must be one of {', '.join(PROFILES)}")
    produced = separate_local(track_id, wanted, quality, log)
    meta = library.load_meta(track_id)
    meta.setdefault("stems", {}).update(produced)
    library.save_meta(track_id, meta)
    return produced
