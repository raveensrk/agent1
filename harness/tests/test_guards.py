#!/usr/bin/env python3
"""Checks for harness/guards. Run:

    python3 harness/tests/test_guards.py      # no pytest needed
    pytest harness/tests/test_guards.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
GUARD = os.path.join(os.path.dirname(HERE), "guards", "commit_block.py")


def load_guard():
    spec = importlib.util.spec_from_file_location("commit_block", GUARD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BLOCKED = [
    "git commit -m 'x'",
    "git commit --no-verify -m 'x'",
    "git -C /tmp/repo commit -m x",
    "git --no-pager commit",
    "cd ~/repos/agent1 && git commit -m x",
    "/usr/bin/git commit-tree HEAD^{tree}",
    "git merge main",
    "git rebase -i HEAD~3",
    "git cherry-pick abc123",
    "git revert HEAD",
    "git am fix.patch",
    "git push",
    "git push origin main",
    "git -c core.hooksPath=/dev/null commit",
    "git config core.hooksPath /tmp/hooks",
    "git config --global core.hooksPath /tmp/hooks",
]

ALLOWED = [
    "git status",
    "git diff --cached",
    "git log --oneline -5",
    "git add -A",
    "git stash list",
    "git branch --show-current",
    "git rev-parse HEAD",
    "git show HEAD",
    "git merge-base main HEAD",
    "git commit-tree-not-a-real-subcommand",  # only the exact subcommand blocks
    "rg -n 'git commit' README.md",
    'echo "git push is the user\'s call"',
]


def run(args, stdin="", env_override=None):
    env = dict(os.environ)
    env.pop("AGENT1_COMMIT", None)
    if env_override is not None:
        env["AGENT1_COMMIT"] = env_override
    return subprocess.run(
        [sys.executable, GUARD, *args], input=stdin, capture_output=True, text=True, env=env
    )


def test_commands_that_make_or_move_a_commit_block():
    guard = load_guard()
    for command in BLOCKED:
        message = guard.decide(command)
        assert message, f"should block: {command}"
        assert "Blocked" in message, message


def test_the_same_commands_without_git_are_allowed():
    guard = load_guard()
    for command in ALLOWED:
        assert guard.decide(command) is None, f"should allow: {command}"


def test_every_block_prints_a_replacement():
    guard = load_guard()
    assert "git add -A" in guard.decide("git commit -m x")
    assert "git log --oneline" in guard.decide("git push")
    assert "AGENT1_COMMIT=1" in guard.decide("git config core.hooksPath /tmp/h")


def test_git_hook_denies_then_the_human_override_passes():
    denied = run(["--git", "pre-commit"])
    assert denied.returncode == 2, denied.stderr
    assert "AGENT1_COMMIT=1" in denied.stderr, denied.stderr

    allowed = run(["--git", "pre-commit"], env_override="1")
    assert allowed.returncode == 0, allowed.stderr
    assert allowed.stderr == "", allowed.stderr


def test_harness_payloads_for_the_shapes_claude_codex_cursor_and_gemini_send():
    claude = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git commit -m 'sneak'"}})
    cursor = json.dumps({"command": "git push", "cwd": "/tmp"})

    for payload in (claude, cursor):
        result = run([], stdin=payload)
        assert result.returncode == 2, f"{payload}: {result.stdout}"
        assert result.stderr.strip(), payload

    allowed = run([], stdin=json.dumps({"tool_input": {"command": "git status"}}))
    assert allowed.returncode == 0, allowed.stderr

    # A payload with no shell command is not a shell call.
    assert run([], stdin=json.dumps({"tool_name": "Read", "tool_input": {"path": "/x"}})).returncode == 0
    # A payload that cannot be read fails closed, never silently open.
    assert run([], stdin="{not json").returncode == 2
    assert run([], stdin="").returncode == 0


if __name__ == "__main__":
    failures = 0
    for name, func in sorted(globals().items()):
        if not name.startswith("test_") or not callable(func):
            continue
        try:
            func()
        except AssertionError as e:
            failures += 1
            print(f"FAIL {name}: {e}")
        else:
            print(f"ok   {name}")
    sys.exit(1 if failures else 0)
