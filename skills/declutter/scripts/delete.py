#!/usr/bin/env python3
"""Remove selected declutter items; dry run unless --execute is supplied.

Usage: delete.py SELECTION [--execute] [--log PATH] [--save-ignore]
       delete.py -h | --help | help

Successful program removals are verified and logged in
~/dot_local/app_cleanup.yaml (override with --log). Manual apps move to Trash;
Homebrew uninstall permanently removes package files. Requires PyYAML.
--save-ignore changes only the persistent ignore list. Exit 1 when any selected
removal fails, is blocked or cannot be verified; exit 0 otherwise.
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledger

HOME = Path.home()
TRASH = HOME / ".Trash"
BREW_PREFIX = Path("/opt/homebrew")
CELLAR = BREW_PREFIX / "Cellar"
CASKROOM = BREW_PREFIX / "Caskroom"
SAFE_ROOTS = ["/Applications", str(HOME), str(CELLAR), str(CASKROOM)]


IGNORE_FILE = Path.home() / ".config" / "declutter" / "ignored.json"


def merge_ignore(existing, adding):
    return sorted(set(existing) | {a for a in adding if a})


def save_ignore(selection_path):
    sel = json.loads(Path(selection_path).read_text())
    adding = [i.get("path") for i in sel.get("ignore", [])]
    try:
        existing = json.loads(IGNORE_FILE.read_text())
    except Exception:
        existing = []
    IGNORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    merged = merge_ignore(existing, adding)
    IGNORE_FILE.write_text(json.dumps(merged, indent=1))
    return len(merged)


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if p.returncode:
        raise RuntimeError((p.stdout + p.stderr).strip() or f"command failed: {cmd}")
    return p.stdout + p.stderr


def safe(path):
    # ponytail: absolute() not resolve() - /Applications apps are symlinks into /System
    p = Path(path).absolute()
    return p != Path("/") and any(str(p).startswith(r) for r in SAFE_ROOTS)


def running(item):
    path = item["path"]
    if Path(path).suffix != ".app":
        return False
    output = run(["ps", "-axo", "comm="])
    return any(line.strip().startswith(path + "/") for line in output.splitlines())


def trash(path):
    src = Path(path)
    if not src.exists():
        return f"skip (missing): {path}"
    dest = TRASH / src.name
    if dest.exists():
        dest = TRASH / f"{src.name}.{int(time.time())}"
    try:
        shutil.move(str(src), str(dest))
        return f"trashed {src}"
    except (PermissionError, OSError):
        # /Applications apps are root-owned - Finder prompts for admin
        out = run(["osascript", "-e",
                   f'tell application "Finder" to delete POSIX file "{src}"'])
        if not src.exists():
            return f"trashed via Finder {src}"
        return f"FAILED {src}: Finder said {out.strip()[:120]}"


def plan(item, execute, log=ledger.LOG):
    kind, name = item["kind"], item.get("name", "?")
    if not safe(item.get("path", "/")):
        return f"BLOCKED {name}: unsafe path {item.get('path')}"
    tracked = execute and kind in {"app", "cask", "formula"}
    if tracked:
        if running(item):
            return f"BLOCKED {name}: app is running - save your work and quit it first"
        ledger.load(log)
        record = ledger.identity(item)
    if kind == "cask":
        if not execute:
            return f"would run: brew uninstall --cask --force {item.get('cask') or name}"
        out = run(["brew", "uninstall", "--cask", "--force", item.get("cask") or name])
        ledger.record(record, "brew_uninstall_permanent", log)
        return f"brew cask {item.get('cask') or name}: {out.strip().splitlines()[-1] if out.strip() else 'ok'}"
    if kind == "formula":
        used = run(["brew", "uses", "--installed", name]).split()
        if used:
            return f"BLOCKED {name}: required by {' '.join(used[:3])} - deselect it"
        if not execute:
            return f"would run: brew uninstall {name}"
        out = run(["brew", "uninstall", name])
        ledger.record(record, "brew_uninstall_permanent", log)
        return f"brew formula {name}: {out.strip().splitlines()[-1] if out.strip() else 'ok'}"
    if kind in ("app", "leftover", "file"):
        if not execute:
            return f"would trash {item['path']}"
        result = trash(item["path"])
        if tracked and result.startswith("trashed"):
            ledger.record(record, "move_to_trash", log)
        return result
    return f"BLOCKED {name}: unknown kind {kind}"


def main():
    if sys.argv[1:] == ["help"]:
        print(__doc__)
        return 0
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("selection", nargs="?", help="path to declutter-selection.json")
    ap.add_argument("--execute", action="store_true", help="apply for real (default: dry run)")
    ap.add_argument("--log", type=Path, default=ledger.LOG, help="YAML removal log")
    ap.add_argument("--save-ignore", action="store_true",
                    help="merge selection's ignore list into the persistent ignore file, then exit")
    args = ap.parse_args()
    if args.selection is None:
        ap.error("selection is required")
    if args.save_ignore:
        n = save_ignore(args.selection)
        print(f"ignore list now has {n} entr(y/ies): {IGNORE_FILE}")
        return
    with open(args.selection) as f:
        items = json.load(f).get("items", [])
    if args.execute:
        ledger.load(args.log)
    print(f"{len(items)} item(s) selected\n")
    failed = False
    for it in items:
        try:
            result = plan(it, args.execute, args.log)
            print(result)
            failed = failed or result.startswith(("FAILED", "BLOCKED"))
        except Exception as e:
            print(f"FAILED {it.get('name', '?')}: {e}")
            failed = True
    if not args.execute:
        print("\nDRY RUN - re-run with --execute to apply.")
    else:
        print(f"\nVerified program removals logged in {args.log}.")
        print("Leave Trash intact until you are happy with the result.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
