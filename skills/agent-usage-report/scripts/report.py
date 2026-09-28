#!/usr/bin/env python3
"""agent-usage-report - one HTML report of every model you used, across harnesses.

Usage:
    python3 report.py                     # all time, opens the report
    python3 report.py -7                  # last 7 days
    python3 report.py -1w                 # last week
    python3 report.py -1d                 # yesterday
    python3 report.py --since 2026-09-01 --until 2026-09-15
    python3 report.py --check             # detect harnesses only, write nothing
    python3 report.py --no-open --offline

Reads logs from pi, Claude Code, Codex and opencode (plus any harnesses you
declare in config), prices them via models.dev, scores the models, and writes a
single self-contained HTML file. Never writes inside a git repository.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import webbrowser
from pathlib import Path

# This skill may live in a public repository; never drop .pyc files there.
sys.dont_write_bytecode = True

sys.path.insert(0, str(Path(__file__).resolve().parent))

import collect  # noqa: E402
import benchmarks  # noqa: E402
import popularity  # noqa: E402
import pricing  # noqa: E402
import render  # noqa: E402
import score  # noqa: E402
import validate  # noqa: E402
CONFIG_NAME = "config.json"


# --------------------------------------------------------------------------
# Config and window
# --------------------------------------------------------------------------

def load_config(explicit=None):
    path = Path(explicit) if explicit else (pricing.report_home() / CONFIG_NAME)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = validate.validate_config(json.load(handle))
            data["_config_path"] = str(path)
            return data
    except (IOError, ValueError):
        return {}


def _midnight(value):
    return value.replace(hour=0, minute=0, second=0, microsecond=0)


def resolve_window(shortcut, since, until):
    now = datetime.datetime.now().astimezone()
    start = end = None

    if shortcut:
        text = shortcut.strip().lower().replace(" ", "")
        match = re.match(r"^0d$", text)
        if match:
            start, end = _midnight(now), now
        elif re.match(r"^-(\d+)d$", text):
            days = int(re.match(r"^-(\d+)d$", text).group(1))
            day = _midnight(now) - datetime.timedelta(days=days)
            start, end = day, day + datetime.timedelta(days=1)
        elif re.match(r"^-(\d+)w$", text):
            weeks = int(re.match(r"^-(\d+)w$", text).group(1))
            start, end = now - datetime.timedelta(days=weeks * 7), now
        elif re.match(r"^-(\d+)$", text):
            days = int(re.match(r"^-(\d+)$", text).group(1))
            start, end = _midnight(now) - datetime.timedelta(days=days - 1), now
        else:
            raise SystemExit("ERROR: unknown window shortcut %r" % shortcut)

    if since:
        start = _parse_day(since, now, end_of_day=False)
    if until:
        end = _parse_day(until, now, end_of_day=True)

    start_epoch = start.timestamp() if start else None
    end_epoch = end.timestamp() if end else None
    label = "all time"
    if start and end:
        label = "%s to %s" % (start.strftime("%Y-%m-%d %H:%M"),
                              end.strftime("%Y-%m-%d %H:%M"))
    elif start:
        label = "since %s" % start.strftime("%Y-%m-%d %H:%M")
    elif end:
        label = "until %s" % end.strftime("%Y-%m-%d %H:%M")
    pretty_start = start.strftime("%Y-%m-%d %H:%M") if start else "beginning"
    pretty_end = end.strftime("%Y-%m-%d %H:%M") if end else "now"
    return start_epoch, end_epoch, label, pretty_start, pretty_end


def _parse_day(text, now, end_of_day):
    text = text.strip()
    try:
        parsed = datetime.datetime.strptime(text, "%Y-%m-%d %H:%M")
    except ValueError:
        try:
            parsed = datetime.datetime.strptime(text, "%Y-%m-%d")
            if end_of_day:
                parsed = parsed + datetime.timedelta(days=1)
        except ValueError:
            raise SystemExit("ERROR: expected YYYY-MM-DD or 'YYYY-MM-DD HH:MM', got %r" % text)
    return parsed.astimezone()


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------

def run(args):
    config = load_config(args.config)

    records, detected, missing = collect.load(config, local=args.local)
    if args.check:
        return check(records, detected, missing, config, args)

    since, until, label, pretty_start, pretty_end = resolve_window(
        args.window, args.since, args.until)
    dataset = collect.aggregate(records, since=since, until=until)
    if not dataset["models"]:
        raise SystemExit("ERROR: no model turns found for window %r." % label)
    if not args.project_name:
        _redact_projects(dataset)

    catalog = pricing.build_catalog(config, refresh=args.refresh_pricing,
                                    offline=args.offline)
    pricing.attach(dataset, catalog)
    aa, aa_source = benchmarks.load(config, refresh=args.refresh_pricing,
                                    offline=args.offline)
    or_rankings, or_source = popularity.load(config, refresh=args.refresh_pricing,
                                             offline=args.offline)
    score.compute(dataset, aa, or_rankings, config)

    generated = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    meta = {
        "window": label,
        "window_start": pretty_start,
        "window_end": pretty_end,
        "generated": generated,
        "detected": detected,
        "missing": missing,
        "pricing_source": catalog.source,
        "pricing_models": catalog.size(),
        "benchmark_source": aa_source,
        "usage_source": or_source,
    }

    out_dir = _output_dir(args, config)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    html_path = Path(args.out) if args.out and args.out.endswith(".html") \
        else out_dir / ("agent_report_%s.html" % stamp)

    _guard_path(html_path)

    with open(html_path, "w", encoding="utf-8") as handle:
        handle.write(render.build(dataset, meta, config))

    leaders = dataset["leaders"]
    _print_summary(dataset, meta, leaders, html_path, args)
    if not args.no_open:
        _open(html_path)
    return 0


def _output_dir(args, config):
    """Where the HTML and JSON land: --out, then config, then ~/Downloads."""
    if args.out:
        target = Path(os.path.expanduser(os.path.expandvars(args.out)))
        return target.parent if args.out.endswith(".html") else target
    configured = config.get("output_dir")
    if configured:
        return Path(os.path.expanduser(os.path.expandvars(configured)))
    return Path.home() / "Downloads"


def _guard_path(path):
    """Refuse to write the report inside a git repository (it holds your spend)."""
    for parent in [path.parent, *path.parent.parents]:
        if (parent / ".git").exists():
            raise SystemExit(
                "ERROR: refusing to write the report inside a git repository (%s).\n"
                "Use --out with a path outside any repo, e.g. ~/Downloads." % parent)


def _redact_projects(dataset):
    """Replace real project names with Project N, ordered by token volume.

    Runs unless --project-name is passed, so the report never leaks repo or
    directory names. Scrubbing here fixes every section that shows projects
    (Projects chart + session drilldown) in one place.
    """
    names = [p["project"] for p in sorted(
        dataset["projects"].values(), key=lambda p: -p["total"])]
    alias = {name: "Project %d" % (i + 1) for i, name in enumerate(names)}
    for p in dataset["projects"].values():
        p["project"] = alias[p["project"]]
    for sess in dataset.get("sessions_detail") or []:
        if sess.get("project") in alias:
            sess["project"] = alias[sess["project"]]


def _print_summary(dataset, meta, leaders, html_path, args):
    totals = dataset["totals"]
    try:
        from rich.console import Console
        from rich.table import Table
        console = Console(highlight=False)
        console.print("[bold]agent-usage-report[/] - %s" % meta["window"])
        table = Table(box=None, show_header=False, pad_edge=False)
        table.add_column(style="dim", no_wrap=True)
        table.add_column()
        table.add_row("harnesses", ", ".join(
            "%s (%d records)" % (h["label"], h["records"]) for h in meta["detected"]))
        if meta["missing"]:
            table.add_row("not found", ", ".join(meta["missing"]))
        table.add_row("pricing", meta["pricing_source"])
        table.add_row("benchmarks", meta["benchmark_source"])
        table.add_row("usage share", meta["usage_source"])
        table.add_row("totals", "%s tokens, %s, %s turns, %s requests, %s sessions" % (
            render.fmt_tokens(totals["tokens"]), render.fmt_money(totals["cost"]),
            totals["turns"], totals["requests"], totals["sessions"]))
        market = dataset.get("market") or {}
        for tier, label in (("frontier", "top frontier"), ("flash", "top flash")):
            names = ", ".join("%s (%.1f%%)%s" % (
                e["model"], e["share"], " *" if e["used_by_you"] else "")
                for e in (market.get(tier) or []))
            table.add_row(label, names or "-")
        table.add_row("html", str(html_path))
        console.print(table)
        return
    except ImportError:
        pass
    # plain fallback when rich is not installed
    print("agent-usage-report - %s" % meta["window"])
    print("  harnesses: %s" % ", ".join(
        "%s (%d records)" % (h["label"], h["records"]) for h in meta["detected"]))
    if meta["missing"]:
        print("  not found: %s" % ", ".join(meta["missing"]))
    print("  pricing:   %s" % meta["pricing_source"])
    print("  benchmarks: %s" % meta["benchmark_source"])
    print("  usage share: %s" % meta["usage_source"])
    print("  totals:    %s tokens, %s, %s turns, %s requests, %s sessions" % (
        render.fmt_tokens(totals["tokens"]), render.fmt_money(totals["cost"]),
        totals["turns"], totals["requests"], totals["sessions"]))
    market = dataset.get("market") or {}
    for tier, label in (("frontier", "top frontier"), ("flash", "top flash")):
        names = ", ".join("%s (%.1f%%)%s" % (
            e["model"], e["share"], " *" if e["used_by_you"] else "")
            for e in (market.get(tier) or []))
        print("  %-10s %s" % (label + ":", names or "-"))
    print("  html:      %s" % html_path)


def _open(path):
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", str(path)])
        else:
            webbrowser.open(path.as_uri())
    except Exception:
        pass


def check(records, detected, missing, config, args):
    turns = [r for r in records if r.get("kind") == "assistant"]
    users = [r for r in records if r.get("kind") == "user"]
    models = sorted({(r.get("model") or "unknown") for r in turns})
    print("agent-usage-report --check")
    for item in detected:
        print("  found    %-14s %d records" % (item["label"], item["records"]))
    for label in missing:
        print("  missing  %-14s (no log directory)" % label)
    print("  turns    %d" % len(turns))
    print("  requests %d" % len(users))
    print("  models   %d: %s" % (len(models), ", ".join(models[:12]) +
                                 (" ..." if len(models) > 12 else "")))
    config_path = config.get("_config_path")
    if config_path:
        print("  config   %s" % config_path)
    if args.check_pricing and turns:
        catalog = pricing.build_catalog(config, refresh=args.refresh_pricing,
                                        offline=args.offline)
        resolved = 0
        for entry in scoring_probe(records):
            if catalog.resolve(entry[0], entry[1]):
                resolved += 1
        print("  pricing  %s" % catalog.source)
        print("  resolved %d/%d models priced" % (resolved, len(scoring_probe(records))))
    return 0


def scoring_probe(records):
    seen = {}
    for rec in records:
        if rec.get("kind") != "assistant":
            continue
        key = rec.get("model") or "unknown"
        seen.setdefault(key, (rec.get("provider") or "", key))
    return list(seen.values())


def build_parser():
    parser = argparse.ArgumentParser(
        prog="agent-usage-report",
        description="One HTML report of every model you used, across agent harnesses.")
    parser.add_argument("window", nargs="?", help="shortcut: 0d, -1d, -7, -1w")
    parser.add_argument("--since", help="start date, YYYY-MM-DD or 'YYYY-MM-DD HH:MM'")
    parser.add_argument("--until", help="end date, YYYY-MM-DD or 'YYYY-MM-DD HH:MM'")
    parser.add_argument("--out", help="output path (file ending in .html or a directory)")
    parser.add_argument("--config", help="path to config.json")
    parser.add_argument("--no-open", action="store_true", help="do not open the browser")
    parser.add_argument("--offline", action="store_true", help="never touch the network")
    parser.add_argument("--refresh-pricing", action="store_true", help="re-fetch models.dev and AA now")
    parser.add_argument("--local", action="store_true",
                        help="also read local harness logs (pi, Claude Code, Codex, opencode db); "
                             "default reads online sources only (OpenCode Zen/Go)")
    parser.add_argument("--project-name", action="store_true",
                        help="show real project names (default: redacted as Project N)")
    parser.add_argument("--check", action="store_true", help="detect harnesses, write nothing")
    parser.add_argument("--check-pricing", action="store_true", help="with --check, resolve prices")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
