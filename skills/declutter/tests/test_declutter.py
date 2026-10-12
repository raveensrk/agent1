#!/usr/bin/env python3
"""Self-check for declutter pure functions. Run: python3 tests/test_declutter.py"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE.parent / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_badge():
    scan = load("scan")
    assert scan.badge(None) == "JUNK"          # never opened
    assert scan.badge(0) == "KEEP"
    assert scan.badge(30) == "KEEP"
    assert scan.badge(31) == "MAYBE"
    assert scan.badge(90) == "MAYBE"
    assert scan.badge(91) == "JUNK"


def test_norm():
    scan = load("scan")
    assert scan.norm("Google Chrome.app") == "googlechrome"
    assert scan.norm("Alfred-4.app") == "alfred4"


def test_is_known():
    scan = load("scan")
    installed = {scan.norm("Google Chrome"), scan.norm("com.google.Chrome")}
    assert scan.is_known("Google", installed)          # substring of installed
    assert scan.is_known("Google Chrome Helper", installed)
    assert not scan.is_known("RandomApp", installed)


def test_safe():
    delete = load("delete")
    assert delete.safe("/Applications/Safari.app")
    assert delete.safe(str(Path.home() / "Library/Caches/OrphanApp"))
    assert not delete.safe("/")
    assert not delete.safe("/usr/bin")


def test_dir_age():
    import tempfile
    scan = load("scan")
    with tempfile.TemporaryDirectory() as td:
        assert scan.dir_age_days(td) == 0


def test_ignored_hidden():
    import contextlib
    import io
    import tempfile
    scan = load("scan")
    keep = {"kind": "app", "name": "Keep", "path": "/Applications/Keep.app",
            "bundle_id": "", "bytes": 10, "badge": "JUNK"}
    gone = {**keep, "name": "Gone", "path": "/Applications/Gone.app"}
    scan.scan_apps = lambda: ([keep, gone], {})
    scan.scan_formulae = lambda: []
    scan.scan_leftovers = lambda installed_keys: []
    scan.scan_files = lambda: []
    scan.scan_big_files = lambda mb: ([], False)
    scan.scan_docker = lambda: []
    out = io.StringIO()
    with tempfile.TemporaryDirectory() as td:
        scan.IGNORE_FILE = Path(td) / "ignored.json"
        scan.IGNORE_FILE.write_text(json.dumps([gone["path"]]))
        with contextlib.redirect_stdout(out):
            scan.main()
    data = json.loads(out.getvalue())
    assert [i["path"] for i in data["items"]] == [keep["path"]]
    assert data["counts"]["ignored_hidden"] == 1


def test_big_file_cmd():
    scan = load("scan")
    cmd = scan.big_file_cmd(500)
    assert cmd[:3] == ["find", str(scan.HOME), "-xdev"]
    assert cmd[-3:] == ["-size", "+500M", "-print"]
    assert str(scan.HOME / "Library") in cmd and "node_modules" in cmd
    assert ".colima" in cmd                     # extensionless VM disks
    assert cmd[cmd.index(")") - 1] != "-o"     # no dangling -o before )


def test_scan_big_files():
    import os
    import tempfile
    scan = load("scan")
    assert scan.scan_big_files(0) == ([], False)
    with tempfile.TemporaryDirectory() as td:
        movie = Path(td) / "movie.mkv"
        disk = Path(td) / "Docker.raw"
        inside_vm = Path(td) / "Win.utm" / "data.img"
        inside_vm.parent.mkdir()
        for f in (movie, disk, inside_vm):
            f.write_bytes(b"x" * 10)
        old = scan._time.time() - 200 * 86400
        os.utime(movie, (old, old))
        scan.run_capped = lambda cmd, seconds: (
            [str(movie), str(disk), str(inside_vm), str(Path(td) / "gone")], True)
        rows, truncated = scan.scan_big_files(500)
    assert truncated
    assert [r["path"] for r in rows] == [str(movie)]
    assert rows[0]["kind"] == "file" and rows[0]["source"] == "large"
    assert rows[0]["bytes"] == 10 and rows[0]["badge"] == "JUNK"


def test_run_capped_keeps_partial():
    scan = load("scan")
    lines, cut = scan.run_capped(["sh", "-c", "echo a; echo b; sleep 5"], 1)
    assert cut and lines == ["a", "b"]
    lines, cut = scan.run_capped(["echo", "x"], 5)
    assert not cut and lines == ["x"]


def test_parse_big_mb():
    scan = load("scan")
    assert scan.parse_big_mb([]) == 500
    assert scan.parse_big_mb(["--big-mb", "1000"]) == 1000
    for bad in (["--big-mb"], ["--big-mb", "x"], ["--big-mb", "-1"]):
        try:
            scan.parse_big_mb(bad)
            raise AssertionError(bad)
        except SystemExit:
            pass


def test_docker_bytes():
    scan = load("scan")
    assert scan.docker_bytes("4.43GB") == 4_430_000_000
    assert scan.docker_bytes("258kB") == 258_000
    assert scan.docker_bytes("0B") == 0
    assert scan.docker_bytes("N/A") == 0


def test_docker_rows():
    scan = load("scan")
    df = {
        "Images": [
            {"ID": "sha256:aaa", "Repository": "used", "Tag": "1", "Containers": "1", "Size": "1GB"},
            {"ID": "sha256:bbb", "Repository": "old", "Tag": "2", "Containers": "0", "Size": "2GB"},
            {"ID": "sha256:cccccccccccccccc", "Repository": "<none>", "Tag": "<none>",
             "Containers": "0", "Size": "3MB"},
        ],
        "Containers": [
            {"ID": "c1", "Names": "up", "State": "running", "Size": "1kB"},
            {"ID": "c2", "Names": "down", "State": "exited", "Size": "5MB", "Status": "Exited (0)"},
        ],
        "Volumes": [
            {"Name": "held", "Links": "1", "Size": "1GB"},
            {"Name": "orphan", "Links": "0", "Size": "7MB"},
        ],
        "BuildCache": [{"Size": "10MB", "InUse": False}, {"Size": "1GB", "InUse": True}],
    }
    rows = {r["path"]: r for r in scan.docker_rows(df)}
    assert set(rows) == {"docker://image/sha256:bbb", "docker://image/sha256:cccccccccccccccc",
                         "docker://container/c2", "docker://volume/orphan",
                         "docker://buildcache/unused"}
    assert rows["docker://image/sha256:bbb"]["name"] == "old:2"
    assert rows["docker://image/sha256:cccccccccccccccc"]["badge"] == "JUNK"
    assert rows["docker://buildcache/unused"]["bytes"] == 10_000_000
    assert all(r["kind"] == "docker" for r in rows.values())


def test_plan_docker():
    delete = load("delete")
    assert delete.docker_ref("docker://volume/v1") == ("volume", "v1")
    assert delete.docker_ref("docker://nope/x") is None
    assert delete.docker_ref("/Users/x") is None
    calls = []
    users = {"held": "abc123\n"}

    def fake_run(cmd):
        calls.append(cmd)
        if cmd[:3] == ["docker", "ps", "-aq"]:
            return users.get(cmd[-1].split("=", 1)[1], "")
        return "removed\n"
    delete.run = fake_run
    vol = lambda n: {"kind": "docker", "name": n, "path": f"docker://volume/{n}"}
    assert delete.plan(vol("held"), execute=True).startswith("BLOCKED held: volume in use")
    assert delete.plan(vol("free"), execute=False) == "would run (permanent): docker volume rm free"
    assert not any(c[:3] == ["docker", "volume", "rm"] for c in calls)
    assert delete.plan(vol("free"), execute=True) == "docker volume free: removed"
    assert ["docker", "volume", "rm", "free"] in calls
    bad = {"kind": "docker", "name": "x", "path": "docker://rootfs/"}
    assert delete.plan(bad, execute=True).startswith("BLOCKED")


def test_merge_ignore():
    delete = load("delete")
    assert delete.merge_ignore(["/a"], ["/b", "/a", "", None]) == ["/a", "/b"]


def test_selection_roundtrip():
    delete = load("delete")
    tmp = Path("/tmp/declutter-test-selection.json")
    tmp.write_text(json.dumps({"generated": "x", "items": [
        {"kind": "app", "name": "T", "path": "/Applications/T.app"},
        {"kind": "formula", "name": "wget", "path": "/opt/homebrew/Cellar/wget"},
    ]}))
    items = json.loads(tmp.read_text())["items"]
    assert len(items) == 2
    assert delete.plan(items[0], execute=False) == "would trash /Applications/T.app"
    assert "ignore" not in items[0]
    tmp.unlink()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok {name}")
    print("all checks passed")
