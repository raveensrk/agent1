#!/usr/bin/env python3
# harness-check: {"id": "no_symlinks", "applies": ["*"], "quadrant": "feedback/computational"}
"""No symlink inside a repo - warn first, find another way.

Raveen's rules, verbatim: "No git repo should have symlinks inside them. this
is a global rule." and "Warn me when using symlinks for anything. Find
alternative way to solve the problem." The rule text lives in common.md's
Working style; this check decides the repo half.

Two scans, because the incident this check exists for had both shapes. On
2026-10-06 agent1's install.py wrote eight absolute-path links into
`~/.pi/agent/extensions`, which is a directory link into `~/dot` - so eight
untracked links appeared in the dot repo's git status and stayed invisible
until someone looked. Both shapes are findings now:

- the working tree, walked: catches untracked links a tool or a session just
  created, the shape `git ls-files` never sees;
- the index, `git ls-files -s`: catches a committed link, the shape a walk of
  a dirty tree could miss.

`SKIP_DIRS` is shared with nested_git_repo.py, and a path under any of them is
exempt in both scans: a committed `diagrams/.venv/bin/python` in the third-party
Examples clone is not this rule's job. There is no allowlist yet; if a real
need appears, mirror the private `nested_repo_allow.txt` pattern.

The warning half of the rule is prose, not a check: before creating any link,
name the alternative you chose instead - a copy installed by a script, a
package or settings declaration, or the real file.

Remedy, printed with each finding: delete the link and use the real target, or
install a copy, or declare the source as a package (pi reads
`"~/repos/agent1"` from settings.json `packages` with no link at all).

    no_symlinks.py FILE...      (or paths on stdin)
"""
from __future__ import annotations

import os
import subprocess
import sys

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".build", ".mypy_cache"}
LINK_DEPTH = 4

# Paths arrive on stdin from the dispatcher, or as arguments when run by hand.
FILES = sys.argv[1:]
if not FILES and not sys.stdin.isatty():
    FILES = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]


def repo_root() -> str | None:
    """The repo root of cwd, or None when cwd is no repo at all."""
    if not os.path.exists(os.path.join(os.getcwd(), ".git")):
        return None
    return os.getcwd().rstrip("/") or "/"


def skipped(rel: str) -> bool:
    """True when any path segment of REL is in SKIP_DIRS (.git included)."""
    return any(part in SKIP_DIRS for part in rel.split(os.sep))


def tree_links(root: str) -> list[tuple[str, str]]:
    """(link, target) for every symlink below ROOT, outside SKIP_DIRS.

    Walked rather than read from the file list, because a symlink to a
    directory is not a file: the dispatcher's list never contains one. Depth
    matches nested_git_repo.py: past four levels a stray link is not project
    structure, it is noise.
    """
    found: list[tuple[str, str]] = []
    base = root.count("/")
    for here, dirs, files in os.walk(root):
        if here.count("/") - base >= LINK_DEPTH:
            dirs[:] = []
        else:
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in list(dirs) + files:
            path = os.path.join(here, name)
            rel = os.path.relpath(path, root)
            if skipped(rel):
                continue
            if os.path.islink(path):
                found.append((rel, os.readlink(path)))
    return found


def index_links(root: str) -> list[tuple[str, str]]:
    """(path, target) for every mode-120000 entry in the index, outside SKIP_DIRS.

    The blob of a tracked symlink holds its target text, so the target comes
    from `git cat-file` rather than from the working tree.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", root, "ls-files", "-s"], capture_output=True, text=True, timeout=60
        )
    except (OSError, subprocess.SubprocessError):
        return []
    out: list[tuple[str, str]] = []
    for line in proc.stdout.splitlines():
        mode, _blob, _stage, path = (line.split(None, 3) + ["" ])[:4]
        if mode != "120000" or skipped(path):
            continue
        target = subprocess.run(
            ["git", "-C", root, "cat-file", "blob", line.split()[1]],
            capture_output=True, text=True, timeout=60,
        ).stdout.strip()
        out.append((path, target))
    return out


def report(kind: str, rel: str, target: str) -> None:
    print(
        f"{os.path.join(os.getcwd(), rel)}:1: symlink in repo ({kind}): {rel} -> {target} - "
        "fix: rm the link and use the real path, or install a copy, or declare the source as a "
        "package (pi: settings.json packages \"~/repos/<repo>\" loads live with no link); "
        "warn and name the alternative before any link is created"
    )


def main() -> int:
    root = repo_root()
    if root is None:
        # The dispatcher falls back to the working directory when the edited
        # files are in no repo at all: no repo, no rule.
        return 0
    seen: set[str] = set()
    for rel, target in sorted(tree_links(root)):
        seen.add(rel)
        report("working tree", rel, target)
    for rel, target in sorted(index_links(root)):
        if rel in seen:
            continue
        report("tracked", rel, target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
