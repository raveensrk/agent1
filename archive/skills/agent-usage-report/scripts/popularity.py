"""Market popularity: which models the world actually uses.

Source: OpenRouter Data API ``/datasets/rankings-daily`` (top 50 public
models by daily token usage). Needs a free OpenRouter API key:
``openrouter_api_key`` in config.json or ``OR_API_KEY`` in the environment.
Cached 24 hours like the other catalogs.
"""

from __future__ import annotations

import json
import os
import time

from adapters.util import expand

OR_API = "https://openrouter.ai/api/v1/datasets/rankings-daily"
CACHE_TTL = 24 * 3600

# Flash tier: fast cheap variants. Names carry the hint; plus a cheap+fast
# fallback from AA data for makers that don't name them (Haiku, Nano).
_TIER_WORDS = ("flash", "mini", "lite", "turbo", "nano", "instant", "small",
               "hydro", "light", "sprint")
_FLASH_PRICE = 0.5      # blended $/1M at or below this is cheap
_FLASH_SPEED = 80.0     # median output tokens/sec at or above this is fast


def report_home(config=None):
    override = os.environ.get("AGENT_REPORT_HOME")
    if override:
        return expand(override)
    if config and config.get("home"):
        return expand(config["home"])
    return Path_home()


def Path_home():
    import pathlib
    return pathlib.Path.home() / ".local" / "share" / "agent_report"


def load(config=None, refresh=False, offline=False):
    """Return (rankings, source). rankings = [{slug, tokens, share}, ...]."""
    cached = _load_cache(config)
    fresh = cached is not None and (time.time() - _cache_mtime(config)) < CACHE_TTL
    if (fresh and not refresh) or offline:
        return cached or [], "cache" if cached else "none"

    key = (config or {}).get("openrouter_api_key") or os.environ.get("OR_API_KEY")
    fetched = None
    if key and not offline:
        try:
            import urllib.request
            request = urllib.request.Request(
                OR_API, headers={"User-Agent": "agent-usage-report",
                                 "Authorization": "Bearer %s" % key})
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
            data = json.loads(raw.decode("utf-8")).get("data") or []
            fetched = _parse(data)
            if fetched:
                report_home(config).mkdir(parents=True, exist_ok=True)
                with open(_cache_path(config), "w", encoding="utf-8") as handle:
                    handle.write(json.dumps(fetched))
        except Exception:
            fetched = None

    if fetched:
        return fetched, "openrouter.ai (live)"
    if cached:
        return cached, "openrouter.ai (cached%s)" % (", stale" if offline else "")
    return [], ("no usage data (set openrouter_api_key in config or OR_API_KEY)"
                if not key else "no usage data")


def _parse(rows):
    """[{slug, tokens}] -> {model: share of daily tokens}. rankings-daily
    returns ~30 days; same model appears date-suffixed ('-20260826') and
    multiple times, so group by date-stripped slug and sum tokens."""
    import re
    totals = {}
    display = {}
    for row in rows:
        slug = str(row.get("model_permaslug") or "")
        if not slug or slug == "other":
            continue
        try:
            tokens = float(row.get("total_tokens") or 0)
        except (TypeError, ValueError):
            continue
        base = re.sub(r"-\d{8}$", "", slug)
        totals[base] = totals.get(base, 0.0) + tokens
    entries = [{"slug": slug, "tokens": tokens} for slug, tokens in totals.items()]
    total = sum(e["tokens"] for e in entries) or 1.0
    for entry in entries:
        entry["share"] = entry["tokens"] / total * 100.0
    entries.sort(key=lambda e: -e["tokens"])
    return entries


def cache_path(config=None):
    return _cache_path(config)


def _cache_path(config):
    return report_home(config) / "or_rankings.json"


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


def match_slug(permaslug):
    """'anthropic/claude-opus-5' -> 'claudeopus5' (join key to AA + logs)."""
    tail = permaslug.rsplit("/", 1)[-1]
    return normalize(tail)


def normalize(name):
    import re
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())
