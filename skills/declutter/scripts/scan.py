#!/usr/bin/env python3
"""Scan macOS for installed apps (GUI + brew), leftovers. Writes JSON to stdout.

usage: scan.py [-h|--help]
example: python3 scripts/scan.py > ~/tmp/declutter/scan.json

Read-only. Reads /Applications, ~/Applications, the Homebrew Cellar and
Caskroom under $HOMEBREW_PREFIX (default /opt/homebrew), ~/Library/Application
Support, ~/Library/Caches, ~/Library/Logs, the Xcode caches under
~/Library/Developer, and ~/.config/declutter/ignored.json (paths to hide).
Runs `mdls` and `brew list --cask`. Exit 0 with the JSON on stdout.
"""
import json
import os
import plistlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import time as _time

HOME = Path.home()
BREW_PREFIX = Path(os.environ.get("HOMEBREW_PREFIX", "/opt/homebrew"))
CELLAR = BREW_PREFIX / "Cellar"
CASKROOM = BREW_PREFIX / "Caskroom"
APP_DIRS = [Path("/Applications"), HOME / "Applications"]
LEFTOVER_BASES = [HOME / "Library/Application Support", HOME / "Library/Caches"]

# regenerable file targets; DerivedData and Logs are split per child,
# the rest count as one item each
FILE_SCANS = {
    HOME / "Library/Developer/Xcode/DerivedData": "children",
    HOME / "Library/Developer/CoreSimulator/Caches": "whole",
    HOME / "Library/Caches/Homebrew": "whole",
    HOME / "Library/Caches/pip": "whole",
    HOME / "Library/Caches/Yarn": "whole",
    HOME / "Library/Logs": "children",
}
MIN_FILE_BYTES = 1_000_000  # hide sub-1MB cache crumbs

# ponytail: substring-based leftover filter, false positives land in report for human review
GENERIC_DIRS = {"iCloud", "MobileSync", "Group Containers", "Containers", "Sync",
                "Backup", "Knowledge", "CrashReporter", "Saved Application State",
                "Google", "Apple", "com.apple"}

JUNK_DAYS = 90
MAYBE_DAYS = 30
IGNORE_FILE = Path.home() / ".config" / "declutter" / "ignored.json"


def load_ignored():
    try:
        return set(json.loads(IGNORE_FILE.read_text()))
    except Exception:
        return set()


def badge(days):
    if days is None or days > JUNK_DAYS:
        return "JUNK"
    if days > MAYBE_DAYS:
        return "MAYBE"
    return "KEEP"


def norm(name):
    return (name.lower().replace(" ", "").replace("-", "").replace("_", "")
            .removesuffix(".app"))


def is_known(entry_name, installed_keys):
    """True if entry name plausibly belongs to an installed app (substring rule)."""
    n = norm(entry_name)
    if not n:
        return True
    return any(n in k or k in n for k in installed_keys)


def run(cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return p.stdout if p.returncode == 0 else ""
    except Exception:
        return ""


def dir_age_days(path):
    try:
        age = _time.time() - os.path.getmtime(path)
        return max(0, int(age // 86400))
    except OSError:
        return None


def dir_size(path):
    out = run(["du", "-sk", str(path)])
    try:
        return int(out.split()[0]) * 1024
    except (ValueError, IndexError):
        return 0


def read_info(app_path):
    try:
        with open(app_path / "Contents" / "Info.plist", "rb") as f:
            return plistlib.load(f)
    except Exception:
        return {}


def last_used_days(app_path):
    raw = run(["mdls", "-name", "kMDItemLastUsedDate", "-raw", str(app_path)]).strip()
    if not raw or raw == "(null)":
        return None
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S %z")
        return max(0, (datetime.now(timezone.utc) - dt).days)
    except ValueError:
        return None


def cask_app_map():
    """normalized app name -> cask name, from brew's own artifact list."""
    raw = run(["brew", "list", "--cask", "--json=v2"])
    if not raw:
        return {}
    try:
        casks = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    mapping = {}
    for c in casks:
        for art in c.get("artifacts", []):
            if isinstance(art, dict):
                apps = art.get("app") or []
                if isinstance(apps, str):
                    apps = [apps]
                for a in apps:
                    if isinstance(a, str):
                        mapping[norm(a)] = c["name"]
    return mapping


def scan_apps():
    casks = cask_app_map()
    apps = []
    for d in APP_DIRS:
        if not d.is_dir():
            continue
        for item in sorted(d.glob("*.app")):
            info = read_info(item)
            name = item.stem
            exe = info.get("CFBundleExecutable") or name
            days = last_used_days(item)
            apps.append({
                "kind": "app",
                "name": name,
                "path": str(item),
                "bundle_id": info.get("CFBundleIdentifier", ""),
                "bytes": dir_size(item),
                "days_unused": days,
                "badge": badge(days),
                "running": bool(run(["pgrep", "-x", exe]).strip()),
                "source": "brew" if norm(name) in casks else "manual",
                "cask": casks.get(norm(name), ""),
                "duplicate": False,
            })
    by_name = {}
    for a in apps:
        by_name.setdefault(norm(a["name"]), []).append(a)
    for a in apps:
        a["duplicate"] = len(by_name[norm(a["name"])]) > 1
    return apps, casks


def scan_formulae():
    raw = run(["brew", "list", "--formula", "--json=v2"])
    if not raw:
        return []
    try:
        formulae = json.loads(raw)
    except json.JSONDecodeError:
        return []
    leaves = set(run(["brew", "leaves"]).split())
    out = []
    for f in formulae:
        name = f["name"]
        cellar = CELLAR / name
        required_by = []
        if name not in leaves:
            required_by = run(["brew", "uses", "--installed", name]).split()
        out.append({
            "kind": "formula",
            "name": name,
            "path": str(cellar),
            "bytes": dir_size(cellar) if cellar.exists() else 0,
            "days_unused": None,
            "badge": "KEEP" if required_by else "MAYBE",
            "leaf": name in leaves,
            "required_by": required_by,
            "version": (f.get("installed") or [{}])[0].get("version", "?"),
        })
    return out


def scan_leftovers(installed_keys):
    out = []
    for base in LEFTOVER_BASES:
        if not base.is_dir():
            continue
        for entry in sorted(base.iterdir()):
            if (entry.name.startswith(".") or entry.name in GENERIC_DIRS
                    or entry.name.startswith("com.apple.")):
                continue
            if is_known(entry.name, installed_keys):
                continue
            out.append({
                "kind": "leftover",
                "name": entry.name,
                "path": str(entry),
                "bytes": dir_size(entry),
                "days_unused": None,
                "badge": "MAYBE",
                "from": base.name,
            })
    return out


def scan_files():
    targets = []
    for base, mode in FILE_SCANS.items():
        if not base.is_dir():
            continue
        if mode == "children":
            targets += sorted(base.iterdir())
        else:
            targets.append(base)
    # ponytail: depth-5 home-wide find, misses deeper projects, stays fast
    found = run(["find", str(HOME), "-maxdepth", "5", "-name", "node_modules",
                 "-type", "d", "-prune", "-not", "-path", "*/Library/*"])
    targets += [Path(p) for p in found.splitlines() if p.strip()]
    out = []
    for t in targets:
        size = dir_size(t)
        if size < MIN_FILE_BYTES:
            continue
        days = dir_age_days(t)
        out.append({
            "kind": "file",
            "name": t.name,
            "path": str(t),
            "bytes": size,
            "days_unused": days,
            "badge": badge(days),
            "running": False,
            "duplicate": False,
            "source": "regenerable",
        })
    return out


def main():
    if {"-h", "--help"} & set(sys.argv[1:]):
        print(__doc__)
        return
    apps, casks = scan_apps()
    formulae = scan_formulae()
    installed_keys = ({norm(a["name"]) for a in apps}
                      | {norm(a["bundle_id"]) for a in apps if a["bundle_id"]}
                      | {norm(c) for c in casks.values()}
                      | {norm(f["name"]) for f in formulae})
    leftovers = scan_leftovers(installed_keys)
    files = scan_files()
    items = apps + formulae + leftovers + files
    ignored = load_ignored()
    shown = [i for i in items if i["path"] not in ignored]
    json.dump({
        "generated": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "apps": len(apps),
            "formulae": len(formulae),
            "leftovers": len(leftovers),
            "files": len(files),
            "junk": sum(1 for i in shown if i["badge"] == "JUNK"),
            "reclaimable_bytes": sum(i["bytes"] for i in shown if i["badge"] != "KEEP"),
            "ignored_hidden": len(items) - len(shown),
        },
        "items": shown,
    }, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
