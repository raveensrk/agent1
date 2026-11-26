#!/usr/bin/env python3
# harness-check: {"id": "lemmax_lint", "applies": ["*.org"], "quadrant": "feedback/computational"}
"""Lint each edited .org file of a repo whose theories opt in.

A repo opts in with a tracked .org file holding #+PROPERTY: LEMMAX_TESTS.
For each such file it runs lmx lint --no-tests FILE and prints each finding
as path:line: message. With no lmx on PATH there is nothing to check. Exit 0.

    lemmax_lint.py FILE...      (or paths on stdin)
"""
import os
import re
import shutil
import subprocess
import sys

OPT_IN = r"^#\+PROPERTY:[[:space:]]+LEMMAX_TESTS\+?([[:space:]]|$)"
FINDING = re.compile(r"^lmx: ([^:]*):([0-9]*): (.*)$")


def opted_in(root):
    r = subprocess.run(["git", "-C", root, "grep", "--cached", "-q", "-E", OPT_IN, "--", "*.org"],
                       capture_output=True)
    return r.returncode == 0


def main(files):
    if not shutil.which("lmx"):
        return 0
    if not files and not sys.stdin.isatty():
        files = [l.strip() for l in sys.stdin if l.strip()]
    for f in files:
        if not os.path.isfile(f):
            continue
        top = subprocess.run(["git", "-C", os.path.dirname(os.path.abspath(f)), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True)
        if top.returncode != 0 or not opted_in(top.stdout.strip()):
            continue
        r = subprocess.run(["lmx", "lint", "--no-tests", f], capture_output=True, text=True)
        for line in r.stderr.splitlines():
            m = FINDING.match(line)
            if m:
                print(f"{m.group(1)}:{m.group(2)}: {m.group(3)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
