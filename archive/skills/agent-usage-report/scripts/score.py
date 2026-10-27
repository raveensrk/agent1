"""Quality, efficiency and market-popularity verdicts.

Quality: Artificial Analysis Intelligence Index (independent public
benchmark, 0-100). Efficiency: AA index per dollar you actually paid.

The verdict is the market's, not yours: the 3 most-used frontier models and
the 3 most-used flash-tier models worldwide (OpenRouter daily token share),
cross-checked against Artificial Analysis tier data, and flagged when they
also appear in your logs.
"""

from __future__ import annotations

from benchmarks import normalize
from popularity import _FLASH_PRICE, _FLASH_SPEED, _TIER_WORDS


def compute(dataset, aa, or_rankings, config=None):
    """Attach AA benchmarks, rank value per dollar, and build the verdict."""
    models = dataset["models"]
    ranked = []
    for entry in models.values():
        info = aa.get(normalize(entry["model"])) or {}
        entry["aa_intelligence"] = info.get("intelligence_index")
        if entry["aa_intelligence"] is not None and entry["turns"] > 0:
            ranked.append(entry)
        else:
            entry["efficiency_score"] = None

    # Efficiency: benchmark quality per dollar actually paid, ranked across
    # the models you use. A free model that scores well wins outright.
    for entry in ranked:
        cost = entry.get("cost_per_million") or 0.0
        entry["value_per_dollar"] = round(
            (entry["aa_intelligence"] or 0.0) / (cost + 0.01), 3)
    efficiency_order = sorted(ranked, key=lambda e: (-e["value_per_dollar"], e["model"]))
    for index, entry in enumerate(efficiency_order, 1):
        entry["efficiency_score"] = round(
            100.0 * (len(ranked) - index) / (len(ranked) - 1), 1) if len(ranked) > 1 else 100.0

    leaders = {
        "most_intelligent": None,
        "most_efficient": None,
        "cheapest": None,
        "biggest_spend": None,
    }
    with_index = [e for e in ranked if e.get("aa_intelligence") is not None]
    if with_index:
        leaders["most_intelligent"] = max(
            with_index, key=lambda e: (e["aa_intelligence"], e["turns"]))
        leaders["most_efficient"] = max(ranked, key=lambda e: e["value_per_dollar"])
    with_cost = [e for e in models.values() if e.get("cost_per_million")]
    if with_cost:
        leaders["cheapest"] = min(with_cost, key=lambda e: e["cost_per_million"])
    spenders = [e for e in models.values() if (e.get("cost_total") or 0) > 0]
    if spenders:
        leaders["biggest_spend"] = max(spenders, key=lambda e: e["cost_total"])

    dataset["ranking"] = ranked
    dataset["unranked"] = [e for e in models.values() if e.get("aa_intelligence") is None]
    dataset["leaders"] = leaders
    dataset["totals"] = _totals(dataset, models)
    dataset["market"] = _verdict(dataset, aa, or_rankings)
    return dataset


def _verdict(dataset, aa, or_rankings):
    """3 most-used frontier + 3 most-used flash-tier models worldwide.

    Tiers come from Artificial Analysis data (dynamic frontier cutoff,
    flash-name heuristics), popularity from OpenRouter daily tokens.
    """
    cutoff = _frontier_cutoff(aa)
    used = {normalize(entry["model"]) for entry in dataset["models"].values()}
    verdict = {"frontier": [], "flash": [], "source_models": 0}
    for row in or_rankings:
        key = normalize(row["slug"].rsplit("/", 1)[-1])
        info = aa.get(key) or {}
        if not verdict["frontier"] or len(verdict["frontier"]) < 3:
            pass
        tier = _tier(row["slug"], info, cutoff)
        if tier not in ("frontier", "flash"):
            continue
        if any(e["key"] == key for e in verdict[tier]):
            continue
        if len(verdict[tier]) >= 3:
            continue
        verdict[tier].append({
            "key": key,
            "model": row["slug"].rsplit("/", 1)[-1],
            "share": round(row["share"], 1),
            "tokens": row["tokens"],
            "aa_intelligence": info.get("intelligence_index"),
            "used_by_you": key in used,
        })
        verdict["source_models"] += 1
    return verdict


def _tier(name, info, cutoff):
    index = info.get("intelligence_index")
    price = info.get("price")
    speed = info.get("speed")
    low = str(name).lower()
    # a model named flash/mini/... is flash tier even if it is smart
    if any(w in low for w in _TIER_WORDS):
        return "flash"
    if price is not None and speed is not None \
            and float(price) <= _FLASH_PRICE and float(speed) >= _FLASH_SPEED:
        return "flash"
    if index is not None and cutoff is not None and index >= cutoff:
        return "frontier"
    return None


def _frontier_cutoff(aa):
    """Frontier = top quartile of the AA Intelligence Index catalog.
    With a tiny catalog, the best model defines the bar."""
    indexes = sorted(
        (v["intelligence_index"] for v in aa.values()
         if v.get("intelligence_index") is not None), reverse=True)
    if not indexes:
        return None
    return indexes[len(indexes) // 4] if len(indexes) >= 8 else indexes[0]


def _totals(dataset, models):
    total_tokens = sum(e["total"] for e in models.values())
    cost = sum(e.get("cost_total") or 0.0 for e in models.values())
    recorded = sum(e.get("cost_recorded") or 0.0 for e in models.values())
    uncached = sum(e["input"] for e in models.values())
    split = _cost_split(models)
    return {
        "tokens": total_tokens,
        "input": uncached,
        "output": sum(e["output"] for e in models.values()),
        "cache_read": sum(e["cache_read"] for e in models.values()),
        "cache_write": sum(e["cache_write"] for e in models.values()),
        "reasoning": sum(e["reasoning"] for e in models.values()),
        "cost": cost,
        "cost_recorded": recorded,
        "cost_computed": cost - recorded,
        "cost_split": split,
        "cache_saving": _cache_saving(models),
        "cache_hit_rate": round(
            sum(e["cache_read"] for e in models.values()) * 100.0
            / ((uncached + sum(e["cache_read"] for e in models.values())) or 1), 1),
        "models": len(models),
        "sessions": dataset["sessions"],
        "requests": dataset["requests"],
        "turns": dataset["turns"],
        "waste": round(sum(e.get("waste_cost") or 0.0 for e in models.values()), 4),
        "wasted_turns": sum(e.get("error_stops", 0) for e in models.values()),
        "blended_per_million": round(cost / total_tokens * 1_000_000, 4) if total_tokens else 0.0,
    }


def _cost_split(models):
    """Where the money went, estimated from rates for every model with pricing."""
    split = {"input": 0.0, "cache_read": 0.0, "cache_write": 0.0, "output": 0.0}
    for entry in models.values():
        rates = entry.get("rates")
        if not rates:
            continue
        for key in split:
            rate = rates.get(key)
            if rate is None:
                continue
            split[key] += float(entry.get(key) or 0) * float(rate) / 1_000_000.0
    return {k: round(v, 4) for k, v in split.items()}


def _cache_saving(models):
    """Dollars saved by reading from cache instead of paying full input rate."""
    saving = 0.0
    for entry in models.values():
        rates = entry.get("rates")
        if not rates:
            continue
        full = rates.get("input")
        discounted = rates.get("cache_read")
        if full is None or discounted is None:
            continue
        saving += entry["cache_read"] * max(
            0.0, float(full) - float(discounted)) / 1_000_000.0
    return round(saving, 4)
