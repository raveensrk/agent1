#!/usr/bin/env python3
"""Tests for scripts/ant.py: base, scope, tests and session, on throwaway repos."""
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
ANT = os.path.join(SKILL, "scripts", "ant.py")
SKILLS = os.path.dirname(SKILL)
ANT_SKILLS = ("investigator-ant", "janitor-ant", "judge-ant", "detective-ant", "retrospective-ant")


def sh(cwd, *args):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


def ant(*args, cwd=None):
    r = subprocess.run([sys.executable, ANT, *args], cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def repo(branch="main"):
    d = tempfile.mkdtemp(prefix="ant-test-")
    sh(d, "git", "init", "-q", "-b", branch)
    sh(d, "git", "config", "user.email", "t@t")
    sh(d, "git", "config", "user.name", "t")
    open(os.path.join(d, "a.py"), "w").write("x = 1\ny = 2\nz = 3\n")
    open(os.path.join(d, "gone.py"), "w").write("old\n")
    open(os.path.join(d, "ok.sh"), "w").write("exit 0\n")
    sh(d, "git", "add", ".")
    sh(d, "git", "commit", "-qm", "base")
    sh(d, "git", "checkout", "-qb", "feature")
    return d


def commit(d, msg="change"):
    sh(d, "git", "add", "-A")
    sh(d, "git", "commit", "-qm", msg)


def test_base():
    d = repo("master")
    assert ant("base", "--repo", d)[1].strip() == "master"
    assert ant("base", "--repo", d, "--base", "feature")[1].strip() == "feature"
    code, _, err = ant("base", "--repo", d, "--base", "nope")
    assert code == 2 and "not found" in err
    sh(d, "git", "branch", "-m", "master", "trunk")
    code, _, err = ant("base", "--repo", d)
    assert code == 2 and "--base" in err


def test_scope():
    d = repo()
    open(os.path.join(d, "a.py"), "w").write("x = 1\nY = 20\nz = 3\nw = 4\n")
    open(os.path.join(d, "new.py"), "w").write("n\nm\n")
    os.remove(os.path.join(d, "gone.py"))
    commit(d)
    out = json.loads(ant("scope", "--repo", d)[1])
    assert out["base"] == "main"
    files = {f["path"]: f["ranges"] for f in out["files"]}
    assert files == {"a.py": [[2, 2], [4, 4]], "new.py": [[1, 2]]}
    assert out["deleted"] == ["gone.py"]
    assert out["linesChanged"] == 4


def test_tests_verdicts():
    d = repo()
    run = lambda: json.loads(ant("tests", "--repo", d, "--", "sh", "ok.sh")[1])
    assert run()["verdict"] == "pass"
    open(os.path.join(d, "ok.sh"), "w").write("echo broke; exit 1\n")
    commit(d)
    r = run()
    assert r["verdict"] == "new-failure" and r["before"]["exit"] == 0 and "broke" in r["after"]["tail"]
    sh(d, "git", "checkout", "-q", "main")
    open(os.path.join(d, "ok.sh"), "w").write("exit 1\n")
    commit(d, "main breaks")
    sh(d, "git", "checkout", "-q", "-b", "fix")
    assert run()["verdict"] == "already-failing"
    open(os.path.join(d, "ok.sh"), "w").write("exit 0\n")
    commit(d, "fixed")
    assert run()["verdict"] == "fixed"
    listed = subprocess.run(["git", "-C", d, "worktree", "list"], capture_output=True, text=True).stdout
    assert len(listed.strip().splitlines()) == 1, "the base worktree was not removed"
    code, _, err = ant("tests", "--repo", d)
    assert code == 2 and "after --" in err


def test_help():
    for args in (["help"], ["-h"], ["--help"]):
        code, out, _ = ant(*args)
        assert code == 0 and "ant.py" in out, args
    assert "Exit codes" in ant("help")[1]


def test_session():
    home = tempfile.mkdtemp(prefix="ant-proj-")
    os.makedirs(os.path.join(home, "p"))
    rows = [
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "1", "name": "Bash", "input": {"command": "ls"}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "1", "content": "ok", "is_error": False}]}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "2", "name": "Bash", "input": {"command": "ls"}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "2", "content": "boom", "is_error": True}]}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "3", "name": "Edit", "input": {}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "3", "content": [{"type": "text", "text": "The user doesn't want to proceed"}], "is_error": True}]}},
        {"type": "api-request-blob", "message": {"content": [{"type": "tool_use", "id": "9", "name": "Bash", "input": {}}]}},
        "not json",
    ]
    with open(os.path.join(home, "p", "s1.jsonl"), "w") as f:
        for r in rows:
            f.write((r if isinstance(r, str) else json.dumps(r)) + "\n")
    out = json.loads(ant("session", "--session", "s1", "--projects", home)[1])
    assert out["toolCalls"] == 3 and out["byTool"] == {"Bash": 2, "Edit": 1}
    assert [e["tool"] for e in out["errors"]] == ["Bash", "Edit"]
    assert [e["rejected"] for e in out["errors"]] == [False, True]
    assert out["repeats"] == [{"tool": "Bash", "input": '{"command": "ls"}', "times": 2}]
    code, _, err = ant("session", "--session", "none", "--projects", home)
    assert code == 2 and "no transcript" in err


def test_skills_share_mode_rules_and_point_to_ant():
    block = re.compile(r"^## Which mode\n(.*?)(?=^## )", re.S | re.M)
    texts = {s: open(os.path.join(SKILLS, s, "SKILL.md"), encoding="utf-8").read() for s in ANT_SKILLS}
    blocks = {s: block.search(t).group(1) for s, t in texts.items()}
    assert len(set(blocks.values())) == 1, "the Which mode sections differ: " + ", ".join(blocks)
    for s in ("janitor-ant", "judge-ant", "detective-ant", "retrospective-ant"):
        assert "../ishikari/scripts/ant.py" in texts[s], s
    assert "Fail when bugs is not empty" in texts["detective-ant"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
