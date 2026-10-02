#!/usr/bin/env python3
"""Checks for the harness dispatcher and the checks it discovers.

    python3 harness/tests/test_lint.py        # no pytest needed
    pytest harness/tests/test_lint.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
HARNESS = os.path.dirname(HERE)
LINT = os.path.join(HARNESS, "lint.py")
CHECKS = os.path.join(HARNESS, "checks")


def load_lint():
    spec = importlib.util.spec_from_file_location("harness_lint", LINT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_discovers_every_check_with_a_header():
    checks = load_lint().load_checks()
    ids = sorted(c["id"] for c in checks)
    # derived, not hardcoded: adding a check file must not fail this test
    files = sorted(f[:-3] for f in os.listdir(CHECKS) if f.endswith(".py"))
    assert ids == files, ids
    for check in checks:
        assert check["quadrant"] == "feedback/computational", check


def test_stale_doc_path_check_ignores_relative_tmp():
    check = os.path.join(CHECKS, "stale_doc_paths.py")
    with tempfile.TemporaryDirectory() as tmp:
        doc = os.path.join(tmp, "rules.md")
        with open(doc, "w") as fh:
            fh.write("--output ../tmp/out.json\n")
            fh.write("Write it to `/tmp/definitely_absent_here.json`.\n")
        proc = subprocess.run([sys.executable, check, doc], capture_output=True, text=True)
        assert ":1:" not in proc.stdout, proc.stdout
        assert ":2:" in proc.stdout, proc.stdout


def test_stale_doc_path_check_skips_historical_prose():
    lint = load_lint()
    check = next(c for c in lint.load_checks() if c["id"] == "stale_doc_paths")
    assert lint.applies(check, "notes/archive/Study/Unix/unix.md") is False
    assert lint.applies(check, "work/deck/unix/tmux.md") is False
    assert lint.applies(check, "website/content/posts/tmux.md") is False
    assert lint.applies(check, "docs/tasks/review.md") is True


def test_applies_globs_and_negation():
    lint = load_lint()
    check = {"applies": ["*.md", "!**/archive/**"]}
    assert lint.applies(check, "docs/readme.md")
    assert lint.applies(check, "archive/old.md") is False
    assert lint.applies(check, "deep/archive/old.md") is False
    assert lint.applies(check, "harness/lint.py") is False
    assert lint.applies({"applies": []}, "anything") is True


def test_convert_parses_findings_and_ignores_noise():
    lint = load_lint()
    found = lint.convert("demo", "feedback/computational", "/tmp/repo", "", [
        "/tmp/repo/a.py:12: message one",
        "not a finding",
        "",
    ])
    assert found == [
        {
            "check": "demo",
            "quadrant": "feedback/computational",
            "path": "a.py",
            "line": 12,
            "message": "message one",
        }
    ], found


def test_exec_bit_check_flags_a_script_and_clears_after_chmod():
    check = os.path.join(CHECKS, "script_exec_bit.py")
    with tempfile.TemporaryDirectory() as tmp:
        script = os.path.join(tmp, "run_me.py")
        with open(script, "w") as fh:
            fh.write("#!/usr/bin/env python3\nprint('hi')\n")
        before = subprocess.run([sys.executable, check, script], capture_output=True, text=True)
        assert "shebang but no exec bit" in before.stdout, before.stdout
        # both remedies, because a pasted fragment trips only the second one
        assert "chmod +x" in before.stdout, before.stdout
        assert "drop the shebang line" in before.stdout, before.stdout
        os.chmod(script, os.stat(script).st_mode | stat.S_IXUSR)
        after = subprocess.run([sys.executable, check, script], capture_output=True, text=True)
        assert after.stdout == "", after.stdout


def test_python_compiles_check_flags_a_broken_edit_and_clears_after_repair():
    check = os.path.join(CHECKS, "python_compiles.py")
    with tempfile.TemporaryDirectory() as tmp:
        broken = os.path.join(tmp, "broken.py")
        with open(broken, "w") as fh:
            fh.write("# an edit dropped the comment marker\ndef broken(:\n    pass\n")
        before = subprocess.run([sys.executable, check, broken], capture_output=True, text=True)
        assert "does not compile: invalid syntax" in before.stdout, before.stdout
        assert broken in before.stdout, before.stdout
        good = os.path.join(tmp, "good.py")
        with open(good, "w") as fh:
            fh.write("# an edit that kept the comment marker\nx = 1\n")
        after = subprocess.run([sys.executable, check, good, broken], capture_output=True, text=True)
        assert good not in after.stdout, after.stdout
        assert "broken.py:2" in after.stdout, after.stdout


def test_interpreter_check_reads_a_rule_and_a_shebang():
    check = os.path.join(CHECKS, "interpreter_resolves.py")
    with tempfile.TemporaryDirectory() as tmp:
        doc = os.path.join(tmp, "rules.md")
        with open(doc, "w") as fh:
            fh.write("Use a `#!/usr/bin/env python3.11` shebang.\n")
        proc = subprocess.run([sys.executable, check, doc], capture_output=True, text=True)
        assert "interpreter not on this machine: python3.11" in proc.stdout, proc.stdout
        good = os.path.join(tmp, "ok.md")
        with open(good, "w") as fh:
            fh.write("Use a `#!/usr/bin/env python3` shebang.\n")
        proc = subprocess.run([sys.executable, check, good], capture_output=True, text=True)
        assert proc.stdout == "", proc.stdout


def test_repo_local_check_overrides_the_machine_one():
    lint = load_lint()
    with tempfile.TemporaryDirectory() as tmp:
        directory = os.path.join(tmp, "scripts", "checks")
        os.makedirs(directory)
        with open(os.path.join(directory, "local.py"), "w") as fh:
            fh.write('# harness-check: {"id": "script_exec_bit", "applies": ["*.sh"]}\n')
        checks = lint.load_checks(lint.CHECK_DIRS + lint.repo_check_dirs(tmp))
        by_id = {c["id"]: c for c in checks}
        assert by_id["script_exec_bit"]["path"].startswith(directory), by_id
        assert by_id["script_exec_bit"]["applies"] == ["*.sh"], by_id


def test_interpreter_check_honours_the_ignore_marker():
    check = os.path.join(CHECKS, "interpreter_resolves.py")
    with tempfile.TemporaryDirectory() as tmp:
        doc = os.path.join(tmp, "quoted.md")
        with open(doc, "w") as fh:
            fh.write("It said `python3.11` once. <!-- lint:ignore -->\n")
        proc = subprocess.run([sys.executable, check, doc], capture_output=True, text=True)
        assert proc.stdout == "", proc.stdout


def test_markdown_check_skips_frontmatter_but_not_prose():
    check = os.path.join(CHECKS, "markdown_bare_path.py")
    with tempfile.TemporaryDirectory() as tmp:
        doc = os.path.join(tmp, "SKILL.md")
        with open(doc, "w") as fh:
            fh.write(
                "---\n"
                'argument-hint: "[--delete ~/Downloads/out.json]"\n'
                "---\n"
                "Save it as ~/Downloads/out.json.\n"
            )
        proc = subprocess.run([sys.executable, check, doc], capture_output=True, text=True)
        assert proc.stdout.count(":4:") == 1, proc.stdout
        assert ":2:" not in proc.stdout, proc.stdout


def test_dispatcher_end_to_end_in_a_temp_repo():
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "init", "-q", tmp], check=True)
        bad = os.path.join(tmp, "tool.sh")
        with open(bad, "w") as fh:
            fh.write("#!/bin/sh\necho hi\n")
        proc = subprocess.run(
            [sys.executable, LINT, "--json"], capture_output=True, text=True, cwd=tmp
        )
        assert proc.returncode == 1, proc.stderr
        report = json.loads(proc.stdout)
        assert [f["check"] for f in report["findings"]] == ["script_exec_bit"], report
        assert report["findings"][0]["path"] == "tool.sh", report
        assert report["failures"] == []

        os.chmod(bad, os.stat(bad).st_mode | stat.S_IXUSR)
        proc = subprocess.run([sys.executable, LINT], capture_output=True, text=True, cwd=tmp)
        assert proc.returncode == 0, proc.stdout
        assert "0 findings" in proc.stdout, proc.stdout


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
