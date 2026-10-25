"""Tests for harness/githooks/post-commit, through real `git commit` runs.

Run: timeout 120 python3 -m pytest -q harness/tests/test_post_commit.py
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


def commit(tmp, message="feat: x"):
    with open(os.path.join(tmp, "f.txt"), "a") as fh:
        fh.write("x\n")
    subprocess.run(["git", "-C", tmp, "add", "f.txt"], check=True)
    return subprocess.run(["git", "-C", tmp, "commit", "-q", "-m", message], capture_output=True, text=True)


def test_without_a_repo_hook_nothing_happens():
    with tempfile.TemporaryDirectory() as tmp:
        repo(tmp)
        run = commit(tmp)
        assert run.returncode == 0 and run.stderr == "", run.stderr


def test_a_repos_own_hook_runs_after_the_commit():
    """The global hooksPath hides .git/hooks; the hook chains to it."""
    with tempfile.TemporaryDirectory() as tmp:
        repo(tmp)
        local = os.path.join(tmp, ".git", "hooks", "post-commit")
        with open(local, "w") as fh:
            fh.write("#!/bin/sh\ngit log -1 --format=%s > ran.txt\n")
        os.chmod(local, os.stat(local).st_mode | stat.S_IXUSR)
        assert commit(tmp, "feat: made").returncode == 0
        with open(os.path.join(tmp, "ran.txt")) as fh:
            assert fh.read().strip() == "feat: made", "it ran, with the commit already made"


def test_help_exits_zero():
    hook = os.path.join(HOOKS, "post-commit")
    for flag in ("-h", "--help", "help"):
        assert subprocess.run([hook, flag], capture_output=True).returncode == 0, flag
