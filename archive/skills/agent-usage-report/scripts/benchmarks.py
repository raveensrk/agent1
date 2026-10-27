"""Artificial Analysis benchmark data.

Fetches the AA Intelligence Index (and any later metrics) from the AA API v2
(``https://artificialanalysis.ai/api/v2/data/llms/models``). Requires a free
API key: set ``aa_api_key`` in config.json or the ``AA_API_KEY`` environment
variable. Responses are cached for 24 hours like models.dev pricing.

Local overrides in ``~/.local/share/agent_report/aa.json`` fix name mismatches
or pin values:

    {"claude-opus-5": {"intelligence_index": 68.4}}
"""

from __future__ import annotations

import gzip
import json
import os
import re
import time
from pathlib import Path

from adapters.util import expand
AA_API = "https://artificialanalysis.ai/api/v2/data/llms/models"
CACHE_TTL = 24 * 3600

_DEFAULT_HOME = Path.home() / ".local" / "share" / "agent_report"


def report_home(config=None):
    override = os.environ.get("AGENT_REPORT_HOME")
    if override:
        return expand(override)
    if config and config.get("home"):
        return expand(config["home"])
    return _DEFAULT_HOME


def normalize(name):
    """Match AA model names ('Claude Opus 5') to log names ('claude-opus-5')."""
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())


def _normalize(name):  # kept for backwards compatibility
    return normalize(name)


def load(config=None, refresh=False, offline=False):
    """Return {model_name: {"intelligence_index": float}} plus a source label."""
    overrides = _load_overrides(config)
    cached = _parse(_load_cache(config))
    fresh = cached is not None and (time.time() - _cache_mtime(config)) < CACHE_TTL
    if (fresh and not refresh) or offline:
        index = {k: v for k, v in (cached or {}).items() if k not in overrides}
        index.update(overrides)
        return index, _source_label("cache" if cached else "none", overrides,
                                    offline=offline)
    key = (config or {}).get("aa_api_key") or os.environ.get("AA_API_KEY")
    fetched = None
    if key and not offline:
        try:
            import urllib.request
            request = urllib.request.Request(
                AA_API,
                headers={"User-Agent": "agent-usage-report", "X-API-Key": key})
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
            fetched = _parse(json.loads(raw.decode("utf-8")))
            if fetched is not None:
                home = report_home(config)
                home.mkdir(parents=True, exist_ok=True)
                with open(home / "aa_models.json", "w", encoding="utf-8") as handle:
                    handle.write(raw.decode("utf-8"))
        except Exception:
            fetched = None

    data, source = (fetched, "artificialanalysis.ai") if fetched is not None \
        else (cached, "cache")
    index = {k: v for k, v in (data or {}).items() if k not in overrides}
    index.update(overrides)
    return index, _source_label(source if data else "none", overrides,
                                no_key=not key and not offline)


def _source_label(source, overrides, offline=False, no_key=False):
    bits = []
    if source == "artificialanalysis.ai":
        bits.append("AA API (live)")
    elif source == "cache":
        bits.append("AA API (cached%s)" % (", stale" if offline else ""))
    elif no_key:
        bits.append("no benchmark data (set aa_api_key in config or AA_API_KEY)")
    else:
        bits.append("no benchmark data")
    if overrides:
        bits.append("aa.json overrides (%d)" % len(overrides))
    return ", ".join(bits)


def _load_overrides(config):
    path = report_home(config) / "aa.json"
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (IOError, ValueError):
        return {}
    return {str(k): {"intelligence_index": float(v["intelligence_index"])}
            for k, v in (raw or {}).items() if isinstance(v, dict)
            and v.get("intelligence_index") is not None}


def _cache_path(config):
    return report_home(config) / "aa_models.json"


def _cache_mtime(config):
    try:
        return _cache_path(config).stat().st_mtime
    except OSError:
        return 0.0


def _load_cache(config):
    try:
        with open(_cache_path(config), "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (IOError, ValueError):
        return None


def _parse(payload):
    """Extract {normalized_name: {"intelligence_index": x}} from the AA reply.

    Field names vary across API versions; match known spellings and fall
    back to any key containing both 'intelligence' and 'index'.
    """
    models = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(models, list):
        return None
    out = {}
    for model in models:
        if not isinstance(model, dict):
            continue
        name = model.get("slug") or model.get("model_name") or model.get("name")
        if not name:
            continue
        pricing = model.get("pricing") or {}
        value = _index_of(model)
        if value is not None:
            out[normalize(name)] = {
                "intelligence_index": value,
                "price": pricing.get("price_1m_blended_3_to_1"),
                "speed": model.get("median_output_tokens_per_second"),
                "name": name,
            }
    return out or None


def _index_of(model):
    for key in ("artificial_analysis_intelligence_index", "intelligence_index",
                "aa_intelligence_index"):
        if model.get(key) is not None:
            return float(model[key])
    evals = model.get("evaluations") or {}
    for key in evals:
        if "intelligence" in key and "index" in key and evals[key] is not None:
            return float(evals[key])
    return None
