#!/usr/bin/env python3
"""Ping-pong latency benchmark: same prompts through pi, wall-clock timing.

Runs each model N short-prompt runs (one-word reply) and 1 long reasoning
prompt via `pi -p`, measuring wall time. Timing includes pi CLI startup and
the model's thinking time; identical for every model, so comparisons hold.

Usage:
  ping_pong.py model1 [model2 ...] [--runs N]     default runs=3
  ping_pong.py --prompts                          print the two prompts

Output: one JSON object with per-model short (times, mean, median) and long
(total seconds, output chars) results.
"""

import json
import statistics
import subprocess
import sys
import time
from datetime import datetime

SHORT = "Reply with exactly one word: PONG"
LONG = ("Design a rate limiter for a multi-tenant API gateway. Requirements: "
        "1M requests/minute sustained, per-tenant quotas, burst allowance, "
        "Redis-backed, eventual consistency acceptable. Reason step by step: "
        "algorithm choice (token bucket vs sliding window vs leaky bucket), "
        "data model, failure modes, and a rollout plan. Finish with the final "
        "design as a numbered list.")


def run(model, prompt, timeout=600, retries=2):
    for i in range(retries + 1):
        t0 = time.perf_counter()
        try:
            r = subprocess.run(["pi", "-p", prompt, "--model", model],
                               capture_output=True, text=True, timeout=timeout)
            ok, out = r.returncode == 0 and bool(r.stdout.strip()), r.stdout.strip()
        except subprocess.TimeoutExpired:
            ok, out = False, ""
        if ok:
            return {"ok": True, "s": round(time.perf_counter() - t0, 2), "chars": len(out)}
        if i < retries:
            time.sleep(5 * (i + 1))  # provider rate-limit cooldown
    return {"ok": False, "s": round(time.perf_counter() - t0, 2), "chars": 0}


def main():
    args = sys.argv[1:]
    if "--prompts" in args:
        print("SHORT:", SHORT, "\nLONG:", LONG)
        return
    runs = 3
    if "--runs" in args:
        runs = int(args[args.index("--runs") + 1])
    models = [a for a in args if not a.startswith("-") and not a.isdigit()]
    if not models:
        sys.exit("usage: ping_pong.py model1 [model2 ...] [--runs N]")
    result = {"generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
              "runner": "pi -p", "runs": runs, "short_prompt": SHORT,
              "long_prompt": LONG, "models": {}}
    for m in models:
        short = [run(m, SHORT) for _ in range(runs)]
        longr = run(m, LONG)
        ok = [r["s"] for r in short if r["ok"]]
        result["models"][m] = {
            "short_times": ok,
            "short_mean": round(statistics.mean(ok), 2) if ok else None,
            "short_median": round(statistics.median(ok), 2) if ok else None,
            "long": longr,
        }
        print(f"{m}: short {result['models'][m]['short_mean']}s mean, "
              f"long {longr['s']}s ({longr['chars']} chars)", file=sys.stderr)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
