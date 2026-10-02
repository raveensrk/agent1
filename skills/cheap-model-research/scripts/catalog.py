#!/usr/bin/env python3
"""Catalog union of pi and opencode models, priced via models.dev.

Outputs one JSON object to stdout:
  generated_at, pi_version, opencode_version, counts, models[]

models[] fields: provider, id, in_pi, in_opencode, availability, context,
max_output, thinking, images, reasoning, tool_call, open_weights, knowledge,
release_date, modalities, cost_in, cost_out, price_usd_per_m, pricing, usable.

availability: "both", "pi", or "opencode".

Usage:
  catalog.py            full pipeline (network for models.dev)
  catalog.py --selftest parser tests only, no network
  catalog.py --check    live pipeline, asserts instead of JSON
"""

import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CACHE = Path.home() / ".cache" / "cheap_model_research" / "api.json"
MODELS_DEV = "https://models.dev/api.json"
MIN_CONTEXT = 32_000
BLEND = (3, 1)  # input:output weight for blended price


def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed (exit {r.returncode}): {r.stderr.strip()[:200]}")
    return r.stdout


def parse_pi(text):
    """pi --list-models table -> [(provider, model, ctx, maxout, think, img)]."""
    rows = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 6 or parts[0] == "provider":
            continue
        provider, model = parts[0], parts[1]
        rows.append((provider, model, parts[2], parts[3],
                     parts[4].lower() == "yes", parts[5].lower() == "yes"))
    return rows


def parse_opencode(text):
    """opencode models lines 'provider/model' -> [(provider, model)]."""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line or "/" not in line:
            continue
        provider, model = line.split("/", 1)
        rows.append((provider, model))
    return rows


def fetch_models_dev():
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    req = urllib.request.Request(MODELS_DEV, headers={"User-Agent": "cheap-model-research/1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
    CACHE.write_text(json.dumps(data))
    return data


def version(cmd, arg="-v"):
    try:
        out = subprocess.run([cmd, arg], capture_output=True, text=True, timeout=30)
        return (out.stdout + out.stderr).strip().splitlines()[0][:80]
    except Exception:
        return "unknown"


def blend_price(mdev_model):
    cost = mdev_model.get("cost") or {}
    cin, cout = cost.get("input"), cost.get("output")
    if cin is None or cout is None:
        if cin == 0 and cout == 0:
            return 0.0, "free", 0.0, 0.0
        return None, "unknown", cin, cout
    pricing = "free" if cin == 0 and cout == 0 else "paid"
    w_in, w_out = BLEND
    blended = (w_in * cin + w_out * cout) / (w_in + w_out)
    return blended, pricing, cin, cout


def usable(m):
    if not m.get("usable_capability"):
        return False
    if m["pricing"] == "unknown":
        return False
    ctx = m.get("context")
    return isinstance(ctx, int) and ctx >= MIN_CONTEXT


def build(pi_rows, oc_rows, catalog):
    oc_set = {(p, m) for p, m, *_ in oc_rows}
    pi_set = {(p, m) for p, m, *_ in pi_rows}
    models = []
    def entry_for(provider, model, pi_row=None):
        mdev = catalog.get(provider, {}).get("models", {}).get(model)
        entry = {
            "provider": provider, "id": model,
            "in_pi": pi_row is not None or (provider, model) in pi_set,
            "in_opencode": (provider, model) in oc_set,
            "context": mdev.get("limit", {}).get("context") if mdev else None,
            "max_output": mdev.get("limit", {}).get("output") if mdev else None,
            "thinking": bool(mdev.get("reasoning")) if mdev else (pi_row[2] if pi_row else None),
            "images": bool(mdev.get("attachment")) if mdev else (pi_row[3] if pi_row else None),
            "tool_call": bool(mdev.get("tool_call")) if mdev else None,
            "open_weights": mdev.get("open_weights") if mdev else None,
            "knowledge": mdev.get("knowledge") if mdev else None,
            "release_date": mdev.get("release_date") if mdev else None,
            "in_models_dev": mdev is not None,
        }
        entry["availability"] = "both" if entry["in_pi"] and entry["in_opencode"] else ("pi" if entry["in_pi"] else "opencode")
        if mdev:
            blended, pricing, cin, cout = blend_price(mdev)
            entry.update(pricing=pricing, price_usd_per_m=blended,
                         cost_in=cin, cost_out=cout)
            entry["usable_capability"] = bool(
                mdev.get("reasoning") or mdev.get("tool_call"))
            out_mods = (mdev.get("modalities") or {}).get("output") or ["text"]
            entry["usable_capability"] = entry["usable_capability"] and "text" in out_mods
        else:
            entry.update(pricing="unknown", price_usd_per_m=None,
                         cost_in=None, cost_out=None, usable_capability=None)
        entry["usable"] = usable(entry)
        return entry
    for provider, model, ctx, maxout, think, img in pi_rows:
        models.append(entry_for(provider, model, (ctx, maxout, think, img)))
    seen = pi_set
    for provider, model in oc_rows:
        if (provider, model) not in seen:
            models.append(entry_for(provider, model))
    models.sort(key=lambda m: (m["price_usd_per_m"] is None,
                               m["price_usd_per_m"] if m["price_usd_per_m"] is not None else 0,
                               m["provider"], m["id"]))
    return models


def run(check=False):
    catalog = fetch_models_dev()
    models = build(parse_pi(sh(["pi", "--list-models"])),
                   parse_opencode(sh(["opencode", "models"])), catalog)
    result = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "pi_version": version("pi"), "opencode_version": version("opencode"),
        "counts": {
            "union": len(models),
            "both": sum(m["availability"] == "both" for m in models),
            "pi_only": sum(m["availability"] == "pi" for m in models),
            "opencode_only": sum(m["availability"] == "opencode" for m in models),
            "usable": sum(m["usable"] for m in models),
            "free": sum(m["pricing"] == "free" for m in models),
            "unknown_price": sum(m["pricing"] == "unknown" for m in models),
        },
        "models": models,
    }
    if check:
        assert result["counts"]["union"] > 0, "empty union"
        for m in models:
            if m["in_models_dev"]:
                assert m["pricing"] in ("free", "paid")
        print(f"check ok: {result['counts']}")
    else:
        print(json.dumps(result, indent=2))


def selftest():
    pi = ("provider      model        context  max-out  thinking  images\n"
          "anthropic     claude-haiku-4-5  200K  64K  yes  yes\n"
          "xai           grok-mini         1M    8K   no   no\n")
    oc = ("xai/grok-mini\nopencode/big-pickle\nbadline\n")
    p = parse_pi(pi)
    assert len(p) == 2 and p[0][:2] == ("anthropic", "claude-haiku-4-5")
    assert p[0][4] is True and p[1][4] is False
    o = parse_opencode(oc)
    assert o == [("xai", "grok-mini"), ("opencode", "big-pickle")]
    cat = {"xai": {"models": {"grok-mini": {
        "reasoning": False, "tool_call": True, "attachment": False,
        "modalities": {"input": ["text"], "output": ["text"]},
        "limit": {"context": 1_000_000, "output": 8_000},
        "cost": {"input": 0.1, "output": 0.5}}}}}
    out = build(p, o, cat)
    assert len(out) == 3, out  # union: both-row + pi-only + opencode-only
    m = out[0]
    assert m["id"] == "grok-mini" and m["pricing"] == "paid"
    assert abs(m["price_usd_per_m"] - 0.2) < 1e-9  # (3*0.1 + 1*0.5)/4
    assert m["usable"] is True
    assert m["availability"] == "both"
    pi_only = out[1]
    assert pi_only["id"] == "claude-haiku-4-5" and pi_only["availability"] == "pi"
    assert pi_only["pricing"] == "unknown" and pi_only["usable"] is False
    other = out[2]
    assert other["id"] == "big-pickle" and other["availability"] == "opencode"
    assert other["pricing"] == "unknown" and other["usable"] is False
    # free model
    cat["xai"]["models"]["grok-mini"]["cost"] = {"input": 0, "output": 0}
    assert build(p, o, cat)[0]["pricing"] == "free"
    # plan-only model: unknown price, unusable
    cat["xai"]["models"]["grok-mini"].pop("cost")
    assert build(p, o, cat)[0]["pricing"] == "unknown"
    assert build(p, o, cat)[0]["usable"] is False
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    elif "--check" in sys.argv:
        run(check=True)
    else:
        run()
