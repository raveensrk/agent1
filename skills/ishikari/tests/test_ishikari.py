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


def test_workflows_config_and_req():
    with tempfile.TemporaryDirectory() as home:
        repo = make_repo(home)
        env = json.loads(run(home, "setup", repo))
        for k in ("plan", "build", "finish"):
            assert env["workflows"][k].startswith(os.path.join(os.path.realpath(repo), ".git", "ishikari")), k
        assert "testCommand" not in env

        state = env["state"]
        run(home, "config", state, "testCommand", "make test")
        env = json.loads(run(home, "setup", repo))
        assert env["testCommand"] == "make test"
        run(home, "config", state, "testCommand", "")
        assert "testCommand" not in json.loads(run(home, "setup", repo))

        org = os.path.join(repo, "requirements.org")
        open(org, "w").write("#+TITLE: r\n")
        entry = "* OPEN A\n:PROPERTIES:\n:ID:          A-1\n:LAST_EDITED: 2026-01-01\n:END:\nbody\n"
        run(home, "req", "add", org, stdin=entry)
        text = open(org).read()
        assert text.startswith("#+TITLE: r\n\n* OPEN A")
        run(home, "req", "done", org, "A-1")
        text = open(org).read()
        assert "* DONE A" in text and ":LAST_EDITED: 2026-01-01" not in text
        assert ":APPROVED:" in text and ":IMPLEMENTED:" in text and text.count(":END:") == 1
        r = subprocess.run([sys.executable, TOOL, "req", "done", org, "Z-9"], env={**os.environ, "HOME": home},
                           capture_output=True, text=True, timeout=TIMEOUT)
        assert r.returncode == 1 and "Z-9" in r.stderr


def fails(home, *args, stdin=None):
    r = subprocess.run([sys.executable, TOOL, *args], input=stdin, env={**os.environ, "HOME": home},
                       capture_output=True, text=True, timeout=TIMEOUT)
    assert r.returncode == 1, r.stdout
    return r.stderr


def test_guards():
    with tempfile.TemporaryDirectory() as home:
        repo = make_repo(home)
        state = json.loads(run(home, "setup", repo))["state"]
        assert "not valid JSON" in fails(home, "boards", "write", state, "bulletin", stdin="[oops")
        assert "JSON list" in fails(home, "boards", "write", state, "bulletin", stdin='{"a": 1}')
        assert "non-empty JSON list" in fails(home, "boards", "write", state, "bulletin", stdin='["x"]')
        assert "list of ids" in fails(home, "boards", "remove", state, "critiques", stdin='[["x"]]')
        board = open(os.path.join(state, "boards", "bulletin.md")).read()
        assert "| Task" in board  # a refused write leaves the board as it was

        org = os.path.join(repo, "requirements.org")
        run(home, "req", "add", org, stdin="* OPEN B\n:PROPERTIES:\n:ID: B-1\n:END:\n")
        names = os.listdir(repo)
        assert not [n for n in names if n.endswith((".lock", ".tmp"))], names  # nothing left in the repo
        assert "missing" in fails(home, "req", "done", os.path.join(repo, "nope.org"), "B-1")

        crlf = os.path.join(repo, "crlf.org")
        open(crlf, "w", newline="").write("* OPEN C\r\n:PROPERTIES:\r\n:ID: C-1\r\n:END:\r\n")
        run(home, "req", "done", crlf, "C-1")
        raw = open(crlf, newline="").read()
        assert "* DONE C\r\n" in raw and "\n" not in raw.replace("\r\n", "")  # stays CRLF

        assert "columns" in fails(home, "boards", "add", state, "critiques", "r9", stdin='[["a", "b", "c", "d"]]')


def test_parallel_writers():
    with tempfile.TemporaryDirectory() as home:
        state = json.loads(run(home, "setup", make_repo(home)))["state"]
        env = {**os.environ, "HOME": home}
        procs = [subprocess.Popen([sys.executable, TOOL, "boards", "add", state, "critiques", "p"],
                                  stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, env=env, text=True)
                 for _ in range(30)]
        for k, p in enumerate(procs):
            p.communicate(json.dumps([[f"f{k}.py", f"c{k}"]]), timeout=TIMEOUT)
            assert p.returncode == 0
        text = open(os.path.join(state, "boards", "critiques.md")).read()
        assert sum(1 for l in text.splitlines() if l.startswith("| p-")) == 30  # no row lost


if __name__ == "__main__":
    test_setup_and_boards()
    test_workflows_config_and_req()
    test_guards()
    test_parallel_writers()
    print("ok")
