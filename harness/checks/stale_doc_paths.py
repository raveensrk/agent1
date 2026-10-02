#!/usr/bin/env python3
# harness-check: {"id": "stale_doc_paths", "applies": ["*.md", "!**/archive/**", "!**/deck/**", "!**/content/**", "!**/notes/**"], "quadrant": "feedback/computational"}
"""Absolute /tmp/... paths in agent docs must exist on this machine.

Temporary files live under `~/tmp` here, but docs written on other machines
say `/tmp/explain/...`, and every future session follows the stale path into
`command not found` or a wrong write target. A `/tmp/...` path that does not
exist is a stale reference; `~/tmp/...` paths are skipped (home-relative is
the convention). Inline code spans are checked too - the stale references are
written as commands. A line containing `lint:ignore` is not reported. Historical
prose - archives, study notes, decks, site content - is out of scope, the same
exclusions `markdown_bare_path` uses: those files discuss `/tmp` as a Unix
concept, not as this machine's staging directory.

    stale_doc_paths.py FILE...      (or paths on stdin)
"""
from __future__ import annotations

import os
import re
import sys

# absolute /tmp path, not preceded by ~ or a word char, and not a relative
# `../tmp/...`: only a leading slash is absolute
PATH_RE = re.compile(r"(?<![\w~./])/tmp/[\w][\w./-]*")


def check(path: str) -> list[str]:
    findings = []
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return findings
    for number, line in enumerate(text.splitlines(), start=1):
        if "lint:ignore" in line:
            continue
        for match in PATH_RE.finditer(line):
            target = match.group(0)
            if os.path.exists(target):
                continue
            home = os.path.expanduser("~/tmp" + target[len("/tmp"):])
            findings.append(
                f"{path}:{number}: {target} does not exist on this machine - "
                f"use ~/tmp/... ({home})")
    return findings


def main() -> int:
    paths = sys.argv[1:] or [line.strip() for line in sys.stdin if line.strip()]
    for path in paths:
        for finding in check(path):
            print(finding)
    return 0


if __name__ == "__main__":
    sys.exit(main())