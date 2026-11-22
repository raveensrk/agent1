#!/usr/bin/env python3
# harness-check: {"id": "lemmax_lint", "applies": ["*.org"], "quadrant": "feedback/computational"}
# lemma: RT-10
"""A requirements file that opts in keeps requirements.org's format (RT-10).

For each candidate .org file whose header has #+LEMMAX_TESTS:, or in a repo
with lemmax/config.eld or a tracked *.setup file holding #+LEMMAX_TESTS:, this runs
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

LEMMAX = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "lemmax", "lemmax")
OPTED = re.compile(r"^#\+LEMMAX_TESTS:", re.MULTILINE)
FINDING = re.compile(r"^lemmax: ([^:]+):(\d+): (.*)$")

files = sys.argv[1:]
if not files and not sys.stdin.isatty():
    files = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]

def repo_root(path):
    """The git repo that holds PATH, or None."""
    d = os.path.dirname(os.path.abspath(path))
    while True:
        if os.path.exists(os.path.join(d, ".git")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


# lemma: 01a203e8-0c8b-713e-8f21-ffee439bcbb0
def has_setup(path):
    """Whether PATH's repo has a tracked *.setup file holding #+LEMMAX_TESTS:,
    as the global hooks decide: a file may opt in through #+SETUPFILE:."""
    root = repo_root(path)
    if not root:
        return False
    return subprocess.run(["git", "-C", root, "grep", "--cached", "-q", "-E", r"^#\+LEMMAX_TESTS:", "--", "*.setup"],
                          capture_output=True).returncode == 0


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
            if not OPTED.search(fh.read()) and not has_config(path) and not has_setup(path):
                continue
    except OSError:
        continue
    run = subprocess.run([LEMMAX, "lint", "--no-tests", path], capture_output=True, text=True)
    for line in run.stderr.splitlines():
        found = FINDING.match(line)
        if found:
            print(f"{found.group(1)}:{found.group(2)}: {found.group(3)}")
