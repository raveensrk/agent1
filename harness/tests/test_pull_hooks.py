"""Tests for harness/githooks/post-merge and post-rewrite, through real git runs.

A tracked script/post-commit records its arguments, so each test reads what the
hooks asked for. macOS only, like the tracked-script half of the hooks.

Run: timeout 120 python3 -m pytest -q harness/tests/test_pull_hooks.py
"""
import os
import platform
import stat
import subprocess
import tempfile

import pytest

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "githooks")
pytestmark = pytest.mark.skipif(platform.system() != "Darwin", reason="the hooks run the tracked script on macOS only")


def git(cwd, *args):
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, check=True).stdout.strip()


def configure(path):
    for key, value in (("user.name", "Test"), ("user.email", "t@example.com"), ("core.hooksPath", HOOKS), ("pull.rebase", "true")):
        git(path, "config", key, value)


def commit(path, name):
    with open(os.path.join(path, name), "a") as fh:
        fh.write("x\n")
    git(path, "add", name)
    git(path, "commit", "-q", "-m", f"feat: {name}")


def setup(tmp):
    """An upstream clone and a local clone that records every hook call in LOG."""
    log = os.path.join(tmp, "log")
    bare, up, local = (os.path.join(tmp, n) for n in ("o.git", "up", "local"))
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", bare], check=True)
    subprocess.run(["git", "clone", "-q", bare, up], check=True, capture_output=True)
    configure(up)
    git(up, "config", "core.hooksPath", os.devnull)
    os.mkdir(os.path.join(up, "script"))
    script = os.path.join(up, "script", "post-commit")
    with open(script, "w") as fh:
        fh.write(f'#!/bin/sh\necho "[$*]" >> {log}\n')
    os.chmod(script, os.stat(script).st_mode | stat.S_IXUSR)
    git(up, "add", ".")
    git(up, "commit", "-q", "-m", "feat: script")
    git(up, "push", "-q", "origin", "HEAD:main")
    subprocess.run(["git", "clone", "-q", bare, local], check=True, capture_output=True)
    configure(local)
    return up, local, log


def calls(log):
    if not os.path.exists(log):
        return []
    with open(log) as fh:
        lines = fh.read().splitlines()
    os.remove(log)
    return lines


def upstream(up):
    commit(up, "u.txt")
    git(up, "push", "-q", "origin", "HEAD:main")


def test_fast_forward_pull_installs():
    with tempfile.TemporaryDirectory() as tmp:
        up, local, log = setup(tmp)
        upstream(up)
        git(local, "pull", "-q")
        assert calls(log) == ["[--pull]"]


def test_pull_with_nothing_new_does_nothing():
    with tempfile.TemporaryDirectory() as tmp:
        _, local, log = setup(tmp)
        git(local, "pull", "-q")
        assert calls(log) == []


def test_rebase_pull_installs():
    with tempfile.TemporaryDirectory() as tmp:
        up, local, log = setup(tmp)
        upstream(up)
        commit(local, "l.txt")
        calls(log)
        git(local, "pull", "-q")
        assert calls(log)[-1] == "[--pull]"


def test_merge_pull_installs():
    with tempfile.TemporaryDirectory() as tmp:
        up, local, log = setup(tmp)
        upstream(up)
        commit(local, "l.txt")
        calls(log)
        git(local, "pull", "-q", "--no-rebase", "--no-edit")
        assert calls(log) == ["[--pull]"]


def test_local_merge_asks_for_the_range():
    with tempfile.TemporaryDirectory() as tmp:
        _, local, log = setup(tmp)
        git(local, "switch", "-q", "-c", "b")
        commit(local, "b.txt")
        git(local, "switch", "-q", "main")
        calls(log)
        git(local, "merge", "-q", "--ff-only", "b")
        assert calls(log) == ["[--range ORIG_HEAD HEAD]"]


def test_amend_asks_for_the_range_from_the_old_commit():
    with tempfile.TemporaryDirectory() as tmp:
        _, local, log = setup(tmp)
        commit(local, "a.txt")
        old = git(local, "rev-parse", "HEAD")
        calls(log)
        git(local, "commit", "-q", "--amend", "-m", "feat: amended")
        assert calls(log)[-1] == f"[--range {old} HEAD]"


def test_manual_rebase_asks_for_the_range_from_the_old_tip():
    with tempfile.TemporaryDirectory() as tmp:
        up, local, log = setup(tmp)
        upstream(up)
        commit(local, "l.txt")
        old = git(local, "rev-parse", "HEAD")
        git(local, "fetch", "-q")
        calls(log)
        git(local, "rebase", "-q", "origin/main")
        assert calls(log)[-1] == f"[--range {old} HEAD]"


def test_a_repos_own_hook_wins():
    with tempfile.TemporaryDirectory() as tmp:
        up, local, log = setup(tmp)
        own = os.path.join(local, ".git", "hooks", "post-merge")
        with open(own, "w") as fh:
            fh.write(f'#!/bin/sh\necho own >> {log}\n')
        os.chmod(own, os.stat(own).st_mode | stat.S_IXUSR)
        upstream(up)
        git(local, "pull", "-q")
        assert calls(log) == ["own"]


def test_help_exits_zero():
    for hook in ("post-merge", "post-rewrite"):
        for flag in ("-h", "--help", "help"):
            run = subprocess.run([os.path.join(HOOKS, hook), flag], capture_output=True, stdin=subprocess.DEVNULL)
            assert run.returncode == 0, (hook, flag)
