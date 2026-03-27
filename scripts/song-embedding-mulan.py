#!/usr/bin/env python3

import json
import os
import sys


def main():
    request = json.load(sys.stdin)
    provider = (request.get("provider") or "mulan").strip().lower()
    if provider != "mulan":
        json.dump(
            {
                "provider": provider,
                "status": "unavailable",
                "summary": f'Unsupported embedding provider "{provider}".',
                "confidence_notes": ["Only the mulan adapter is defined in-repo."],
            },
            sys.stdout,
        )
        return

    model_path = (os.environ.get("GLASS_HARBOR_MULAN_MODEL_PATH") or "").strip()
    try:
        import tensorflow  # noqa: F401
        import tensorflow_hub  # noqa: F401
    except Exception as error:  # pragma: no cover - env dependent
        json.dump(
            {
                "provider": "mulan",
                "status": "unavailable",
                "summary": "MuLan dependencies are not installed; falling back to deterministic style scoring.",
                "confidence_notes": [f"tensorflow/tensorflow_hub import failed: {error}"],
            },
            sys.stdout,
        )
        return

    if not model_path:
        json.dump(
            {
                "provider": "mulan",
                "status": "unavailable",
                "summary": "MuLan backend requested, but GLASS_HARBOR_MULAN_MODEL_PATH is not configured.",
                "confidence_notes": ["No local MuLan model path is configured."],
            },
            sys.stdout,
        )
        return

    json.dump(
        {
            "provider": "mulan",
            "status": "unavailable",
            "summary": "MuLan runtime dependencies were found, but the local model bridge is not yet configured in-repo.",
            "confidence_notes": [
                f"Model path configured at {model_path}.",
                "The repo will continue with deterministic MIR-only style scoring until a MuLan model bridge is wired.",
            ],
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
