#!/usr/bin/env python3
# harness-check: {"id": "skill_frontmatter", "applies": ["**/SKILL.md"], "quadrant": "feedback/computational"}
"""Every SKILL.md opens with YAML frontmatter carrying name and description.

A skill is discovered and invoked by its frontmatter. On 04 Oct 2026 a markdown
sweep with a mdformat that did not know frontmatter rewrote 15 SKILL.md headers
into a setext heading - `name`, `description`, `allowed-tools` and
`argument-hint` all collapsed into one line of prose - and nothing caught it:
the damaged files were still valid markdown, still mdformat-clean, and every
other check passed. This is the signal that was missing.

It also holds the convention the skills README states: the directory names the
skill, so `skills/todo/SKILL.md` carries `name: todo`.

    skill_frontmatter.py FILE...      (or paths on stdin)
"""
from __future__ import annotations

import os
import re
import sys

BLOCK = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|$)", re.S)
NAME = re.compile(r"^name:\s*(.+?)\s*$", re.M)
DESCRIPTION = re.compile(r"^description:\s*\S", re.M)


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def main() -> int:
    files = sys.argv[1:]
    if not files and not sys.stdin.isatty():
        files = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]

    for path in files:
        try:
            text = open(path, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError) as err:
            print(f"{path}:1: cannot read: {err}", file=sys.stderr)
            return 2

        directory = os.path.basename(os.path.dirname(os.path.abspath(path)))
        block = BLOCK.match(text)
        if not block:
            print(
                f"{path}:1: no YAML frontmatter - a skill without one has no name to call it by "
                f"- fix: add --- / name: {directory} / description: <when to use it> / --- at line 1"
            )
            continue

        body = block.group(1)
        name = NAME.search(body)
        if not name:
            print(f"{path}:1: frontmatter has no name - fix: add name: {directory}")
        elif unquote(name.group(1)) != directory:
            print(
                f"{path}:1: name {unquote(name.group(1))!r} does not match the directory "
                f"{directory!r} - fix: rename one so they agree, the directory is the skill name"
            )
        if not DESCRIPTION.search(body):
            print(
                f"{path}:1: frontmatter has no description - fix: add description: "
                "<what it does, and when to use it>"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
