"""Pricing resolution and cost computation.

Cost per model comes from, in order of trust:

1. ``~/.local/share/agent_report/prices.json`` - your overrides.
2. ``~/.pi/agent/models-store.json`` - pi's own per-million rates.
3. models.dev (``https://models.dev/api.json``), cached for 24h.
4. ``assets/prices_snapshot.json`` - a bundled snapshot for offline runs.

Harnesses that record real spend (pi, opencode) keep it; those that do not
(Claude Code, Codex) get a computed estimate. Each model entry tracks how much
of its cost was recorded vs computed so the report can label the difference.
"""

from __future__ import annotations

import gzip
import json
import os
import time
import urllib.request
from pathlib import Path

from adapters.util import expand

import validate

MODELS_DEV = "https://models.dev/api.json"
CACHE_TTL = 24 * 3600

_SNAPSHOT = Path(__file__).resolve().parent.parent / "assets" / "prices_snapshot.json.gz"
_DEFAULT_HOME = Path.home() / ".local" / "share" / "agent_report"

_PROVIDER_ALIASES = {
    "openai-codex": "openai",
    "openai_codex": "openai",
    "codex": "openai",
    "claude": "anthropic",
    "opencode-go": "opencode",
    "opencode_go": "opencode",
    "google-vertex": "google",
}

_KEYS = ("input", "output", "cache_read", "cache_write")


def report_home(config=None):
    override = os.environ.get("AGENT_REPORT_HOME")
    if override:
        return expand(override)
    if config and config.get("home"):
        return expand(config["home"])
    return _DEFAULT_HOME


def _norm(value):
    return str(value or "").lower().replace("_", "-").strip()


def _split(model):
    """Return (provider_hint, model_name) from a possibly namespaced id."""
    text = str(model or "")
    if "/" in text:
        head, _, tail = text.partition("/")
        return _norm(head), _norm(tail)
    return "", _norm(text)


def _clean_cost(cost):
    if not isinstance(cost, dict):
        return None
    out = {}
    for key in _KEYS:
        value = cost.get(key)
        out[key] = float(value) if isinstance(value, (int, float)) else None
    if out["input"] is None and out["output"] is None:
        return None
    if out["cache_read"] is None:
        out["cache_read"] = out["input"]
    if out["cache_write"] is None:
        out["cache_write"] = out["input"]
    return out


class Catalog(object):
    """Lookup of per-million rates keyed by provider and model."""

    def __init__(self):
        self.entries = {}          # "provider/model" -> {cost, context}
        self.by_model = {}         # "model" -> {provider: {cost, context}}
        self.source = "none"

    def add(self, provider, model, cost, context=None):
        clean = _clean_cost(cost)
        if clean is None:
            return
        provider = _PROVIDER_ALIASES.get(_norm(provider), _norm(provider))
        model = _norm(model)
        if not model:
            return
        entry = {"cost": clean, "context": context, "provider": provider, "model": model}
        self.entries["%s/%s" % (provider, model)] = entry
        self.by_model.setdefault(model, {})[provider] = entry
        # Also index by the bare model name so a provider mismatch still hits.
        self.entries.setdefault("%s" % model, entry)

    def resolve(self, provider, model):
        provider_hint, name = _split(model)
        provider = _norm(provider) or provider_hint
        provider = _PROVIDER_ALIASES.get(provider, provider)

        entry = self.entries.get("%s/%s" % (provider, name))
        if entry:
            return entry
        candidates = self.by_model.get(name)
        if not candidates:
            return None
        if provider in candidates:
            return candidates[provider]
        if provider_hint in candidates:
            return candidates[provider_hint]
        # Fall back to the provider models.dev lists for this model.
        return sorted(candidates.values(), key=lambda e: e["provider"])[0]

    def size(self):
        return len(self.by_model)


def _load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (IOError, ValueError):
        return None


def _load_snapshot():
    try:
        with gzip.open(str(_SNAPSHOT), "rt", encoding="utf-8") as handle:
            return json.load(handle)
    except (IOError, ValueError):
        return None


def _load_overrides(config):
    path = report_home(config) / "prices.json"
    return validate.validate_prices(_load_json(path) or {})


def _load_pi_store():
    path = Path.home() / ".pi" / "agent" / "models-store.json"
    return _load_json(path) or {}


def _load_models_dev(config, refresh=False, offline=False):
    home = report_home(config)
    cache = home / "models_dev.json"
    fresh = cache.exists() and (time.time() - cache.stat().st_mtime) < CACHE_TTL
    if (fresh and not refresh) or offline:
        data = _load_json(cache) if cache.exists() else None
        return data, "cache" if data else "none"
    if not offline:
        try:
            request = urllib.request.Request(MODELS_DEV, headers={"User-Agent": "agent-usage-report"})
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
            data = json.loads(raw.decode("utf-8"))
            home.mkdir(parents=True, exist_ok=True)
            with open(cache, "w", encoding="utf-8") as handle:
                handle.write(raw.decode("utf-8"))
            return data, "models.dev"
        except Exception:
            pass
    data = _load_json(cache) if cache.exists() else _load_snapshot()
    return data, "snapshot" if data else "none"


def build_catalog(config=None, refresh=False, offline=False):
    catalog = Catalog()
    sources = []

    overrides = _load_overrides(config)
    for key, cost in overrides.items():
        provider, _, model = key.partition("/")
        if not model:
            model, provider = provider, ""
        catalog.add(provider, model, cost)
    if overrides:
        sources.append("user prices.json")

    pi_store = _load_pi_store()
    pi_count = 0
    for provider, blob in pi_store.items():
        for model in (blob or {}).get("models") or []:
            catalog.add(provider, model.get("id"), model.get("cost"),
                        context=model.get("contextWindow"))
            pi_count += 1
    if pi_count:
        sources.append("pi models-store (%d)" % pi_count)

    dev, dev_source = _load_models_dev(config, refresh=refresh, offline=offline)
    dev_count = 0
    if dev:
        for provider, blob in dev.items():
            for model_id, model in ((blob or {}).get("models") or {}).items():
                cost = model.get("cost") or {}
                context = ((model.get("limit") or {}).get("context"))
                catalog.add(provider, model_id, cost, context=context)
                dev_count += 1
        sources.append("models.dev:%s (%d)" % (dev_source, dev_count))

    catalog.source = ", ".join(sources) if sources else "none"
    return catalog


def compute_cost(entry_tokens, rates):
    """Dollar cost from per-million rates for a token breakdown."""
    if not rates:
        return None
    total = 0.0
    for key in _KEYS:
        amount = float(entry_tokens.get(key) or 0)
        rate = rates.get(key)
        if rate is None:
            rate = rates.get("input")
        if rate is None:
            continue
        total += amount * float(rate) / 1_000_000.0
    return total


def attach(dataset, catalog, minimum_turns=0):
    """Fill cost_computed and blended rates on every model entry."""
    for entry in dataset["models"].values():
        provider = _dominant(entry.get("providers"))
        resolved = catalog.resolve(provider, entry["model"])
        rates = resolved["cost"] if resolved else None
        entry["rates"] = rates
        if rates and not entry.get("context_window"):
            entry["context_window"] = resolved.get("context") or 0

        computed = None
        if rates:
            remaining = {
                "input": entry["input"] - entry.get("input_rec", 0),
                "cache_read": entry["cache_read"] - entry.get("cache_read_rec", 0),
                "cache_write": entry["cache_write"] - entry.get("cache_write_rec", 0),
                "output": entry["output"] - entry.get("output_rec", 0),
            }
            remaining = {k: max(0, v) for k, v in remaining.items()}
            if any(remaining.values()):
                computed = compute_cost(remaining, rates)
        entry["cost_computed"] = computed

        recorded = entry.get("cost_recorded") or 0.0
        entry["cost_total"] = recorded + (computed or 0.0)
        total_tokens = entry["total"] or 0
        entry["cost_per_million"] = (
            round(entry["cost_total"] / total_tokens * 1_000_000, 4) if total_tokens else 0.0
        )
        entry["cost_provenance"] = (
            "recorded" if computed is None and recorded
            else "computed" if not recorded
            else "mixed"
        )
    _sessions_cost(dataset, catalog)
    _ = minimum_turns
    return dataset


def _sessions_cost(dataset, catalog):
    """Cost per session for the drilldown table: recorded dollars if the
    harness logged them, else an estimate from the dominant model's rates.
    The models dict maps model name -> turns, so the dominant key is the
    most-used model's name directly."""
    for sess in dataset.get("sessions_detail") or []:
        resolved = catalog.resolve(_dominant(sess.get("models") or {}),
                                   _dominant(sess.get("models") or {}))
        rates = resolved["cost"] if resolved else None
        recorded = sess.get("cost_recorded") or 0.0
        if recorded:
            sess["cost_total"] = round(recorded, 6)
            sess["cost_provenance"] = "recorded"
        elif rates:
            sess["cost_total"] = round(compute_cost(
                {k: sess.get(k, 0) for k in _KEYS}, rates) or 0.0, 6)
            sess["cost_provenance"] = "computed"
        else:
            sess["cost_total"] = 0.0
            sess["cost_provenance"] = "unknown"


def _dominant(mapping):
    """Key with the highest value; for a models->turns dict this is the
    dominant model name."""
    if not mapping:
        return ""
    if not mapping:
        return ""
    return sorted(mapping.items(), key=lambda item: (-item[1], item[0]))[0][0]
