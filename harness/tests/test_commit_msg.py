"""Tests for harness/githooks/commit-msg, through real `git commit` runs.

Run: timeout 120 python3 -m pytest -q harness/tests/test_commit_msg.py
"""
import os
import stat
import subprocess
import tempfile

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "githooks")


def repo(tmp):
    subprocess.run(["git", "init", "-q", tmp], check=True)
    for key, value in (("user.name", "Test"), ("user.email", "t@example.com"), ("core.hooksPath", HOOKS)):
        subprocess.run(["git", "-C", tmp, "config", key, value], check=True)
    return tmp


def commit(tmp, message):
    with open(os.path.join(tmp, "f.txt"), "a") as fh:
        fh.write("x\n")
    subprocess.run(["git", "-C", tmp, "add", "f.txt"], check=True)
    return subprocess.run(["git", "-C", tmp, "commit", "-q", "-m", message], capture_output=True, text=True)


def test_ai_trailers_are_refused():
    with tempfile.TemporaryDirectory() as tmp:
        repo(tmp)
        for trailer in (
            "Co-Authored-By: Claude <noreply@anthropic.com>",
            "co-authored-by: Claude Opus 5.5 <noreply@anthropic.com>",
            "Co-authored-by: GitHub Copilot <copilot@github.com>",
            "Co-Authored-By: Codex <codex@openai.com>",
            "Co-Authored-By: GPT-5 <bot@example.com>",
        ):
            run = commit(tmp, "feat: x\n\n" + trailer)
            assert run.returncode != 0, trailer
            assert "AI co-author trailer" in run.stderr and trailer in run.stderr, run.stderr


def test_humans_and_comments_pass():
    with tempfile.TemporaryDirectory() as tmp:
        repo(tmp)
        assert commit(tmp, "feat: x\n\nCo-Authored-By: Raveen <r@example.com>").returncode == 0
        assert commit(tmp, "feat: y\n\n# Co-Authored-By: Claude <noreply@anthropic.com>").returncode == 0
        assert commit(tmp, "docs: mention Claude in the body, no trailer").returncode == 0


def test_a_repos_own_hook_still_runs():
    """The global hooksPath hides .git/hooks; the hook chains to it."""
    with tempfile.TemporaryDirectory() as tmp:
        repo(tmp)
        local = os.path.join(tmp, ".git", "hooks", "commit-msg")
        with open(local, "w") as fh:
            fh.write("#!/bin/sh\necho local-hook-ran >&2\nexit 1\n")
        os.chmod(local, os.stat(local).st_mode | stat.S_IXUSR)
        run = commit(tmp, "feat: x")
        assert run.returncode != 0 and "local-hook-ran" in run.stderr, run.stderr


def test_help_exits_zero():
    hook = os.path.join(HOOKS, "commit-msg")
    for flag in ("-h", "--help", "help"):
        assert subprocess.run([hook, flag], capture_output=True).returncode == 0, flag
