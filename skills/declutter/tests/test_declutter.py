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
    out = io.StringIO()
    with tempfile.TemporaryDirectory() as td:
        scan.IGNORE_FILE = Path(td) / "ignored.json"
        scan.IGNORE_FILE.write_text(json.dumps([gone["path"]]))
        with contextlib.redirect_stdout(out):
            scan.main()
    data = json.loads(out.getvalue())
    assert [i["path"] for i in data["items"]] == [keep["path"]]
    assert data["counts"]["ignored_hidden"] == 1


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
