"""Generic JSONL sniffer for harnesses without a dedicated adapter.

Off by default. Enable by listing roots in the user config:

    {
      "extra_harnesses": [
        {"name": "amp", "label": "Amp", "glob": "~/.amp/**/*.jsonl"}
      ]
    }

For every JSONL line the sniffer walks the parsed object looking for a dict
that carries both an input-ish and an output-ish token key. Field names are
matched case-insensitively against the aliases below, so it covers OpenAI
(``prompt_tokens``/``completion_tokens``), Anthropic and camelCase variants.

It is best-effort: when a field is ambiguous the adapter prefers the
harness's own ``total`` and leaves cost to pricing.py.
"""

from __future__ import annotations

import glob
import json
import os

from .util import expand, make, parse_ts, text_of

NAME = "generic"
LABEL = "Other harnesses"
OPTIONAL = True

_ALIASES = {
    "input": ("input", "input_tokens", "prompt_tokens", "prompttokens", "inputtokens"),
    "output": ("output", "output_tokens", "completion_tokens", "completiontokens", "outputtokens"),
    "cache_read": (
        "cacheread", "cache_read", "cached_input_tokens", "cache_read_input_tokens",
        "cachereadtokens", "cachedtokens",
    ),
    "cache_write": (
        "cachewrite", "cache_write", "cache_creation_input_tokens",
        "cachewriteinputtokens", "cachewritetokens",
    ),
    "reasoning": ("reasoning", "reasoning_tokens", "reasoning_output_tokens", "thinking_tokens"),
    "total": ("total", "total_tokens", "totaltokens"),
}

_CONFIG = []


def configure(config):
    """Receive the parsed user config; pick up ``extra_harnesses``."""
    del _CONFIG[:]
    for entry in (config or {}).get("extra_harnesses") or []:
        glob_pattern = entry.get("glob")
        if not glob_pattern:
            continue
        _CONFIG.append(
            {
                "name": entry.get("name") or "generic",
                "label": entry.get("label") or entry.get("name") or "Other",
                "glob": glob_pattern,
            }
        )


def discover():
    found = []
    for entry in _CONFIG:
        pattern = os.path.expandvars(os.path.expanduser(entry["glob"]))
        found.extend(sorted(glob.glob(pattern, recursive=True)))
    return found


def available():
    return bool(discover())


def records():
    seen = set()
    for entry in _CONFIG:
        pattern = os.path.expandvars(os.path.expanduser(entry["glob"]))
        for path in sorted(glob.glob(pattern, recursive=True)):
            if path in seen or not path.endswith(".jsonl"):
                continue
            seen.add(path)
            for rec in _session(path, entry):
                yield rec


def _lookup(mapping, field):
    lowered = {str(k).lower(): v for k, v in mapping.items()}
    for alias in _ALIASES[field]:
        if alias in lowered:
            return lowered[alias]
    return None


def _find_usage(obj):
    """Depth-first search for the first dict holding input and output tokens."""
    if isinstance(obj, dict):
        if _lookup(obj, "input") is not None and _lookup(obj, "output") is not None:
            return obj
        for value in obj.values():
            found = _find_usage(value)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _find_usage(value)
            if found is not None:
                return found
    return None


def _find_value(obj, keys):
    if isinstance(obj, dict):
        for key in keys:
            if key in obj and isinstance(obj[key], (str, int, float)):
                return obj[key]
        for value in obj.values():
            found = _find_value(value, keys)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _find_value(value, keys)
            if found is not None:
                return found
    return None


def _session(path, entry):
    session_id = os.path.splitext(os.path.basename(path))[0]
    last = None
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if '"' not in line:
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue

            role = _find_value(event, ("role",))
            timestamp = parse_ts(_find_value(event, ("timestamp", "time", "created")))
            model = _find_value(event, ("model", "modelId", "model_id", "modelID")) or "unknown"
            provider = _find_value(event, ("provider", "providerID")) or entry["name"]

            usage = _find_usage(event)
            if usage is not None:
                cache_read = int(_lookup(usage, "cache_read") or 0)
                cache_write = int(_lookup(usage, "cache_write") or 0)
                raw_input = int(_lookup(usage, "input") or 0)
                output = int(_lookup(usage, "output") or 0)
                total = int(_lookup(usage, "total") or 0)
                # OpenAI-style usage folds cached tokens into the input count.
                uncached = max(0, raw_input - cache_read - cache_write)
                if not total:
                    total = raw_input + output
                record = make(
                    kind="assistant", harness=entry["name"], session_id=session_id,
                    timestamp=timestamp, provider=str(provider), model=str(model),
                    input=uncached, cache_read=cache_read, cache_write=cache_write,
                    output=output, reasoning=int(_lookup(usage, "reasoning") or 0),
                    total=total, stop_reason=str(role or "stop"),
                )
                last = record
                yield record
            elif str(role).lower() == "user":
                yield make(
                    kind="user", harness=entry["name"], session_id=session_id,
                    timestamp=timestamp, provider=str(provider), model=str(model),
                    text=text_of(event.get("content") or event.get("text") or ""),
                )
    del last
