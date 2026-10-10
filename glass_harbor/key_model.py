"""Key detection with S-KEY (Deezer, ICASSP 2025), vendored under glass_harbor/vendor/skey.

On our test tracks S-KEY found the shared key (G# minor) of a rap acapella and a house instrumental with 0.8-0.9
confidence where chroma-template matching picked neighbouring keys. Falls back to templates when torch/nnAudio
are missing.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import warnings
from functools import lru_cache
from pathlib import Path

import numpy as np

from glass_harbor import audio as A
from glass_harbor.keys import Key, parse_key

CHECKPOINT = Path(__file__).parent / "vendor" / "skey" / "skey.pt"
# Output index -> key, as in upstream key_detection.key_map.
KEY_MAP = [
    "A Major", "Bb Major", "B Major", "C Major", "C# Major", "D Major", "D# Major", "E Major", "F Major",
    "F# Major", "G Major", "G# Major", "B minor", "C minor", "C# minor", "D minor", "D# minor", "E minor",
    "F minor", "F# minor", "G minor", "G# minor", "A minor", "Bb minor",
]


def available() -> bool:
    return all(importlib.util.find_spec(m) for m in ("torch", "torchaudio", "nnAudio", "einops")) and CHECKPOINT.exists()


@lru_cache(maxsize=1)
def _model():
    import torch

    with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):  # nnAudio prints while building
        warnings.simplefilter("ignore")
        from glass_harbor.vendor.skey.chromanet import ChromaNet
        from glass_harbor.vendor.skey.hcqt import VQT, CropCQT

        ckpt = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
        hcqt = VQT(harmonics=[1], fmin=27.5, n_bins=99)
        net = ChromaNet(n_bins=84, n_harmonics=1, out_channels=[2, 3, 40, 40, 30, 10, 3],
                        kernels=[7, 7, 7, 7, 7, 5, 5], temperature=1)
        hcqt.load_state_dict({k.replace("hcqt.", ""): v for k, v in ckpt["stone"].items() if "hcqt" in k})
        net.load_state_dict({k.replace("chromanet.", ""): v for k, v in ckpt["stone"].items() if "chromanet" in k})
        hcqt.eval()
        net.eval()
    return hcqt, net, CropCQT(84), int(ckpt["audio"]["sr"])


def estimate_key(audio: np.ndarray) -> tuple[Key, float, list[tuple[str, float]]]:
    """Return (key, probability of that key, top-3 [(name, prob)])."""
    import soxr
    import torch

    hcqt, net, crop, sr = _model()
    signal = soxr.resample(A.mono(audio), A.SR, sr).astype(np.float32)
    peak = float(np.max(np.abs(signal))) if signal.size else 0.0
    if peak <= 0:
        return Key(0, "major"), 0.0, []
    with torch.no_grad(), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        probs = net(crop(hcqt(torch.from_numpy(signal / peak)[None, None]), torch.zeros(1))).mean(0).numpy()
    order = np.argsort(probs)[::-1]
    top = [(parse_key(KEY_MAP[int(i)]).name, round(float(probs[i]), 3)) for i in order[:3]]
    return parse_key(KEY_MAP[int(order[0])]), float(probs[order[0]]), top
