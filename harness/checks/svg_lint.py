#!/usr/bin/env python3
# harness-check: {"id": "svg_lint", "applies": ["*.svg"], "quadrant": "feedback/computational"}
"""Every SVG an agent writes must parse, pass svglint and be Prettier-formatted.

Caught live: prompt-collection/design/mockup.svg had `y="571"width="1.5"` twice,
a missing space between attributes. That is not XML, so a browser refuses the
whole file, and nothing said so until a human ran a linter by hand.

Two passes per file. xmllint first: it names the line of a parse error, where
svglint only reports "Attribute 'width' has no space in starting". Then svglint
(through npx, cached after the first run) for its rules, with the file's own
`.svglintrc.js` when the repo has one. svglint gives no line, so its findings
land on line 1.

A file that passes both is then held to Prettier's XML plugin with `--check`.
Checks report, they never write, so the finding carries the `--write` command
and the agent runs it. Plain `npx -p` cannot find the plugin from the package
it adds; `npx -c` runs with both packages on the path, and works.

    svg_lint.py FILE...      (or paths on stdin)
"""
import os
import re
import shlex
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


PRETTIER = "prettier --plugin=@prettier/plugin-xml --parser=xml"
PRETTIER_NPX = ["npx", "-y", "-p", "prettier@3", "-p", "@prettier/plugin-xml@3", "-c"]


def prettier(paths: list[str]) -> list[str]:
    """One finding per file Prettier would reformat, with the command that does it."""
    if not paths:
        return []
    command = f"{PRETTIER} --check " + " ".join(shlex.quote(p) for p in paths)
    result = subprocess.run([*PRETTIER_NPX, command], capture_output=True, text=True, timeout=120)
    if result.returncode == 0:
        return []
    wanted = {os.path.realpath(p): p for p in paths}
    out = []
    for line in (result.stdout + result.stderr).splitlines():
        if not line.startswith("[warn] ") or line.startswith("[warn] Code style"):
            continue
        path = wanted.get(os.path.realpath(line[len("[warn] "):].strip()))
        if path:
            out.append(f"{path}:1: not formatted by Prettier; fix: npx -y -p prettier@3 "
                       f"-p @prettier/plugin-xml@3 -c '{PRETTIER} --write {path}'")
    if not out:
        sys.exit(f"svg_lint: prettier failed: {result.stderr.strip()[:300]}")
    return out


if not shutil.which("xmllint"):
    sys.exit("svg_lint: xmllint not found")
clean = []
for path in FILES:
    found = xmllint(path)
    # A file that does not parse would only repeat the same error under svglint.
    if not found and shutil.which("npx"):
        found = svglint(path)
    for finding in found:
        print(finding)
    if not found:
        clean.append(path)
# Formatting is judged only on files that are already valid.
if clean and shutil.which("npx"):
    for finding in prettier(clean):
        print(finding)
