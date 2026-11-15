#!/usr/bin/env python3
"""Checks for pinned.py, run on an invented home holding invented repos.

Run: timeout 120 python3 -m pytest -q skills/relayout/tests/test_pinned.py
No pytest: timeout 120 python3 skills/relayout/tests/test_pinned.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
PINNED = os.path.join(os.path.dirname(HERE), "scripts", "pinned.py")
TIMEOUT = 30  # seconds for each call

FILES = {
    "README.md": "# my-app\n",
    ".gitignore": "/target/\n",
    "Cargo.toml": '[package]\nname = "my-app"\n',
    "src/main.rs": "mod util;\nfn main() {}\n",
    "src/util.rs": "pub fn add() {}\n",
    "notes/plan.md": "# Plan\n",
    "docs/guide.md": "# Guide\n",
    "hooks/pre-commit": "#!/bin/sh\n",
    "skills/tidy/SKILL.md": "---\nname: tidy\n---\n",
    "misc/loose.txt": "loose\n",
}
OTHER = (
    "Read [the plan](~/repos/my-app/notes/plan.md).\n"
    "More in ../my-app/docs/ when needed.\n"
    "Prose only: my-app/src/util.rs\n"
    "Gone: ~/repos/my-app/old/file.md\n"
)


def write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def env(home: str) -> dict[str, str]:
    return {"HOME": home, "PATH": os.environ.get("PATH", ""), "GIT_CONFIG_NOSYSTEM": "1"}


def make_home(tmp: str) -> tuple[str, str]:
    """A home holding the repo `my-app`, and files outside it that point in."""
    home = os.path.join(tmp, "home")
    app = os.path.join(home, "repos", "my-app")
    for rel, text in FILES.items():
        write(os.path.join(app, rel), text)
    for args in (["init", "-q", "-b", "main", app], ["-C", app, "add", "-A"]):
        subprocess.run(["git", *args], check=True, env=env(home), capture_output=True,
                       timeout=TIMEOUT)
    write(os.path.join(home, "repos", "other", "AGENTS.md"), OTHER)
    write(os.path.join(home, "repos", "other", "session.jsonl"),
          "~/repos/my-app/misc/loose.txt\n")
    write(os.path.join(home, ".gitconfig"), "[core]\n\thooksPath = ~/repos/my-app/hooks\n")
    return home, app


def pinned(*args: str, home: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, PINNED, *args], env=env(home),
                          capture_output=True, text=True, timeout=TIMEOUT)


def pins(*args: str) -> dict[str, str]:
    """Run pinned.py on a fresh invented home; map each pinned path to its line."""
    with tempfile.TemporaryDirectory() as tmp:
        home, app = make_home(tmp)
        proc = pinned(app, *[a.replace("HOME", home) for a in args], home=home)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.splitlines()[-1].startswith("pinned: "), proc.stdout
    found = {}
    for line in proc.stdout.splitlines()[:-1]:
        path, _, rest = line.partition(": ")
        found[path] = rest
    return found


def test_anchored_reference_pins_the_file():
    found = pins()
    assert found["notes/plan.md"].startswith("outside: "), found
    assert found["notes/plan.md"].endswith("other/AGENTS.md:1"), found


def test_sibling_folder_reference_pins_the_folder_and_its_contents():
    found = pins()
    assert found["docs/**"].startswith("outside: "), found
    assert found["docs/**"].endswith("other/AGENTS.md:2"), found


def test_bare_mentions_logs_and_untracked_paths_pin_nothing():
    found = pins()
    assert not [p for p in found if p.startswith(("src/util.rs", "misc", "old"))], found


def test_gitconfig_hooks_path_pins_the_hooks_folder():
    found = pins()
    assert found["hooks/**"].startswith("outside: "), found
    assert found["hooks/**"].endswith(".gitconfig:2"), found


def test_tool_and_root_files_are_pinned():
    found = pins()
    expected = {
        "Cargo.toml": "tool",
        "src/main.rs": "tool",
        "skills/tidy/": "tool",
        "skills/tidy/SKILL.md": "tool",
        "README.md": "root",
        ".gitignore": "root",
    }
    for path, kind in expected.items():
        assert found.get(path, "").startswith(kind + ": "), (path, found)


def test_root_flag_replaces_the_default_roots():
    found = pins("--root", "HOME/repos/other")
    assert "notes/plan.md" in found, found
    assert "hooks/**" not in found, found


def test_a_folder_without_git_is_refused():
    with tempfile.TemporaryDirectory() as tmp:
        proc = pinned(tmp, home=tmp)
    assert proc.returncode == 1, proc
    assert proc.stderr.startswith("pinned.py: not a git repo"), proc.stderr


def test_help_calls_print_help_and_exit_0():
    with tempfile.TemporaryDirectory() as tmp:
        for flag in ("-h", "--help"):
            proc = pinned(flag, home=tmp)
            assert proc.returncode == 0, proc
            assert proc.stdout.startswith("usage: pinned.py"), proc.stdout
        proc = pinned("help", home=tmp)
    assert proc.returncode == 0, proc
    assert "Exit codes:" in proc.stdout, proc.stdout


if __name__ == "__main__":
    failures = 0
    for name, func in sorted(globals().items()):
        if not name.startswith("test_") or not callable(func):
            continue
        try:
            func()
        except AssertionError as e:
            failures += 1
            print(f"FAIL {name}: {e}")
        else:
            print(f"ok   {name}")
    sys.exit(1 if failures else 0)
