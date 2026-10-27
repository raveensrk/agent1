"""OpenCode Zen / Go cloud adapter.

The local opencode SQLite db only covers sessions stored on this machine;
Zen (pay-as-you-go wallet) and Go (subscription) usage lives server-side in
the opencode console. This adapter fetches the console usage API:

    GET https://opencode.ai/console/api/orgs           (session cookie)
    GET https://opencode.ai/console/api/usage/models   (x-org-id header)

Cookie is read from ``~/.local/share/opencode_usage/zen_cookie`` (one
``__Host-console_session=...`` line) or the ``OPENCODE_ZEN_COOKIE`` env var.
Successful fetches are cached to ``~/.local/share/agent_report/opencode_zen.json``
and reused when the console is unreachable.

The API returns lifetime aggregates per model/provider, not per-turn rows, so
each row becomes one assistant record with ``timestamp=0`` — all-time reports
include it, windowed reports (``-7`` etc.) cannot attribute it and skip it.
Cost is recorded (metered by opencode), so it needs no pricing lookup.
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from .util import expand, make

NAME = "opencode_zen"
LABEL = "OpenCode Zen/Go"
OPTIONAL = True

CONSOLE = "https://opencode.ai"
MICRO_CENTS = 1e8  # 100_000_000 micro-cents = $1


def cookie_path():
    override = os.environ.get("AGENT_REPORT_OPENCODE_ZEN_COOKIE")
    if override:
        return expand(override)
    return Path.home() / ".local" / "share" / "opencode_usage" / "zen_cookie"


def _fixture():
    """Offline JSON override (used by tests): AGENT_REPORT_OPENCODE_ZEN_JSON."""
    path = os.environ.get("AGENT_REPORT_OPENCODE_ZEN_JSON")
    return expand(path) if path else None


def cache_path():
    return expand("~/.local/share/agent_report/opencode_zen.json")


def available():
    return bool(_fixture() and Path(_fixture()).exists()) or bool(
        os.environ.get("OPENCODE_ZEN_COOKIE")
    ) or cookie_path().exists()


def discover():
    source = _fixture()
    if source and Path(source).exists():
        return [Path(source)]
    return [cookie_path()]


def _get(url, cookie=None, org=None):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "agent-usage-report/1.0")
    if cookie:
        req.add_header("Cookie", cookie)
    if org:
        req.add_header("x-org-id", org)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_items():
    """Return the raw per-model usage items, from network, cache, or fixture."""
    fixture = _fixture()
    if fixture and Path(fixture).exists():
        return json.loads(Path(fixture).read_text())["items"]

    cookie = os.environ.get("OPENCODE_ZEN_COOKIE")
    if not cookie and cookie_path().exists():
        cookie = cookie_path().read_text().strip()

    try:
        if not cookie:
            raise OSError("no console session cookie")
        orgs = _get(CONSOLE + "/console/api/orgs", cookie=cookie)
        items = []
        for org in orgs:
            data = _get(CONSOLE + "/console/api/usage/models", cookie=cookie,
                        org=org.get("id"))
            items.extend(data.get("items") or [])
        cache_path().parent.mkdir(parents=True, exist_ok=True)
        cache_path().write_text(json.dumps({"items": items}))
        return items
    except Exception:
        if cache_path().exists():
            return json.loads(cache_path().read_text())["items"]
        return []


def records():
    for item in fetch_items():
        provider = str(item.get("provider") or "opencode")
        # 'opencode' is the Zen catalog, 'opencode-go' the Go catalog.
        if provider == "opencode-go":
            provider = "opencode"
        cost = float(item.get("totalCostMicroCents") or 0) / MICRO_CENTS
        yield make(
            kind="assistant", harness=NAME,
            session_id="opencode-console",
            timestamp=0.0,
            provider=provider,
            model=str(item.get("model") or "unknown"),
            input=int(item.get("totalInputTokens") or 0),
            cache_read=int(item.get("totalCacheReadTokens") or 0),
            cache_write=int(item.get("totalCacheWrite5mTokens") or 0)
            + int(item.get("totalCacheWrite1hTokens") or 0),
            output=int(item.get("totalOutputTokens") or 0),
            cost=cost if cost else None,
            cost_source="recorded" if cost else None,
        )
