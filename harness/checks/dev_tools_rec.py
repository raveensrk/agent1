#!/usr/bin/env python3
# harness-check: {"id": "dev_tools_rec", "applies": ["dev_tools.rec"], "quadrant": "feedback/computational"}
"""dev_tools.rec obeys its schema and its learning path.

dev_tools.rec is the one file that lists the tools, as a draw_graph document:
Node records for the tools, Edge records for the learning path, Group records
for the boxes. recfix decides the schema (%type, %mandatory, %allowed);
draw_graph check decides what recfix cannot see - edge ends that name real
tools, no prerequisite above its tool's Level or Tier, no loops, no edge
implied through another - from the file's own %graph lines.

Runs once per repo however many files changed: the findings are about the
data, not about one path.

    dev_tools_rec.py FILE...      (or paths on stdin)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

REC = "dev_tools.rec"
INSTALL = "cd ~/repos/draw_graph/app && cargo tauri build --no-bundle && cp ../target/release/draw_graph ~/.local/bin/"

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

    # The graph rules: draw_graph prints `FILE:LINE: SUBJECT: PROBLEM - fix: HOW`
    # on stdout, already the finding shape; a count goes to stderr.
    draw_graph = shutil.which("draw_graph")
    if not draw_graph:
        print(f"{REC}:1: draw_graph not found - fix: {INSTALL}")
        return 0
    run = subprocess.run([draw_graph, "check", REC], capture_output=True, text=True)
    for line in run.stdout.splitlines():
        print(line if " - fix: " in line else f"{line} - fix: edit {REC} in draw_graph, or by hand")
    if run.returncode not in (0, 1):
        print(f"{REC}:1: draw_graph check failed: {' '.join(run.stderr.split())} - fix: draw_graph check {REC}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
