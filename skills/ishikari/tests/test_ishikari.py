#!/usr/bin/env python3
"""Checks for ishikari.py, run on an invented repo under an invented home.

Run: timeout 120 python3 -m pytest -q skills/ishikari/tests/test_ishikari.py
No pytest: timeout 120 python3 skills/ishikari/tests/test_ishikari.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), "scripts", "ishikari.py")
TIMEOUT = 30  # seconds for each call


def run(home, *args, stdin=None):
    env = {**os.environ, "HOME": home}
    r = subprocess.run([sys.executable, TOOL, *args], input=stdin, env=env,
                       capture_output=True, text=True, timeout=TIMEOUT)
    assert r.returncode == 0, r.stderr
    return r.stdout


def make_repo(root):
    repo = os.path.join(root, "app")
    os.makedirs(repo)
    for cmd in (["init", "-q", "-b", "main"],
                ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "init"]):
        subprocess.run(["git", "-C", repo, *cmd], check=True, timeout=TIMEOUT)
    return repo


def test_setup_and_boards():
    with tempfile.TemporaryDirectory() as home:
        repo = make_repo(home)
        env = json.loads(run(home, "setup", repo))
        assert env["main"] == "main"
        assert env["state"].startswith(os.path.join(home, ".ishikari", "app-"))
        for k in ("plan", "build", "finish"):
            assert os.path.isfile(env["workflows"][k]), k
        for b in ("bulletin", "bounty", "critiques"):
            assert os.path.isfile(os.path.join(env["state"], "boards", f"{b}.md"))

        state = env["state"]
        run(home, "boards", "add", state, "critiques", "r1",
            stdin=json.dumps([["a.py", "why | so?"], ["b.py", "and this"]]))
        text = open(os.path.join(state, "boards", "critiques.md")).read()
        assert "r1-1" in text and "r1-2" in text and "why \\| so?" in text

        run(home, "boards", "remove", state, "critiques", stdin=json.dumps(["r1-1"]))
        text = open(os.path.join(state, "boards", "critiques.md")).read()
        assert "r1-1" not in text and "r1-2" in text

        run(home, "boards", "write", state, "bulletin", stdin=json.dumps([["r/x", "building", "worker ant", "-"]]))
        run(home, "boards", "write", state, "bulletin", stdin=json.dumps([["r/x", "done", "merger ant", "-"]]))
        text = open(os.path.join(state, "boards", "bulletin.md")).read()
        assert text.count("r/x") == 1 and "done" in text and "building" not in text


if __name__ == "__main__":
    test_setup_and_boards()
    print("ok")
