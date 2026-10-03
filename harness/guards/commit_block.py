#!/usr/bin/env python3
"""commit block: an agent never commits.

Three ways in, one decision:

    commit_block.py --git pre-commit     git hook mode, installed globally
    commit_block.py                      harness hook mode: hook JSON on stdin
    commit_block.py --check "CMD"        one command, for tests and one-liners

The hook mode speaks the contract Claude Code, Codex, Cursor and Gemini CLI
already use: JSON on stdin, exit 2 blocks the tool call, stderr is the reason
the model reads. pi and opencode run their own adapter and call --check.

The git half is harness/githooks, made global with
`git config --global core.hooksPath`. It denies any commit that reaches git
unless AGENT1_COMMIT=1, which only the user's own commit path sets.

Every block prints the replacement. A bare no sends the next attempt down the
same dead end.
"""
from __future__ import annotations

import json
import os
import re
import sys

OVERRIDE = "AGENT1_COMMIT"

# Subcommands that create or rewrite a commit.
BLOCKED = {"commit", "commit-tree", "merge", "rebase", "cherry-pick", "revert", "am"}
# Subcommands that move a commit to a remote.
PUSHED = {"push"}

# git options that take a separate value, so the next word is not the subcommand.
VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}

COMMIT_FIX = (
    "An agent never commits. Stage the work and stop:\n"
    "  git add -A\n"
    "Then tell the user the change is ready for review. The user reviews the\n"
    "staged diff and commits it with AGENT1_COMMIT=1, which only their own\n"
    "commit path sets."
)
PUSH_FIX = (
    "An agent never pushes. Local commits are the user's to make and to send:\n"
    "  git log --oneline -5\n"
    "Then tell the user the branch is ready to push."
)
HOOK_FIX = (
    "An agent never commits, and this one did not carry the human override.\n"
    "Stage the work with `git add -A` and tell the user it is ready for review.\n"
    "The user commits with:\n"
    "  AGENT1_COMMIT=1 git commit\n"
    "(the lazygit commit key does this for them)"
)
BROKEN_FIX = (
    "commit_block could not read the hook payload, so it fails closed rather\n"
    "than let a commit through unwatched. Check the harness hook wiring -\n"
    "Claude Code, Codex, Cursor and Gemini CLI all send JSON on stdin - and\n"
    "test it by hand:\n"
    "  python3 ~/repos/agent1/harness/guards/commit_block.py --check 'git commit'"
)


def git_args(command: str) -> list[list[str]]:
    """Every `git ...` argv in a shell command.

    ponytail: quoted spans are dropped, not parsed, so `bash -c "git commit"`
    is invisible here. The git hook is the backstop for that shape.
    """
    bare = re.sub(r"'[^']*'", "''", command)
    bare = re.sub(r'"[^"]*"', '""', bare)
    out = []
    for segment in re.split(r"\|\||&&|[;|\n]", bare):
        words = segment.split()
        for i, word in enumerate(words):
            if os.path.basename(word) == "git":
                out.append(words[i + 1 :])
    return out


def subcommand(argv: list[str]) -> str:
    """The git subcommand, skipping options and their values."""
    i = 0
    while i < len(argv):
        word = argv[i]
        if word in VALUE_OPTS:
            i += 2
        elif word.startswith("-"):
            i += 1
        else:
            return word
    return ""


def decide(command: str) -> str | None:
    """The block message for a shell command, or None to allow it."""
    for argv in git_args(command):
        joined = " ".join(argv).lower()
        # A redirected hooks path is a bypass of the git half of this block.
        if "core.hookspath" in joined:
            return f"Blocked: redirecting core.hooksPath disables the commit block.\n{COMMIT_FIX}"
        sub = subcommand(argv)
        if sub in BLOCKED:
            return f"Blocked: git {sub}.\n{COMMIT_FIX}"
        if sub in PUSHED:
            return f"Blocked: git {sub}.\n{PUSH_FIX}"
    return None


def command_from_payload(payload: object) -> str:
    """The shell command in a hook payload, or "" when it carries none.

    Shapes seen in the wild:

        Claude Code, Codex, Gemini   {"tool_name": "Bash", "tool_input": {"command": "..."}}
        Cursor beforeShellExecution  {"command": "...", "cwd": "..."}

    No deep scan: a payload without one of these keys is not a shell call, and
    guessing from arbitrary text would block an edit that merely quotes a command.
    """
    if not isinstance(payload, dict):
        return ""
    if isinstance(payload.get("command"), str):
        return payload["command"]
    for key in ("tool_input", "input", "args", "arguments", "params"):
        found = command_from_payload(payload.get(key))
        if found:
            return found
    return ""


def block(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--check":
        command = " ".join(argv[1:])
        return block(decide(command)) if decide(command) else 0

    if argv and argv[0] == "--git":
        hook = argv[1] if len(argv) > 1 else "pre-commit"
        if os.environ.get(OVERRIDE) == "1":
            return 0
        return block(HOOK_FIX if hook == "pre-commit" else PUSH_FIX)

    raw = sys.stdin.read()
    if not raw.strip():
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return block(BROKEN_FIX)
    command = command_from_payload(payload)
    if not command:
        return 0
    return block(decide(command)) if decide(command) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
