#!/usr/bin/env python3
# harness-check: {"id": "harness_doc_paths", "applies": ["*.md", "!**/archive/**", "!**/deck/**", "!**/content/**", "!**/notes/**"], "quadrant": "feedback/computational"}
"""A `harness/...` path named in an agent doc must exist in that repo.

Measured 2026-10-03: a file the harness spawned was deleted while the prose
still named it. Every command that reached the spawner returned only
`can't open file ... [Errno 2] No such file or directory` instead of running,
which reads like a shell mistake rather than a missing file, and eight calls in
that session went into finding out what the error was. A file the harness
spawns is named in prose exactly once, so a missing one is silent until
something calls it.
The rule is about `harness/...` and nothing else: those paths always resolve
against the repo that owns the doc, never against another repo or a skill
directory, so there is no cross-repo noise. `stale_doc_paths` covers absolute
`/tmp/...` paths and `markdown_bare_path` covers prose paths under `~` and
`/Users/raveen_kumar_personal`; this is the repo-relative case neither sees, and
it reads inline code spans because the motivating reference was written in one.

Absolute, home-relative and skill-relative paths are out of scope: a doc under
`skills/<name>/` says `scripts/foo.py` meaning its own directory, and that is
not a `harness/...` path.

    harness_doc_paths.py FILE...      (or paths on stdin)
"""
from __future__ import annotations

import os
import re
import sys

# A harness path only counts as the whole token, so a longer path that merely
# contains one, or a markdown link target, does not trip it.
PATH_RE = re.compile(r"(?<![\w/.-])harness/[\w./-]+")


def repo_root(path: str) -> str | None:
    """The nearest ancestor holding a `harness/` directory, or None."""
    current = os.path.dirname(os.path.realpath(path))
    while True:
        if os.path.isdir(os.path.join(current, "harness")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def check(path: str) -> list[str]:
    root = repo_root(path)
    if root is None:
        return []
    findings = []
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return findings
    for number, line in enumerate(text.splitlines(), start=1):
        if "lint:ignore" in line:
            continue
        for match in PATH_RE.finditer(line):
            target = match.group(0).rstrip(".,;:)")
            if os.path.exists(os.path.join(root, target)):
                continue
            findings.append(
                f"{path}:{number}: {target} does not exist in {root} - "
                f"restore the file, or drop the reference so the next spawn "
                f"does not die on a missing path")
    return findings


def main() -> int:
    paths = sys.argv[1:] or [line.strip() for line in sys.stdin if line.strip()]
    for path in paths:
        for finding in check(path):
            print(finding)
    return 0


if __name__ == "__main__":
    sys.exit(main())
