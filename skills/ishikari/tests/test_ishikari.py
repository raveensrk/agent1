#!/usr/bin/env python3
"""Checks for ishikari.py, run on an invented repo under an invented home.

Run: timeout 120 python3 -m pytest -q skills/ishikari/tests/test_ishikari.py
No pytest: timeout 120 python3 skills/ishikari/tests/test_ishikari.py
"""
from __future__ import annotations

import json
import os
import shutil
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.realpath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), "scripts", "ishikari.py")
TIMEOUT = 30  # seconds for each call
SKILL = os.path.dirname(HERE)
METRO = os.path.join(SKILL, "design", "metro.clj")
SVG = os.path.join(SKILL, "design", "ishikari-metro.svg")
SCRIPTS = [os.path.join(SKILL, "scripts", f"ishikari-{n}.js") for n in ("plan", "build", "finish")]
NS = "{http://www.w3.org/2000/svg}"
KIND = re.compile(r"""['`]([a-z]+(?:-[a-z]+)*-(?:ant|clerk))(?=[:'`])""")
KIND_STATION = {  # label kind in the scripts -> its station name on the map
    "investigator-ant": "Investigator ant", "researcher-ant": "Researcher ants  ∥",
    "add-requirement-ant": "Add requirement ant", "architect-ant": "Architect ant",
    "worker-ant": "Worker ants  ∥",
    "detective-ant": "Detective ants  ∥", "integrator-ant": "Integrator ant",
    "merger-ant": "Merger ant", "janitor-ant": "Janitor ant",
    "juror-ant": "Juror ants  ∥", "judge-ant": "Judge ant", "finisher-ant": "Finisher ant",
    "logbook-clerk": "Logbook",
}
NOTES = {  # architecture.md "Required note texts"
    "N1": "fewer than 2 passing tasks: no combined test",
    "N2": "a cleanup run has no janitor",
    "N3": "below 7 and gaps: one fix round",
    "N4": "only when main moved and checkCommand is set",
    "N5": "only with 3+ merged tasks",
    "N6": "a plan may run a saved workflow in place of a worker ant",
    "N7": "max 2 extra build rounds",
    "N8": "runs the tests, commits, lands it only if",
    "N9": "the main session pipes it into ishikari.py req add",
    "N10": "the fix lands only through this fast-forward",
    "N11": "logbook clerk ant: appends each ant's entry",
    "N12": "no requirements file: no add requirement ant",
}


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


def test_setup_and_logbook():
    with tempfile.TemporaryDirectory() as home:
        repo = make_repo(home)
        env = json.loads(run(home, "setup", repo))
        assert env["main"] == "main"
        assert env["state"].startswith(os.path.join(home, ".ishikari", "app-"))
        for k in ("plan", "build", "finish"):
            assert os.path.isfile(env["workflows"][k]), k
        assert env["requirements"] == []
        for f in ("requirements.org", "docs/requirements/cli.org", "notes.org", "requirements/x.txt"):
            os.makedirs(os.path.dirname(os.path.join(repo, f)), exist_ok=True)
            open(os.path.join(repo, f), "w").close()
        subprocess.run(["git", "-C", repo, "add", "."], check=True, timeout=TIMEOUT)
        subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "r"], check=True, timeout=TIMEOUT)
        top = os.path.realpath(repo)
        assert json.loads(run(home, "setup", repo))["requirements"] == [
            os.path.join(top, "docs/requirements/cli.org"), os.path.join(top, "requirements.org")]
        state = env["state"]
        book = os.path.join(state, "logbook.rec")
        assert "%rec: Entry" in open(book).read()

        run(home, "log", "append", state, stdin=json.dumps([
            {"run": "r1", "task": "x", "who": "worker ant", "event": "awaiting review"},
            {"run": "r1", "task": "x", "who": "inspector ant", "event": "bug open", "detail": "line one\nline two", "tries": 2}]))
        run(home, "log", "append", state, stdin=json.dumps([{"run": "r1", "task": "x", "who": "merger ant", "event": "done"}]))
        run(home, "log", "note", state, "check", "the", "auth", "flow")
        text = open(book).read()
        assert text.count("Task: x") == 3  # append only: nothing replaced
        assert "Detail: line one\n+ line two" in text and "Tries: 2" in text
        assert "Who: you\nEvent: note\nDetail: check the auth flow" in text
        status = run(home, "log", "status", state, "r1")
        assert "r1/x  done  merger ant" in status and "bug open" not in status
        if shutil.which("recsel"):  # the file is a valid recfile
            out = subprocess.run(["recsel", "-t", "Entry", "-e", "Event = 'done'", "-P", "Who", book],
                                 capture_output=True, text=True, timeout=TIMEOUT)
            assert out.returncode == 0 and out.stdout.strip() == "merger ant", out.stderr


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
        book = os.path.join(state, "logbook.rec")
        before = open(book).read()
        assert "not valid JSON" in fails(home, "log", "append", state, stdin="[oops")
        assert "non-empty JSON list" in fails(home, "log", "append", state, stdin='{"a": 1}')
        assert "JSON object" in fails(home, "log", "append", state, stdin='["x"]')
        assert "unknown field" in fails(home, "log", "append", state, stdin='[{"run": "r", "who": "w", "event": "e", "colour": "red"}]')
        assert "no who" in fails(home, "log", "append", state, stdin='[{"run": "r", "event": "e"}]')
        assert open(book).read() == before  # a refused write adds nothing

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


def test_parallel_writers():
    with tempfile.TemporaryDirectory() as home:
        state = json.loads(run(home, "setup", make_repo(home)))["state"]
        env = {**os.environ, "HOME": home}
        procs = [subprocess.Popen([sys.executable, TOOL, "log", "append", state],
                                  stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, env=env, text=True)
                 for _ in range(30)]
        for k, p in enumerate(procs):
            p.communicate(json.dumps([{"run": "p", "task": str(k), "who": "worker ant", "event": "done"}]), timeout=TIMEOUT)
            assert p.returncode == 0
        text = open(os.path.join(state, "logbook.rec")).read()
        assert text.count("Run: p\n") == 30  # no entry lost


def git_in(repo, *args):
    subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   check=True, timeout=TIMEOUT)


def test_main_branch_and_run_id():
    with tempfile.TemporaryDirectory() as home:
        repo = os.path.join(home, "app")
        os.makedirs(repo)
        git_in(repo, "init", "-q", "-b", "feature")
        git_in(repo, "commit", "-q", "--allow-empty", "-m", "init")
        assert "--main" in fails(home, "setup", repo)  # a feature branch is never taken as main
        assert json.loads(run(home, "setup", repo, "--main", "feature"))["main"] == "feature"
        assert "does not exist" in fails(home, "setup", repo, "--main", "nope")
        git_in(repo, "branch", "main")
        assert "not the main branch main" in fails(home, "setup", repo)
        git_in(repo, "checkout", "-q", "main")
        open(os.path.join(repo, "f"), "w").write("x")
        git_in(repo, "add", "f")
        assert "uncommitted" in fails(home, "setup", repo)
        git_in(repo, "commit", "-q", "-m", "f")
        assert json.loads(run(home, "setup", "--main", "main", repo))["main"] == "main"  # --main first

        wt = os.path.join(home, "wt")
        git_in(repo, "worktree", "add", "-q", "-b", "side", wt)
        env = json.loads(run(home, "setup", wt))  # a linked worktree resolves to the main checkout
        assert env["repo"] == os.path.realpath(repo) and env["main"] == "main", env

        git_in(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        git_in(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/gone")
        assert json.loads(run(home, "setup", repo))["main"] == "main"  # origin/HEAD with no local branch is skipped
        assert fails(home, "setup", repo, "--main", "gone").strip().endswith("; pass --main <branch>")

        ids = {json.loads(run(home, "setup", repo))["run"] for _ in range(5)}
        assert len(ids) == 5, ids  # same second, still distinct
        assert all(re.fullmatch(r"\d{8}-\d{6}-[0-9a-f]{4}", i) for i in ids), ids


def test_req_and_log_gaps():
    with tempfile.TemporaryDirectory() as home:
        repo = make_repo(home)
        state = json.loads(run(home, "setup", repo))["state"]
        org = os.path.join(home, "r.org")
        for i in ("A-1", "A-2", "A-3"):
            run(home, "req", "add", org, stdin=f"* OPEN {i}\n:PROPERTIES:\n:ID: {i}\n:END:\n")
        out = run(home, "req", "done", org, "A-1", "A-3")
        text = open(org).read()
        assert "* DONE A-1" in text and "* OPEN A-2" in text and "* DONE A-3" in text, text
        assert "A-1" in out and "A-3" in out and text.count(":IMPLEMENTED:") == 2

        crlf = os.path.join(home, "c.org")
        open(crlf, "w", newline="").write("#+TITLE: c\r\n")
        run(home, "req", "add", crlf, stdin="* OPEN D\r\n:PROPERTIES:\r\n:ID: D-1\r\n:END:\r\n")
        raw = open(crlf, newline="").read()
        assert "* OPEN D\r\n" in raw and "\n" not in raw.replace("\r\n", "")  # added entry follows CRLF

        run(home, "config", state, "checkCommand", "make lint")
        run(home, "config", state, "checkCommand", "")
        assert json.load(open(os.path.join(state, "config.json"))) == {}  # empty value forgets the key

        run(home, "log", "append", state, stdin=json.dumps([{"run": "r", "task": "a|b", "who": "ant", "event": "x | y", "detail": "Event: fake\n\nRun: injected"}]))
        entries = [l for l in open(os.path.join(state, "logbook.rec")).read().split("\n\n") if "Task: a|b" in l]
        assert len(entries) == 1 and "+ -" not in entries[0] and "Run: injected" not in entries[0].replace("+ Run: injected", "")  # a newline never starts a new field


def metro_texts(path):
    """Every visible label of the map: [{s, x, y, size, weight, anchor}], and W, H."""
    root = ET.parse(path).getroot()
    _, _, w, h = (float(v) for v in root.get("viewBox").split())
    out = []
    for t in root.iter(NS + "text"):
        if t.get("class") != "h":
            continue
        out.append({"s": t.text or "", "x": float(t.get("x")), "y": float(t.get("y")),
                    "size": float(t.get("font-size")), "weight": int(t.get("font-weight") or 400),
                    "anchor": t.get("text-anchor") or "start"})
    return out, w, h


def text_box(t):
    w = len(t["s"]) * t["size"] * (0.6 if t["weight"] >= 700 else 0.55)
    x0 = {"start": t["x"], "middle": t["x"] - w / 2, "end": t["x"] - w}[t["anchor"]]
    return x0, x0 + w, t["y"] - 0.75 * t["size"], t["y"] + 0.25 * t["size"]


def test_metro_map():
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "map.svg")
        subprocess.run(["bb", METRO, out], check=True, timeout=TIMEOUT)
        assert os.path.isfile(out)
        with open(out, "rb") as a, open(SVG, "rb") as b:
            assert a.read() == b.read(), "ishikari-metro.svg is stale: run bb design/metro.clj"
    texts, w, h = metro_texts(SVG)
    names = [t["s"] for t in texts if t["size"] == 16]
    for script in SCRIPTS:
        src = open(script, encoding="utf-8").read()
        for kind in set(KIND.findall(src)):
            assert kind in KIND_STATION, f"{os.path.basename(script)}: no station for {kind}"
            assert KIND_STATION[kind] in names, f"{os.path.basename(script)}: {KIND_STATION[kind]} not on the map"
    counts = {"Merger ant": 2, "Worker ant": 1, "Inspector ant": 0, "Detective ant": 1, "Judge ant": 2,
              "Verifier ant": 0, "Juror ants  ∥": 1, "Logbook": 1}
    for name, n in counts.items():
        assert names.count(name) == n, (name, names.count(name))
    for name in ("Task", "You", "investigation_report.md", "Worker plans", "Dropped", "merge failed",
                 "Dropped cleanup", "MAIN", "checkCommand", "check-fix round", "req done"):
        assert name in names, name
    polygons = len(list(ET.parse(SVG).getroot().iter(NS + "polygon")))
    assert polygons >= sum(" ant" in n for n in names)
    strings = [t["s"] for t in texts]
    for nid, note in NOTES.items():
        assert any(note in s for s in strings), nid
    for nid in ("N7", "N11"):
        assert sum(NOTES[nid] in s for s in strings) == 1, nid
    mf = next(t for t in texts if t["size"] == 16 and t["s"] == "merge failed")
    n7 = next(t for t in texts if NOTES["N7"] in t["s"])
    assert n7["x"] == mf["x"] and 0 < n7["y"] - mf["y"] <= 60
    for s in strings:
        for bad in ("req add, keeps", "Judge ant  ∥", "Verifier Ant"):
            assert bad not in s, s
        assert not ("fix plan back" in s and "max 2" in s), s
        assert "fail: one fix round" not in s or "detective, worker, inspector" in s, s
        assert s == "ISHIKARI METRO" or not re.search(r"\bAnts?\b", s), s
    boxes = [(t["s"], text_box(t)) for t in texts]
    for i, (s, (x0, x1, y0, y1)) in enumerate(boxes):
        assert 0 <= x0 and x1 <= w and 0 <= y0 and y1 <= h, f"outside the map: {s}"
        for s2, (u0, u1, v0, v1) in boxes[i + 1:]:
            assert not (x0 < u1 and u0 < x1 and y0 < v1 and v0 < y1), f"overlap: {s!r} and {s2!r}"


def test_docs_match_build():
    lines = open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8").read().split("\n")
    start = lines.index("## Limits")
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        if line.startswith("|"):
            assert line.count("|") == 4, line
    texts, _, _ = metro_texts(SVG)
    book = next(t for t in texts if t["size"] == 16 and t["s"] == "Logbook")
    note = sorted((t for t in texts if t["size"] == 13 and t["x"] == book["x"] and 0 < t["y"] - book["y"] <= 100),
                  key=lambda t: t["y"])
    assert note[0]["s"] == "logbook clerk ant: appends each ant's entry"
    sentence = " ".join(t["s"] for t in note[:4])
    index = " ".join(open(os.path.join(SKILL, "design", "index.md"), encoding="utf-8").read().replace("`", "").split())
    assert sentence in index, sentence
    build = open(SCRIPTS[1], encoding="utf-8").read()
    assert "one logbook append at the end" not in build


if __name__ == "__main__":
    test_setup_and_logbook()
    test_workflows_config_and_req()
    test_guards()
    test_parallel_writers()
    test_main_branch_and_run_id()
    test_req_and_log_gaps()
    test_metro_map()
    test_docs_match_build()
    print("ok")
