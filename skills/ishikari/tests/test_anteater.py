#!/usr/bin/env python3
"""Checks for anteater.py, on invented transcripts under an invented home.

Run: timeout 120 python3 -m pytest -q skills/ishikari/tests/test_anteater.py
No pytest: timeout 120 python3 skills/ishikari/tests/test_anteater.py
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.realpath(__file__))
SKILL = os.path.dirname(HERE)
EATER = os.path.join(SKILL, "scripts", "anteater.py")
TOOL = os.path.join(SKILL, "scripts", "ishikari.py")
SCRIPTS = [os.path.join(SKILL, "scripts", f"ishikari-{n}.js") for n in ("plan", "build", "finish", "retro")]
KIND = re.compile(r"""['`]([a-z]+(?:-[a-z]+)*-(?:ant|clerk))(?=[:'`])""")
TIMEOUT = 30
RUN, OTHER, SID = "20261120-100000-aaaa", "20261120-103000-bbbb", "11111111-2222-3333-4444-555555555555"

sys.path.insert(0, os.path.join(SKILL, "scripts"))
import anteater  # noqa: E402


def call(home, tool, *args, stdin=None, env=None, ok=True):
    e = {**os.environ, "HOME": home, **(env or {})}
    e.pop("CLAUDE_CONFIG_DIR", None)
    if env is None or "CLAUDE_CODE_SESSION_ID" not in env:
        e.pop("CLAUDE_CODE_SESSION_ID", None)
    r = subprocess.run([sys.executable, tool, *args], input=stdin, env=e, capture_output=True, text=True, timeout=TIMEOUT)
    assert (r.returncode == 0) == ok, r.stderr + r.stdout
    return r


def msg(at, mid, model, tin, tout, cw, cr, one_hour=0):
    """One assistant line as Claude Code writes it."""
    use = {"input_tokens": tin, "output_tokens": tout, "cache_creation_input_tokens": cw, "cache_read_input_tokens": cr,
           "cache_creation": {"ephemeral_5m_input_tokens": cw - one_hour, "ephemeral_1h_input_tokens": one_hour}}
    return json.dumps({"type": "assistant", "timestamp": at, "message": {"id": mid, "model": model, "usage": use}})


def put(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("".join(l + "\n" for l in lines))


def world(home):
    """One run with every kind of ant, and a later run in the same session."""
    state = os.path.join(home, ".ishikari", "app-0a1b2c3d")
    for run, setup, last in ((RUN, "2026-11-20T10:00:00.000Z", "2026-11-20T10:20:00.000Z"),
                             (OTHER, "2026-11-20T10:30:00.000Z", "2026-11-20T10:40:00.000Z")):
        put(os.path.join(state, "plans", run, "run.json"),
            [json.dumps({"run": run, "setupAt": setup, "lastSaveAt": last, "sessions": [SID]})])
    proj = os.path.join(home, ".claude", "projects", "-p")
    base = os.path.join(proj, SID)
    fable, opus = "claude-fable-5-2", "claude-opus-5-5"
    put(base + ".jsonl", [
        json.dumps({"type": "user", "timestamp": "2026-11-20T09:50:00.000Z", "message": {"role": "user", "content": "hi"}}),
        msg("2026-11-20T09:59:00.000Z", "m0", fable, 9, 9, 9, 9),          # before setup: not this run
        msg("2026-11-20T10:01:00.000Z", "m1", fable, 10, 100, 1000, 5000),
        msg("2026-11-20T10:01:01.000Z", "m1", fable, 10, 100, 1000, 5000),  # the same message again: counted once
        msg("2026-11-20T10:05:00.000Z", "m2", fable, 20, 200, 0, 6000),
        json.dumps({"type": "assistant", "timestamp": "2026-11-20T10:06:00.000Z",
                    "message": {"id": "s1", "model": "<synthetic>", "usage": {"input_tokens": 0, "output_tokens": 0}}}),
        msg("2026-11-20T10:25:00.000Z", "m3", fable, 7, 7, 7, 7),          # after the last save: not counted
        msg("2026-11-20T10:31:00.000Z", "m4", fable, 5, 5, 5, 5),          # the later run owns this one
    ])
    sub = os.path.join(base, "subagents")
    put(os.path.join(sub, "agent-inv1.jsonl"), [msg("2026-11-20T10:02:00.000Z", "i1", opus, 2, 300, 400, 7000, one_hour=400)])
    put(os.path.join(sub, "agent-inv1.meta.json"), [json.dumps({"description": "Plan the thing", "model": "opus", "effort": "low", "spawnDepth": 1})])
    put(os.path.join(sub, "agent-res1.jsonl"), [msg("2026-11-20T10:03:00.000Z", "r1", opus, 1, 50, 60, 800)])
    put(os.path.join(sub, "agent-res1.meta.json"), [json.dumps({"description": "Clojure facts", "parentAgentId": "inv1", "spawnDepth": 2})])
    put(os.path.join(sub, "agent-late.jsonl"), [msg("2026-11-20T10:32:00.000Z", "l1", opus, 1, 1, 1, 1)])  # the later run's investigator
    put(os.path.join(sub, "agent-late.meta.json"), [json.dumps({"description": "Other run"})])
    wf = os.path.join(sub, "workflows", "wf_build")
    put(os.path.join(base, "workflows", "wf_build.json"),
        [json.dumps({"runId": "wf_build", "workflowName": "ishikari-build", "args": json.dumps({"env": {"run": RUN}})})])
    for aid, label, lines in (
        ("w1", "worker-ant:task-a:build", [msg("2026-11-20T10:10:00.000Z", "w1a", opus, 3, 1000, 2000, 30000),
                                           msg("2026-11-20T10:11:00.000Z", "w1b", opus, 3, 500, 0, 32000)]),
        ("w2", "worker-ant:task-a:fix1", [msg("2026-11-20T10:14:00.000Z", "w2a", opus, 3, 400, 100, 40000)]),
        ("d1", "detective-ant:task-a:check", [msg("2026-11-20T10:12:00.000Z", "d1a", opus, 4, 250, 300, 20000), "{not json"]),
        ("x1", "mystery-ant:zzz", [msg("2026-11-20T10:13:00.000Z", "x1a", "claude-nova-9", 1, 2, 3, 4)]),
        ("c1", "logbook-clerk:now", [msg("2026-11-20T10:15:00.000Z", "c1a", opus, 1, 10, 0, 100)]),
    ):
        put(os.path.join(wf, f"agent-{aid}.jsonl"), lines)
        put(os.path.join(wf, f"agent-{aid}.meta.json"), [json.dumps({"description": label, "workflowPhase": "Build"})])
    # A workflow of the later run: named by its record, so never counted here.
    wf2 = os.path.join(sub, "workflows", "wf_other")
    put(os.path.join(base, "workflows", "wf_other.json"),
        [json.dumps({"workflowName": "ishikari-retro", "args": {"env": {"run": OTHER}}})])
    put(os.path.join(wf2, "agent-o1.jsonl"), [msg("2026-11-20T10:35:00.000Z", "o1a", opus, 1, 1, 1, 1)])
    put(os.path.join(wf2, "agent-o1.meta.json"), [json.dumps({"description": "retrospective-ant"})])
    return state


def test_counts():
    with tempfile.TemporaryDirectory() as home:
        state = world(home)
        out = os.path.join(state, "plans", RUN, "tokens.json")
        assert not os.path.exists(out)
        dry = call(home, EATER, "snapshot", state, RUN, "--dry-run").stdout
        assert not os.path.exists(out)  # --dry-run writes nothing
        call(home, EATER, "snapshot", state, RUN)
        first = open(out, "rb").read()
        assert first.decode() == dry
        call(home, EATER, "snapshot", state, RUN)
        assert open(out, "rb").read() == first  # the same transcripts, the same bytes
        doc = json.loads(first)
        ants = {a["id"]: a for a in doc["ants"]}
        assert sorted(ants) == sorted([f"main:{SID}", "inv1", "res1", "w1", "w2", "d1", "x1", "c1"]), sorted(ants)
        opus, fable = "claude-opus-5-5", "claude-fable-5-2"
        # Worked by hand from world(): in, out, cache write 5 min, cache write 1 h, cache read.
        assert ants[f"main:{SID}"]["usage"] == {fable: [30, 300, 1000, 0, 11000]}  # m1 once, m2; not m0, m3, m4
        assert ants[f"main:{SID}"]["turns"] == 2 and ants[f"main:{SID}"]["stage"] == "main"
        assert ants["inv1"]["usage"] == {opus: [2, 300, 0, 400, 7000]}
        assert (ants["inv1"]["stage"], ants["inv1"]["station"], ants["inv1"]["label"]) == ("investigate", "investigator", "Plan the thing")
        assert (ants["res1"]["station"], ants["res1"]["usage"]) == ("researcher", {opus: [1, 50, 60, 0, 800]})
        assert ants["w1"]["usage"] == {opus: [6, 1500, 2000, 0, 62000]}
        assert (ants["w1"]["stage"], ants["w1"]["station"], ants["w1"]["task"], ants["w1"]["try"]) == ("build", "worker", "task-a", 1)
        assert (ants["w2"]["task"], ants["w2"]["try"]) == ("task-a", 2)  # tries count in start order
        assert ants["w1"]["turns"] == 2 and ants["w1"]["peakContext"] == 32003
        assert (ants["d1"]["station"], ants["d1"]["task"]) == ("detective", "task-a")
        assert (ants["x1"]["station"], ants["x1"]["usage"]) == ("unknown", {"claude-nova-9": [1, 2, 3, 0, 4]})
        assert (ants["c1"]["station"], ants["c1"]["task"]) == ("logbook clerk", "")
        assert doc["fastPath"] is False and doc["sessions"] == [SID]
        assert any("unknown label: mystery-ant:zzz" in w for w in doc["warnings"]), doc["warnings"]
        assert any(w.startswith("unreadable line: ") and w.endswith("agent-d1.jsonl:2") for w in doc["warnings"]), doc["warnings"]
        assert "saved" not in first.decode().lower() and "$" not in first.decode()  # counts only: no dollars, no write time

        # The later run in the same session owns what comes after its setup.
        call(home, EATER, "snapshot", state, OTHER)
        other = {a["id"]: a for a in json.load(open(os.path.join(state, "plans", OTHER, "tokens.json")))["ants"]}
        assert sorted(other) == sorted([f"main:{SID}", "late", "o1"]), sorted(other)
        assert other[f"main:{SID}"]["usage"] == {fable: [5, 5, 5, 0, 5]} and other["o1"]["stage"] == "retro"

        # Cost at view time, and the unknown model shown as ?, never guessed.
        os.environ["HOME"], old = home, os.environ.get("HOME")
        try:
            v = anteater.view(state, RUN)
        finally:
            os.environ["HOME"] = old
        rows = {a["id"]: a for a in v["ants"]}
        # w1 on opus 5.5: 6 in at $4, 1500 out at $20, 2000 written at $5, 62000 read at $0.20, per million.
        assert abs(rows["w1"]["cost"] - (6 * 4 + 1500 * 20 + 2000 * 5 + 62000 * 0.2) / 1e6) < 1e-12
        assert abs(rows["inv1"]["cost"] - (2 * 4 + 300 * 20 + 400 * 8 + 7000 * 0.2) / 1e6) < 1e-12  # 1 h cache write at $8
        assert rows["x1"]["cost"] is None and v["incomplete"] is True
        assert any("no price for model claude-nova-9" in w for w in v["warnings"])
        known = sum(a["cost"] for a in v["ants"] if a["cost"] is not None)
        assert abs(v["total"] - known) < 1e-12
        assert [s["name"] for s in v["stages"]][0] == "build"  # costliest first
        assert {t["name"]: t["ants"] for t in v["tasks"]} == {"task-a": 3}
        assert v["live"] is False and v["source"] == "transcripts"

        # Transcripts cleaned away: the saved file stands, and the page shows it.
        for name in ("agent-w1.jsonl", "agent-w2.jsonl"):
            os.remove(os.path.join(home, ".claude", "projects", "-p", SID, "subagents", "workflows", "wf_build", name))
        assert "kept" in call(home, EATER, "snapshot", state, RUN).stdout
        assert open(out, "rb").read() == first

        # A run with no recorded session is found by its id in a transcript.
        info = json.load(open(os.path.join(state, "plans", OTHER, "run.json")))
        info["sessions"] = []
        json.dump(info, open(os.path.join(state, "plans", OTHER, "run.json"), "w"))
        os.remove(os.path.join(state, "plans", OTHER, "tokens.json"))
        with open(os.path.join(home, ".claude", "projects", "-p", SID + ".jsonl"), "a") as f:
            f.write(json.dumps({"type": "user", "timestamp": "2026-11-20T10:30:30.000Z", "message": {"content": json.dumps({"run": OTHER}, indent=2)}}) + "\n")
            f.write(json.dumps({"type": "user", "timestamp": "2026-11-20T10:30:31.000Z", "message": {"content": f"see {RUN}"}}) + "\n")
        call(home, EATER, "snapshot", state, OTHER)
        again = json.load(open(os.path.join(state, "plans", OTHER, "tokens.json")))
        assert again["sessions"] == [SID] and len(again["ants"]) == 3
        assert anteater.scan_sessions.__doc__ and SID not in [s for s in subprocess.run(
            [sys.executable, "-c", "import sys,json;sys.path.insert(0,sys.argv[1]);import anteater;"
             "print(json.dumps(anteater.scan_sessions({'run':'20261120-100000-aaaa','setup':None})))", os.path.join(SKILL, "scripts")],
            env={**os.environ, "HOME": home}, capture_output=True, text=True, timeout=TIMEOUT).stdout.split('"')]  # a mention is not a link


def test_label_guard():
    kinds = set()
    for path in SCRIPTS:
        kinds |= set(KIND.findall(open(path, encoding="utf-8").read()))
    assert kinds, "no ant label found in the workflow scripts"
    missing = sorted(kinds - set(anteater.STATIONS))
    assert not missing, f"no station rule in anteater.py STATIONS for: {missing}"
    assert set(anteater.TASK_PART) <= set(anteater.STATIONS) and set(anteater.KIND_STAGE) <= set(anteater.STATIONS)
    assert anteater.label_parts("juror-ant:1:task-b") == ("juror-ant", "juror", "task-b")
    assert anteater.label_parts("worker-ant:judge-fix") == ("worker-ant", "worker", "judge-fix")
    assert anteater.label_parts("nope:1")[1] is None


def test_ishikari_hooks():
    with tempfile.TemporaryDirectory() as home:
        repo = os.path.join(home, "app")
        os.makedirs(repo)
        for cmd in (["init", "-q", "-b", "main"],
                    ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "init"]):
            subprocess.run(["git", "-C", repo, *cmd], check=True, timeout=TIMEOUT)
        env = json.loads(call(home, TOOL, "setup", repo, env={"CLAUDE_CODE_SESSION_ID": "sess-aaaa-1111"}).stdout)
        folder = os.path.join(env["state"], "plans", env["run"])
        info = json.load(open(os.path.join(folder, "run.json")))
        assert info["sessions"] == ["sess-aaaa-1111"] and info["lastSaveAt"] is None
        assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", info["setupAt"]), info
        assert not os.path.exists(os.path.join(folder, "tokens.json"))
        # A save from a second session: stamped, and the snapshot written by code.
        r = call(home, TOOL, "save", env["state"], env["run"], "investigate", stdin="{}", env={"CLAUDE_CODE_SESSION_ID": "sess-bbbb-2222"})
        assert r.stdout.strip().endswith("investigate-1.json") and r.stderr == "", r.stderr
        info = json.load(open(os.path.join(folder, "run.json")))
        assert info["sessions"] == ["sess-aaaa-1111", "sess-bbbb-2222"] and info["lastSaveAt"] >= info["setupAt"]
        doc = json.load(open(os.path.join(folder, "tokens.json")))
        assert doc["run"] == env["run"] and doc["ants"] == [] and doc["fastPath"] is True
        # No session id in the shell: still a run, with no session recorded.
        bare = json.loads(call(home, TOOL, "setup", repo).stdout)
        assert json.load(open(os.path.join(env["state"], "plans", bare["run"], "run.json")))["sessions"] == []
        # A run id is never handed out twice, even to another repo's state folder.
        ids = {json.loads(call(home, TOOL, "setup", repo).stdout)["run"] for _ in range(4)} | {env["run"], bare["run"]}
        assert len(ids) == 6
        listed = call(home, EATER, "runs").stdout
        assert env["run"] in listed and bare["run"] in listed


def test_limit():
    with tempfile.TemporaryDirectory() as home:
        os.environ["HOME"], old = home, os.environ.get("HOME")
        try:
            prices = {"models": {}, "five_hour_usd": None}
            assert anteater.limit_fit(prices)["usdPerPercent"] is None  # no log yet
            log = anteater.limit_log()
            os.makedirs(os.path.dirname(log))
            rows = [  # time, session, session cost, percent used, window
                (100, "a", 1.00, 10, "w1"), (200, "a", 3.00, 14, "w1"), (250, "b", 0.50, 15, "w1"),
                (300, "b", 2.50, 20, "w1"), (400, "a", 4.00, 22, "w1"),
                (900, "a", 4.50, 2, "w2"),   # a new window: the drop is not a rise, the first sample is no pair
                (950, "a", 6.50, 6, "w2"), ("junk",),
            ]
            with open(log, "w") as f:
                f.write("".join("\t".join(str(c) for c in r) + "\n" for r in rows))
            fit = anteater.limit_fit(prices)
            # w1: percent 10 -> 22 is 12 points; a rose 3.00, b rose 2.00. w2: 4 points, a rose 2.00.
            assert abs(fit["usdPerPercent"] - (3.0 + 2.0 + 2.0) / (12 + 4)) < 1e-12, fit
            assert "16 percent points over 2 limit windows" in fit["basis"], fit
            with open(log, "w") as f:
                f.write("100\ta\t1\t10\tw1\n200\ta\t2\t12\tw1\n")
            assert anteater.limit_fit(prices)["usdPerPercent"] is None  # 2 points: too few to trust
            assert anteater.limit_fit({"models": {}, "five_hour_usd": 50})["usdPerPercent"] == 0.5  # your number wins
        finally:
            os.environ["HOME"] = old
    p = anteater.load_prices()
    assert anteater.price_of(p, "claude-opus-5-5")["out"] == 20.0
    assert anteater.price_of(p, "claude-opus-5-5-20260901")["out"] == 20.0  # a dated id is the same model
    assert anteater.price_of(p, "claude-opus-5-9") is None  # an unknown model is never priced as a near one


def test_server_and_help():
    for arg in ("-h", "--help", "help"):
        out = call(tempfile.gettempdir(), EATER, arg).stdout
        assert "anteater.py" in out and "snapshot" in out, out
    assert "unknown argument" in call(tempfile.gettempdir(), EATER, "--nope", ok=False).stderr
    with tempfile.TemporaryDirectory() as home:
        state = world(home)
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        env = {**os.environ, "HOME": home}
        env.pop("CLAUDE_CONFIG_DIR", None)
        proc = subprocess.Popen([sys.executable, EATER, "serve", "--port", str(port), "--no-open"], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            assert f"http://127.0.0.1:{port}/" in proc.stdout.readline()

            def get(path):
                with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=TIMEOUT) as r:
                    return r.read().decode()

            assert "<title>Ant Eater</title>" in get("/")
            runs = json.loads(get("/api/runs"))
            assert [r["run"] for r in runs] == [OTHER, RUN]  # newest first
            v = json.loads(get(f"/api/run?state={os.path.basename(state)}&run={RUN}"))
            assert len(v["ants"]) == 8 and v["percent"] is None and v["total"] > 0
            for bad in ("/api/run?state=..&run=x", f"/api/run?state={os.path.basename(state)}&run=nope"):
                try:
                    get(bad)
                    raise AssertionError(f"{bad} was served")
                except urllib.error.HTTPError as e:
                    assert e.code in (400, 404)
        finally:
            proc.terminate()
            proc.wait(timeout=TIMEOUT)


if __name__ == "__main__":
    test_counts()
    test_label_guard()
    test_ishikari_hooks()
    test_limit()
    test_server_and_help()
    print("ok")
