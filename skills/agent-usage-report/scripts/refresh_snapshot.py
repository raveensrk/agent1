#!/usr/bin/env python3
"""Regenerate assets/prices_snapshot.json.gz from models.dev.

Run this occasionally so the offline fallback stays current:

    python3 scripts/refresh_snapshot.py

Writes a compact form: provider -> models -> {cost, limit.context}. Everything
else models.dev publishes (names, modalities, release dates) is dropped, which
takes the payload from ~4.9 MB to ~100 KB gzipped.
"""

from __future__ import annotations

import gzip
import json
import sys
import urllib.request
from pathlib import Path

sys.dont_write_bytecode = True

SOURCE = "https://models.dev/api.json"
TARGET = Path(__file__).resolve().parent.parent / "assets" / "prices_snapshot.json.gz"
KEYS = ("input", "output", "cache_read", "cache_write")


def compact(source):
    out = {}
    for provider, blob in source.items():
        models = {}
        for model_id, model in ((blob or {}).get("models") or {}).items():
            cost = model.get("cost") or {}
            if not any(isinstance(cost.get(k), (int, float)) for k in KEYS):
                continue
            entry = {"cost": {k: cost[k] for k in KEYS if isinstance(cost.get(k), (int, float))}}
            context = (model.get("limit") or {}).get("context")
            if context:
                entry["limit"] = {"context": context}
            models[model_id] = entry
        if models:
            out[provider] = {"models": models}
    return out


def main():
    print("fetching %s" % SOURCE)
    request = urllib.request.Request(SOURCE, headers={"User-Agent": "agent-usage-report"})
    with urllib.request.urlopen(request, timeout=60) as response:
        source = json.loads(response.read().decode("utf-8"))
    compacted = compact(source)
    raw = json.dumps(compacted, separators=(",", ":"), sort_keys=True).encode("utf-8")
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(str(TARGET), "wb") as handle:
        handle.write(raw)
    models = sum(len(v["models"]) for v in compacted.values())
    print("wrote %s (%d providers, %d models, %d bytes raw)"
          % (TARGET, len(compacted), models, len(raw)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
