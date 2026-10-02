#!/usr/bin/env python3
# harness-check: {"id": "markdown_bare_path", "applies": ["*.md", "!**/archive/**", "!**/deck/**", "!**/content/**", "!**/notes/**"], "quadrant": "feedback/computational"}
"""File paths in markdown prose must be markdown links.

common.md: a path is written as [name](path), not as bare text. Fenced code
blocks, indented blocks and inline code spans are skipped - a path inside a
command example is not prose. Directories are skipped too: the rule is about
files you can open. Notes and content archives are out of scope; the rule is
about what the agent writes.

    markdown_bare_path.py FILE...      (or paths on stdin)
"""
from __future__ import annotations

import os
import re
import sys

FILES = sys.argv[1:]
if not FILES and not sys.stdin.isatty():
    FILES = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]

# A path only counts when it is the whole token, so a link target or a path
# inside a word does not trip it. Trailing punctuation is stripped afterwards.
BARE = re.compile(r"(?<![\w(`/~-])(~|/Users/raveen_kumar_personal)/[\w./~-]+")
LINK = re.compile(r"!?\[[^\]]*\]\([^)]*\)")
CODE = re.compile(r"`[^`]*`")
TRAILING = ".,;:!?)-"


def prose(line: str) -> str:
    line = LINK.sub(" ", line)
    line = CODE.sub(" ", line)
    return line.split("<!--")[0]


def worth_reporting(target: str) -> bool:
    """A directory is fine as prose; the rule is about files you can open."""
    if target.endswith("/"):
        return False
    return not os.path.isdir(os.path.expanduser(target))


def frontmatter_end(lines: list[str]) -> int:
    """Last line of a leading YAML block; frontmatter is metadata, not prose."""
    if not lines or lines[0].strip() != "---":
        return 0
    for number, line in enumerate(lines[1:], 2):
        if line.strip() in ("---", "..."):
            return number
    return len(lines)


def main() -> int:
    for path in FILES:
        try:
            text = open(path, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        lines = text.splitlines()
        skip_until = frontmatter_end(lines)
        fenced = False
        for number, line in enumerate(lines, 1):
            if number <= skip_until:
                continue
            if line.lstrip().startswith("```"):
                fenced = not fenced
                continue
            # Indented blocks are code too, and a path in a command example is
            # not prose.
            if fenced or line.startswith("    ") or line.startswith("\t"):
                continue
            if "lint:ignore" in line:
                continue  # an explicit, greppable escape hatch, like `# rubocop:disable`
            for match in BARE.finditer(prose(line)):
                target = match.group(0).rstrip(TRAILING)
                if not target or not worth_reporting(target):
                    continue
                name = target.rstrip("/").rsplit("/", 1)[-1] or target
                print(
                    f"{path}:{number}: bare path in prose: {target} - "
                    f"fix: [{name}]({target})"
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
