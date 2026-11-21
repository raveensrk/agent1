#!/usr/bin/env python3
# harness-check: {"id": "reqtrace_lint", "applies": ["*.org"], "quadrant": "feedback/computational"}
"""A requirements file that opts in keeps requirements.org's format (RT-10).

For each candidate .org file whose header has #+REQTRACE_TESTS:, this runs
`reqtrace lint --no-tests FILE` and turns each finding into path:line: message.
--no-tests, because the test command may take 60 s, too slow for every edit.
An org file that does not opt in gets no finding.

    reqtrace_lint.py FILE...      (or paths on stdin)
"""
import os
import re
import subprocess
import sys

REQTRACE = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "reqtrace", "reqtrace")
OPTED = re.compile(r"^#\+REQTRACE_TESTS:", re.MULTILINE)
FINDING = re.compile(r"^reqtrace: ([^:]+):(\d+): (.*)$")

files = sys.argv[1:]
if not files and not sys.stdin.isatty():
    files = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]

for path in files:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            if not OPTED.search(fh.read()):
                continue
    except OSError:
        continue
    run = subprocess.run([REQTRACE, "lint", "--no-tests", path], capture_output=True, text=True)
    for line in run.stderr.splitlines():
        found = FINDING.match(line)
        if found:
            print(f"{found.group(1)}:{found.group(2)}: {found.group(3)}")
