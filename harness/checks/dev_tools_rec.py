#!/usr/bin/env python3
# harness-check: {"id": "dev_tools_rec", "applies": ["dev_tools.rec", "dev_tools.svg", "dev_tools_path.svg", "dev_tools.html", "dev_tools.py"], "quadrant": "feedback/computational"}
"""dev_tools.rec obeys its schema and its learning path, and both charts are drawn from it.

dev_tools.rec is the one file that lists the tools; its %type, %mandatory and
%allowed lines are the rules (Level 1-5, no unknown or misspelt fields, unique
names), and recfix decides them. The Requires lines carry rules recfix cannot
see - known names, no prerequisite above its tool's level or tier, no loops,
no arrow implied through another - and dev_tools.py --check decides those.
The charts (dev_tools.svg, dev_tools_path.svg, dev_tools.html) are generated
by dev_tools.py, so a hand edit to either side, or a record edit without a
redraw, is a finding.

Runs once per repo however many of these files changed: the findings are
about the data and its charts together, not about one path.

    dev_tools_rec.py FILE...      (or paths on stdin)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

REC = "dev_tools.rec"

# Paths arrive on stdin from the dispatcher, or as arguments when run by hand.
FILES = sys.argv[1:]
if not FILES and not sys.stdin.isatty():
    FILES = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]


def main() -> int:
    if not FILES or not os.path.exists(REC):
        return 0

    # Schema: recfix prints its own `file: line: error` text on stderr.
    recfix = shutil.which("recfix")
    if not recfix:
        print(f"{REC}:1: recfix not found - fix: brew install recutils")
        return 0
    run = subprocess.run([recfix, "--check", REC], capture_output=True, text=True)
    if run.returncode:
        err = " ".join(run.stderr.split())
        print(f"{REC}:1: recfix --check failed: {err} - fix: correct the record, then recfix --check {REC}")
        return 0

    # Learning path and freshness: the generator validates the Requires lines,
    # then compares its charts with the files on disk, one stderr line each.
    run = subprocess.run([sys.executable, "dev_tools.py", "--check"], capture_output=True, text=True)
    for line in run.stderr.splitlines():
        if line.startswith("dev_tools.rec: "):
            print(f"{REC}:1: {line.removeprefix('dev_tools.rec: ')} - fix: edit the Requires, Level or Tier line")
        elif line.endswith("- fix: ./dev_tools.py"):
            svg = line.split(" ", 1)[0]
            print(f"{svg}:1: stale against {REC} - fix: ./dev_tools.py")
        elif line.startswith("dev_tools.py: "):
            print(f"dev_tools.py:1: {line.removeprefix('dev_tools.py: ')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
