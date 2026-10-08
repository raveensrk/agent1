#!/usr/bin/env python3
"""Inventory a directory before its rules are determinized. Read-only.

    python3 inventory.py [DIR]        default: the current directory
    python3 inventory.py --selftest   this script's own check
    python3 inventory.py -h|--help    this text

Prints the git root, the instruction files and the docs they read at session
start with line counts, the checks that already exist, the guards and git hooks
already wired, and which agent harnesses are installed. Classifying each rule is
judgement; this script is the repeatable discovery that comes first.

Example: python3 inventory.py ~/repos/agent2

Runs git and ~/repos/agent1/harness/lint.py --list; writes nothing outside a
temp dir. Exit 0; --selftest exits nonzero on a failed check.
"""
from __future__ import annotations

import glob
import os
import re
import subprocess
import sys

AGENT1 = os.path.expanduser("~/repos/agent1")
AGENT2 = os.path.expanduser("~/repos/agent2")
LINT = os.path.join(AGENT1, "harness", "lint.py")
NAMES = ("AGENTS.md", "CLAUDE.md", "CLAUDE.MD")
HARNESSES = {
    "claude": "~/.claude",
    "codex": "~/.codex",
    "pi": "~/.pi",
    "cursor": "~/.cursor",
    "gemini": "~/.gemini",
    "opencode": "~/.config/opencode",
}
LINK = re.compile(r"\]\(([^)\s]+)\)")
IMPORT = re.compile(r"@(~?/[^\s`]+)")


def read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return ""


def run(args: list[str], cwd: str) -> str:
    try:
        proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout if proc.returncode == 0 else ""


def git_root(target: str) -> str:
    return run(["git", "rev-parse", "--show-toplevel"], target).strip()


def instructions(target: str, root: str) -> list[str]:
    """Instruction files in the target and the repo root, plus the docs they read."""
    found: list[str] = []
    for base in (target, root):
        if not base:
            continue
        for name in NAMES:
            path = os.path.join(base, name)
            if os.path.isfile(path) and path not in found:
                found.append(path)
    for path in list(found):
        links = LINK.findall(read(path)) + [i.lstrip("@") for i in IMPORT.findall(read(path))]
        for link in links:
            if link.startswith(("http", "mailto:", "#")):
                continue
            doc = os.path.normpath(os.path.join(os.path.dirname(path), os.path.expanduser(link)))
            if os.path.isfile(doc) and doc not in found:
                found.append(doc)
    return found


def guards(root: str) -> list[str]:
    found: list[str] = []
    for pattern in (
        os.path.join(AGENT1, "harness", "guards", "*.py"),
        os.path.join(AGENT2, "harness", "guards", "*.py"),
        os.path.join(root or ".", "scripts", "guards", "*.py"),
    ):
        found += sorted(glob.glob(pattern))
    return found


def hooks(root: str) -> list[str]:
    if not root:
        return []
    out = []
    for scope in ("--local", "--global"):
        value = run(["git", "config", scope, "--get", "core.hooksPath"], root).strip()
        out.append(f"  core.hooksPath ({scope[2:]}): {value or 'unset'}")
    local = os.path.join(root, ".githooks")
    if os.path.isdir(local):
        names = sorted(n for n in os.listdir(local) if not n.endswith(".sample"))
        out.append(f"  {local}: {', '.join(names) or 'empty'}")
    return out


def report(target: str) -> str:
    target = os.path.realpath(os.path.expanduser(target or "."))
    root = git_root(target)
    lines = [f"directory: {target}", f"git root:  {root or 'none - no git hook can be installed'}"]
    lines.append("instruction files:")
    for path in instructions(target, root):
        lines.append(f"  {len(read(path).splitlines()):5d} lines  {path}")
    lines.append("checks that already exist:")
    listing = run([sys.executable, LINT, "--list"], root or target).splitlines()
    lines += [f"  {line}" for line in listing] or ["  none found (is ~/repos/agent1 present?)"]
    lines.append("guards:")
    lines += [f"  {path}" for path in guards(root)] or ["  none"]
    lines.append("git hooks:")
    lines += hooks(root) or ["  none - not a git repo"]
    present = [name for name, path in HARNESSES.items() if os.path.isdir(os.path.expanduser(path))]
    lines.append(f"harnesses installed: {', '.join(present) or 'none'}")
    return "\n".join(lines)


def selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "docs"))
        with open(os.path.join(tmp, "AGENTS.md"), "w") as fh:
            fh.write("# Agents\n\nRead [docs/conventions.md](docs/conventions.md).\n")
        with open(os.path.join(tmp, "docs", "conventions.md"), "w") as fh:
            fh.write("# Conventions\n")
        found = instructions(tmp, "")
        assert found == [os.path.join(tmp, "AGENTS.md"),
                         os.path.join(tmp, "docs", "conventions.md")], found
        text = report(tmp)
        for section in ("instruction files:", "checks that already exist:", "harnesses installed:"):
            assert section in text, text
        assert "3 lines" in text and "1 lines" in text, text
    print("inventory selftest ok")
    return 0


if __name__ == "__main__":
    if {"-h", "--help"} & set(sys.argv[1:]):
        print(__doc__)
        sys.exit(0)
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    print(report(sys.argv[1] if len(sys.argv) > 1 else "."))
