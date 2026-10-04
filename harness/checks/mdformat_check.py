#!/usr/bin/env python3
# harness-check: {"id": "mdformat_check", "applies": ["*.md"], "quadrant": "feedback/computational"}
"""Markdown must satisfy mdformat, pinned so it cannot mangle a file.

common.md pins the falsifier for the markup rule: `mdformat --check`. As
installed on this machine two traps sit under that bare command, both measured
on 04 Oct 2026:

  1. mdformat without the mdformat-frontmatter plugin does not know YAML
     frontmatter. It rewrote the header of all 15 skills/*/SKILL.md files into a
     setext heading, collapsing `name`, `description`, `allowed-tools`,
     `argument-hint` and `disable-model-invocation` into one line of prose.
  2. Without `number = true` it renumbers every ordered list to `1.`, which
     breaks any rules file a human reads as "step 3 of 5".

So the check runs the pinned binary - the pipx install that carries the plugin
- and refuses to report formatting findings at all when the plugin is absent.
A missing plugin is a broken check, not a finding: exit 2 with the command that
fixes it.

Scope: a file is checked only when a `.mdformat.toml` exists in its repo, found
by walking up from the file. mdformat's own behaviour is config-dependent -
without `number = true` it renumbers ordered lists, so a repo with no config has
no pinned invocation and the rule is not enforced there. Adding
`.mdformat.toml` to a repo opts it in.

    mdformat_check.py FILE...      (or paths on stdin)

MDFORMAT_BIN overrides the binary, for tests and for another machine.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

PINNED = os.path.expanduser("~/.local/bin/mdformat")
BATCH = 200

# mdformat wraps its message at 80 columns, and a long path moves the quote to
# the next line, so both "is not\nformatted." and "File\n\"path\"" are normal.
NOT_FORMATTED = re.compile(r'File\s+"([^"]+)"\s+is\s+not\s+formatted')


def binary() -> str | None:
    override = os.environ.get("MDFORMAT_BIN")
    if override:
        return override if os.path.exists(override) else None
    if os.path.exists(PINNED):
        return PINNED
    return shutil.which("mdformat")


def pinned_by_repo(path: str) -> bool:
    """True when a .mdformat.toml governs this file, walking up from it."""
    here = os.path.dirname(os.path.abspath(path))
    while True:
        if os.path.isfile(os.path.join(here, ".mdformat.toml")):
            return True
        parent = os.path.dirname(here)
        if parent == here:
            return False
        here = parent


def has_frontmatter_plugin(bin_path: str) -> bool:
    try:
        got = subprocess.run([bin_path, "--version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return "mdformat_frontmatter" in (got.stdout + got.stderr)


def main() -> int:
    files = sys.argv[1:]
    if not files and not sys.stdin.isatty():
        files = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]
    if not files:
        return 0

    files = [path for path in files if pinned_by_repo(path)]
    if not files:
        return 0

    bin_path = binary()
    if not bin_path:
        print(
            "mdformat is not installed: pipx install mdformat "
            "&& pipx inject mdformat mdformat-frontmatter",
            file=sys.stderr,
        )
        return 2

    if not has_frontmatter_plugin(bin_path):
        print(
            f"{bin_path} lacks the mdformat-frontmatter plugin, so it would rewrite "
            "SKILL.md frontmatter into a setext heading. "
            "fix: pipx inject mdformat mdformat-frontmatter",
            file=sys.stderr,
        )
        return 2

    offenders: list[str] = []
    for start in range(0, len(files), BATCH):
        batch = files[start : start + BATCH]
        try:
            got = subprocess.run(
                [bin_path, "--check", *batch], capture_output=True, text=True, timeout=300
            )
        except (OSError, subprocess.SubprocessError) as err:
            print(f"mdformat failed to run: {err}", file=sys.stderr)
            return 2
        if got.returncode not in (0, 1):
            print(f"mdformat exited {got.returncode}: {got.stderr.strip()}", file=sys.stderr)
            return 2
        offenders.extend(NOT_FORMATTED.findall(got.stdout + got.stderr))

    for path in offenders:
        print(f"{path}:1: not mdformat-clean - fix: {bin_path} {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
