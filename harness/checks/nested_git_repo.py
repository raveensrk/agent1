#!/usr/bin/env python3
# harness-check: {"id": "nested_git_repo", "applies": ["*"], "quadrant": "feedback/computational"}
"""My repos never hold another git repo, and never a symlink to one.

The user's rule, verbatim: "Never use nested git repo for my projects. The repo
that i clone from others from the internet can have nested repo because those
are not mine and this rule does not apply." So this check is about the repos
that are his: a `.git` in any directory below the repo root is a finding unless
the path is on the allowlist that records third-party clones. The rule is
public, so the check lives here; the allowlist names this machine's clones, so
it stays in the private repo (agent2) and the check runs without one when that
file is absent.

A symlink that points at a repo is always a finding, with no allowlist: the
link hides which checkout is real, and `income_tax_fy_2025_2026/ledger ->
~/repos/ledger` is the shape that motivated it. A link in a plain folder, where
no repo owns it and no check run reaches it, is the walker's job in lint.py.

Sibling rule: lint.py walks nested repos and prints their findings as warnings,
never as findings, and never changes the exit code - a vendored checkout is not
ours to fix. This check is the other half: a nested repo inside MY repo is the
mistake itself.

Remedy, printed with each finding: move the checkout out of the repo, or, when
it is a clone from the internet, record it in nested_repo_allow.txt.

    nested_git_repo.py FILE...      (or paths on stdin)
"""
from __future__ import annotations

import fnmatch
import os
import sys

REPOS = os.path.expanduser("~/repos")
ALLOW = os.path.join(REPOS, "agent2", "harness", "data", "nested_repo_allow.txt")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".build", ".mypy_cache"}
LINK_DEPTH = 4

# Paths arrive on stdin from the dispatcher, or as arguments when run by hand.
FILES = sys.argv[1:]
if not FILES and not sys.stdin.isatty():
    FILES = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]


def allow_patterns() -> list[str]:
    """Globs relative to the repo root, one per line, `#` comments ignored."""
    try:
        with open(ALLOW, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return []
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def nested_in(root: str, path: str) -> str | None:
    """The first directory between ROOT and PATH that carries its own .git.

    The dispatcher runs each check with cwd set to the repo root it is checking,
    so when that root IS the nested repo this finds nothing - the outer run is
    the only one that reports it.
    """
    root = root.rstrip("/")
    here = os.path.dirname(os.path.realpath(path))
    while here.startswith(root + "/"):
        if os.path.exists(os.path.join(here, ".git")):
            return here
        here = os.path.dirname(here)
    return None


def linked_repos(root: str) -> list[tuple[str, str]]:
    """(link, target) for every symlink below ROOT that points at a git repo.

    Walked rather than read from the file list, because a symlink to a directory
    is not a file: the dispatcher's list never contains one. The caller must
    pass a real repo root; `main` checks that before calling.
    """
    found: list[tuple[str, str]] = []
    base = root.rstrip("/").count("/")
    for here, dirs, files in os.walk(root):
        if here.count("/") - base >= LINK_DEPTH:
            dirs[:] = []
        else:
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in list(dirs) + files:
            path = os.path.join(here, name)
            if os.path.islink(path) and os.path.isdir(path) and os.path.exists(os.path.join(path, ".git")):
                found.append((path, os.path.realpath(path)))
    return found


def main() -> int:
    root = os.getcwd()
    patterns = allow_patterns()
    seen: set[str] = set()
    # The dispatcher falls back to the working directory when the edited files
    # are in no repo at all, and walking that root would mean walking the home
    # directory: a trashed link is not project content. So the walk only runs
    # where a repo root is really the root.
    walked = linked_repos(root) if os.path.exists(os.path.join(root, ".git")) else []
    for link, target in sorted(walked):
        print(
            f"{link}:1: symlink to a git repo: {os.path.relpath(link, root)} -> {target} - "
            f"fix: rm {link} (work in the repo itself, or clone it where it belongs; "
            "a link to a repo is never allowed here)"
        )
    for path in sorted(FILES):
        if not path:
            continue
        nested = nested_in(root, path)
        if not nested or nested in seen:
            continue
        seen.add(nested)
        rel = os.path.relpath(nested, root)
        if any(fnmatch.fnmatch(rel, pattern) for pattern in patterns):
            continue
        print(
            f"{nested}:1: nested git repo: {rel} is its own repo inside this one - "
            f"fix: move it out of the repo, or if it is a clone from the internet say so: "
            f"echo '{rel}' >> {ALLOW}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
