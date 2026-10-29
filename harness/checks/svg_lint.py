#!/usr/bin/env python3
# harness-check: {"id": "svg_lint", "applies": ["*.svg"], "quadrant": "feedback/computational"}
"""Every SVG an agent writes must parse and pass svglint.

Caught live: prompt-collection/design/mockup.svg had `y="571"width="1.5"` twice,
a missing space between attributes. That is not XML, so a browser refuses the
whole file, and nothing said so until a human ran a linter by hand.

Two passes per file. xmllint first: it names the line of a parse error, where
svglint only reports "Attribute 'width' has no space in starting". Then svglint
(through npx, cached after the first run) for its rules, with the file's own
`.svglintrc.js` when the repo has one. svglint gives no line, so its findings
land on line 1.

    svg_lint.py FILE...      (or paths on stdin)
"""
import re
import shutil
import subprocess
import sys

# Paths arrive on stdin from the dispatcher, or as arguments when run by hand.
FILES = sys.argv[1:]
if not FILES and not sys.stdin.isatty():
    FILES = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]

XMLLINT_LINE = re.compile(r"^(?P<path>.+?):(?P<line>\d+): (?P<msg>.+)$")
# svglint prints "  x <rule> <message>" under each failing file.
SVGLINT_FINDING = re.compile(r"^\s+x (?P<msg>.+)$")
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def xmllint(path: str) -> list[str]:
    """Parse errors as findings, one per line number."""
    result = subprocess.run(["xmllint", "--noout", path], capture_output=True, text=True, timeout=30)
    if result.returncode == 0:
        return []
    out, seen = [], set()
    for line in result.stderr.splitlines():
        match = XMLLINT_LINE.match(line)
        if not match or match["line"] in seen:
            continue
        seen.add(match["line"])
        out.append(f"{path}:{match['line']}: not valid XML: {match['msg'].strip()}; "
                   f"fix: repair line {match['line']}, then run xmllint --noout {path}")
    return out or [f"{path}:1: not valid XML; fix: run xmllint --noout {path}"]


def svglint(path: str) -> list[str]:
    """svglint's rule findings, on line 1 since it reports none."""
    result = subprocess.run(["npx", "-y", "svglint@3", "--ci", path],
                            capture_output=True, text=True, timeout=120)
    if result.returncode == 0:
        return []
    out = []
    for line in ANSI.sub("", result.stdout).splitlines():
        match = SVGLINT_FINDING.match(line)
        if match and not line.lstrip().startswith(f"x {path}"):
            out.append(f"{path}:1: svglint: {match['msg'].strip()}; fix: run npx svglint {path}")
    return out


if not shutil.which("xmllint"):
    sys.exit("svg_lint: xmllint not found")
for path in FILES:
    found = xmllint(path)
    # A file that does not parse would only repeat the same error under svglint.
    if not found and shutil.which("npx"):
        found = svglint(path)
    for finding in found:
        print(finding)
