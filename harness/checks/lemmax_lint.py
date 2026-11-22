#!/usr/bin/env python3
# harness-check: {"id": "lemmax_lint", "applies": ["*.org"], "quadrant": "feedback/computational"}
"""A requirements file that opts in keeps requirements.org's format (RT-10).

For each candidate .org file whose header has #+LEMMAX_TESTS:, or in a repo
with lemmax/config.eld, this runs
`lemmax lint --no-tests FILE` and turns each finding into path:line: message.
--no-tests, because the test command may take 60 s, too slow for every edit.
An org file that does not opt in gets no finding.

    lemmax_lint.py FILE...      (or paths on stdin)
"""
# lemma: RT-10
import os
import re
import subprocess
import sys

LEMMAX = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "requirements", "scripts", "lemmax", "lemmax")
OPTED = re.compile(r"^#\+LEMMAX_TESTS:", re.MULTILINE)
FINDING = re.compile(r"^lemmax: ([^:]+):(\d+): (.*)$")

files = sys.argv[1:]
if not files and not sys.stdin.isatty():
    files = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]

def has_config(path):
    """Whether the git repo that holds PATH has lemmax/config.eld."""
    d = os.path.dirname(os.path.abspath(path))
    while True:
        if os.path.exists(os.path.join(d, ".git")):
            return os.path.isfile(os.path.join(d, "lemmax", "config.eld"))
        parent = os.path.dirname(d)
        if parent == d:
            return False
        d = parent


for path in files:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            if not OPTED.search(fh.read()) and not has_config(path):
                continue
    except OSError:
        continue
    run = subprocess.run([LEMMAX, "lint", "--no-tests", path], capture_output=True, text=True)
    for line in run.stderr.splitlines():
        found = FINDING.match(line)
        if found:
            print(f"{found.group(1)}:{found.group(2)}: {found.group(3)}")
