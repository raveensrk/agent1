#!/usr/bin/env python3
"""Checks for the harness dispatcher and the checks it discovers.

    python3 harness/tests/test_lint.py        # no pytest needed
    pytest harness/tests/test_lint.py
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import shlex
import shutil
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


def test_repos_walk_finds_nested_repos_and_marks_them():
    """A repo inside a repo, or inside a plain folder, is walked as nested."""
    lint = load_lint()
    with tempfile.TemporaryDirectory() as tmp:
        for rel in ("outer/.git", "outer/vendored/inner/.git", "plain/checkout/.git"):
            os.makedirs(os.path.join(tmp, rel))
        old = lint.REPOS
        lint.REPOS = tmp
        try:
            targets = lint.collect_targets(argparse.Namespace(files=[], repos=True, changed=False))
        finally:
            lint.REPOS = old
        seen = {os.path.relpath(root, tmp): nested for root, _, _, nested in targets}
        assert seen == {"outer": False, "outer/vendored/inner": True, "plain/checkout": True}, seen


def test_edited_files_in_trash_are_ignored():
    """A file a session removed is not project content; the corpse must not nag."""
    lint = load_lint()
    with tempfile.TemporaryDirectory() as tmp:
        trash = os.path.join(tmp, ".Trash")
        os.makedirs(trash)
        killed = os.path.join(trash, "old-link")
        with open(killed, "w") as fh:
            fh.write("stale\n")
        kept = os.path.join(tmp, "kept.md")
        with open(kept, "w") as fh:
            fh.write("# kept\n")
        old = lint.TRASH
        lint.TRASH = trash
        try:
            targets = lint.collect_targets(
                argparse.Namespace(files=[killed, kept], repos=False, changed=False)
            )
        finally:
            lint.TRASH = old
        listed = [f for _, group, _, _ in targets for f in group]
        assert killed not in listed, listed
        assert kept in listed, listed


def test_walker_reports_a_symlink_to_a_repo_in_a_plain_folder():
    """No repo owns such a link, so no check run reaches it - the walker does."""
    lint = load_lint()
    with tempfile.TemporaryDirectory() as tmp:
        real = os.path.join(tmp, "elsewhere", "realrepo")
        os.makedirs(os.path.join(real, ".git"))
        plain = os.path.join(tmp, "plain")
        os.makedirs(plain)
        os.symlink(real, os.path.join(plain, "linked"))
        old_repos, old_argv = lint.REPOS, sys.argv
        lint.REPOS, sys.argv = tmp, ["lint.py", "--repos"]
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = lint.main()
        finally:
            lint.REPOS, sys.argv = old_repos, old_argv
        out = buf.getvalue()
        assert code == 1, out
        assert "symlink to a git repo" in out, out
        assert "1 findings" in out, out


def test_nested_repo_findings_warn_and_exit_zero():
    """The broken file is reported, but nobody acts on a vendored checkout."""
    lint = load_lint()
    with tempfile.TemporaryDirectory() as tmp:
        outer = os.path.join(tmp, "outer")
        subprocess.run(["git", "init", "-q", outer], check=True)
        with open(os.path.join(outer, "good.py"), "w") as fh:
            fh.write("x = 1\n")
        inner = os.path.join(outer, "vendored", "inner")
        subprocess.run(["git", "init", "-q", inner], check=True)
        with open(os.path.join(inner, "broken.py"), "w") as fh:
            fh.write("def broken(:\n    pass\n")
        old_repos, old_argv = lint.REPOS, sys.argv
        lint.REPOS, sys.argv = tmp, ["lint.py", "--repos"]
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = lint.main()
        finally:
            lint.REPOS, sys.argv = old_repos, old_argv
        out = buf.getvalue()
        assert code == 0, out
        assert "0 findings" in out, out
        assert "warning:" in out and "broken.py" in out, out
        assert "1 nested repos" in out, out


def test_discovers_every_check_with_a_header():
    lint = load_lint()
    checks = lint.load_checks()
    ids = sorted(c["id"] for c in checks)
    # derived, not hardcoded: adding a check file must not fail this test. Every
    # check directory counts, the public one and the private machine one.
    files = sorted(
        f[:-3]
        for directory in lint.CHECK_DIRS
        if os.path.isdir(directory)
        for f in os.listdir(directory)
        if f.endswith(".py")
    )
    assert ids == files, ids
    for check in checks:
        assert check["quadrant"] == "feedback/computational", check


def test_pi_prompt_filename_is_a_slash_command():
    check = os.path.join(CHECKS, "file_naming.py")
    with tempfile.TemporaryDirectory() as root:
        os.makedirs(os.path.join(root, ".git"))
        os.makedirs(os.path.join(root, "prompts"))
        good = os.path.join(root, "prompts", "estimate-cost.md")
        bad = os.path.join(root, "prompts", "bad--name.md")
        outside = os.path.join(root, "bad-name.md")
        for path in (good, bad, outside):
            open(path, "w").close()
        run = subprocess.run([sys.executable, check, good, bad, outside], capture_output=True, text=True)
        assert run.returncode == 0, run.stderr
        assert good not in run.stdout, run.stdout
        assert bad in run.stdout and outside in run.stdout, run.stdout
        # make finds only these exact names, so they are exempt like README.md
        makefile = os.path.join(root, "Makefile")
        open(makefile, "w").close()
        run = subprocess.run([sys.executable, check, makefile], capture_output=True, text=True)
        assert run.stdout == "", run.stdout


def test_file_naming_stops_at_a_linked_worktree_and_skips_deleted_files():
    """A worktree's .git is a file, and its folder name is the tool's, not the repo's.

    On 2026-10-10 the Stop hook flagged `.claude/worktrees/silly-bohr-0702b5`
    after the worktree was removed: nothing marked a root on the way up, so the
    walk reached the main repo and judged the app-chosen worktree name.
    """
    check = os.path.join(CHECKS, "file_naming.py")
    with tempfile.TemporaryDirectory() as root:
        os.makedirs(os.path.join(root, ".git"))
        tree = os.path.join(root, ".claude", "worktrees", "silly-bohr-0702b5")
        os.makedirs(os.path.join(tree, "docs"))
        with open(os.path.join(tree, ".git"), "w") as fh:
            fh.write("gitdir: ../../../.git/worktrees/silly-bohr-0702b5\n")
        kept = os.path.join(tree, "docs", "notes.md")
        open(kept, "w").close()
        gone = os.path.join(root, ".claude", "worktrees", "Gone-Tree", "notes.md")
        run = subprocess.run([sys.executable, check, kept, gone], capture_output=True, text=True)
        assert run.returncode == 0, run.stderr
        assert run.stdout == "", run.stdout


def test_file_naming_honours_the_allowlist():
    """A glob relative to ~/repos, repo name first, skips that tree and no other."""
    check = os.path.join(CHECKS, "file_naming.py")
    with tempfile.TemporaryDirectory() as tmp:
        repos = os.path.realpath(tmp)
        for repo in ("notes", "code"):
            os.makedirs(os.path.join(repos, repo, ".git"))
            os.makedirs(os.path.join(repos, repo, "Study"))
            open(os.path.join(repos, repo, "Study", "Old Note.md"), "w").close()
        # The allowlist lives in the private repo; this run points at a fixture.
        allow = os.path.join(repos, "allow.txt")
        with open(allow, "w") as fh:
            fh.write("# personal notes keep their human names\nnotes/*\n")
        spec = importlib.util.spec_from_file_location("file_naming", check)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.REPOS, module.ALLOW = repos, allow
        skipped = os.path.join(repos, "notes", "Study", "Old Note.md")
        checked = os.path.join(repos, "code", "Study", "Old Note.md")
        assert module.check(skipped) == [], module.check(skipped)
        assert "directory 'Study' is not snake_case" in "".join(module.check(checked))


def test_file_naming_exempts_the_names_a_tool_or_convention_fixes():
    """75 findings under ~/repos on 2026-10-10 named a file a build tool reads by
    its exact spelling (Makefile x47) or a doc of the README and LICENSE kind.
    The exemption is the exact spelling: a near miss is still a finding."""
    check = os.path.join(CHECKS, "file_naming.py")
    names = [
        "Makefile", "CMakeLists.txt", "package-lock.json", "Cargo.toml", "Cargo.lock",
        "Info.plist", "BUILD.bazel", ".markdownlint-cli2.jsonc",
        "README.txt", "CHANGELOG.md", "COPYING", "LICENSE.txt",
    ]
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "init", "-q", tmp], check=True)
        exempt = [os.path.join(tmp, "tool", name) for name in names]
        # a separate directory: macOS folds MakeFile and Makefile into one file
        near = [os.path.join(tmp, "near", name) for name in ("MakeFile", "Changelog.md", "Makefile.vcs")]
        # a path that does not exist is a deleted file and is skipped, so make them
        for path in exempt + near:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w").close()
        run = subprocess.run([sys.executable, check, *exempt, *near], capture_output=True, text=True)
        assert run.returncode == 0, run.stderr
        flagged = sorted(line.split(":1: ")[0] for line in run.stdout.splitlines())
        assert flagged == sorted(near), run.stdout


def test_file_naming_steers_junk_to_a_delete_by_git_state():
    """A Windows Zone.Identifier copy keeps its colon in any snake_case spelling
    (276 under ~/repos on 2026-10-10, all tracked), and Finder writes .DS_Store
    again after a delete. Both steer to a delete, never a rename: git rm when
    tracked, trash when not, and .DS_Store also into the repo's .gitignore."""
    check = os.path.join(CHECKS, "file_naming.py")
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "init", "-q", tmp], check=True)
        root = os.path.realpath(tmp)
        tracked = [
            os.path.join(root, "rtl", name)
            for name in ("cru.sv:Zone - Copy.Identifier", "cru.sv:Zone.Identifier",
                         "cru.sv:Zone - Copy (2).Identifier")
        ]
        finder = os.path.join(root, "web", ".DS_Store")
        for path in tracked + [finder]:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w").close()
        subprocess.run(["git", "-C", root, "add", "rtl"], check=True)
        subprocess.run(
            ["git", "-C", root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "zone"],
            check=True,
        )
        run = subprocess.run([sys.executable, check, *tracked, finder], capture_output=True, text=True)
        assert run.returncode == 0, run.stderr
        ignore = shlex.quote(os.path.join(root, ".gitignore"))
        assert run.stdout.splitlines() == [
            f"{path}:1: file '{os.path.basename(path)}' is a Windows Zone.Identifier leftover, "
            f"not content - delete it, do not rename it: git -C {shlex.quote(root)} rm -- {shlex.quote(path)}"
            for path in tracked
        ] + [
            f"{finder}:1: file '.DS_Store' is macOS Finder metadata, not content - delete and "
            f"ignore it: trash {shlex.quote(finder)} && printf '\\n.DS_Store\\n' >> {ignore}"
        ], run.stdout

        # Through the dispatcher: a colon inside the path still parses.
        proc = subprocess.run([sys.executable, LINT, "--json"], capture_output=True, text=True, cwd=tmp)
        report = json.loads(proc.stdout)
        assert report["failures"] == [], report
        paths = sorted(f["path"] for f in report["findings"] if f["check"] == "file_naming")
        assert paths == sorted(os.path.relpath(p, root) for p in tracked + [finder]), report

        # The steer works as printed, from a cwd in another repo.
        command = run.stdout.splitlines()[0].split("do not rename it: ", 1)[1]
        subprocess.run(command, shell=True, check=True, cwd=HERE, capture_output=True)
        assert not os.path.exists(tracked[0]), command
        status = subprocess.run(["git", "-C", root, "status", "--porcelain"], capture_output=True, text=True)
        assert 'D  "rtl/cru.sv:Zone - Copy.Identifier"' in status.stdout, status.stdout


def test_file_naming_lets_a_skill_directory_carry_its_kebab_name():
    """skill_frontmatter.py wants a skill's directory to match its kebab-case
    name, so a snake_case rename traded one finding for another: 12 under
    ~/repos on 2026-10-10, in .agents/skills/, .claude/skills/ and a repo root.
    The files inside the directory are still checked."""
    check = os.path.join(CHECKS, "file_naming.py")
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "init", "-q", tmp], check=True)
        root = os.path.realpath(tmp)
        skill = os.path.join(root, ".agents", "skills", "page-precheck")
        upper = os.path.join(root, "Page Check")
        for directory in (skill, upper):
            os.makedirs(directory)
            open(os.path.join(directory, "SKILL.md"), "w").close()
        inside = [os.path.join(skill, name) for name in ("SKILL.md", "state.yaml", "session-log.md")]
        # kebab-case, but no SKILL.md: an ordinary directory
        plain = os.path.join(root, "docs", "how-to", "x.md")
        for path in inside + [plain]:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "a").close()
        run = subprocess.run(
            [sys.executable, check, *inside, os.path.join(upper, "SKILL.md"), plain],
            capture_output=True, text=True,
        )
        assert run.returncode == 0, run.stderr
        assert "directory 'page-precheck'" not in run.stdout, run.stdout
        assert f"{inside[2]}:1: file 'session-log.md'" in run.stdout, run.stdout
        # a skill name is kebab-case, so a directory that is not stays a finding
        assert "directory 'Page Check'" in run.stdout, run.stdout
        assert "directory 'how-to'" in run.stdout, run.stdout


def test_stale_doc_path_check_ignores_relative_tmp():
    check = os.path.join(CHECKS, "stale_doc_paths.py")
    with tempfile.TemporaryDirectory() as tmp:
        doc = os.path.join(tmp, "rules.md")
        with open(doc, "w") as fh:
            fh.write("--output ../tmp/out.json\n")
            fh.write("Write it to `/tmp/definitely_absent_here.json`.\n")
            fh.write("The socket is `/tmp/bobko.aerospace-$USER.sock`.\n")
        proc = subprocess.run([sys.executable, check, doc], capture_output=True, text=True)
        assert ":1:" not in proc.stdout, proc.stdout
        assert ":2:" in proc.stdout, proc.stdout
        assert ":3:" not in proc.stdout, proc.stdout


def test_harness_doc_path_check_flags_a_missing_spawned_file():
    # The motivating case: a file the harness spawns, named in prose, then
    # deleted, so the spawner keeps reaching for a path that is not there.
    check = os.path.join(CHECKS, "harness_doc_paths.py")
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "harness", "checks"))
        doc = os.path.join(tmp, "rules.md")
        with open(doc, "w") as fh:
            fh.write("The check is `harness/checks/example_check.py`, run by lint.\n")
            fh.write("lint:ignore harness/checks/gone.py is named but excused.\n")
            fh.write("A skill path like scripts/todo.el is relative to the skill.\n")
        proc = subprocess.run([sys.executable, check, doc], capture_output=True, text=True)
        assert ":1:" in proc.stdout, proc.stdout
        assert "example_check.py" in proc.stdout, proc.stdout
        assert ":2:" not in proc.stdout, proc.stdout
        assert ":3:" not in proc.stdout, proc.stdout

        # Restoring the file clears it, and a doc outside a repo with a
        # harness/ directory is never in scope.
        open(os.path.join(tmp, "harness", "checks", "example_check.py"), "w").close()
        proc = subprocess.run([sys.executable, check, doc], capture_output=True, text=True)
        assert proc.stdout == "", proc.stdout
        outside = os.path.join(tmp, "elsewhere")
        os.makedirs(outside)
        lonely = os.path.join(outside, "notes.md")
        with open(lonely, "w") as fh:
            fh.write("harness/checks/example_check.py\n")
        proc = subprocess.run([sys.executable, check, lonely], capture_output=True, text=True)
        assert proc.stdout == "", proc.stdout


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


def test_convert_parses_findings_and_returns_the_rest():
    lint = load_lint()
    found, stray = lint.convert("demo", "feedback/computational", "/tmp/repo", "", [
        "/tmp/repo/a.py:12: message one",
        "/tmp/repo/b.sv:Zone - Copy.Identifier:1: message two",
        "/tmp/repo/c.py: message with no line",
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
        },
        {
            "check": "demo",
            "quadrant": "feedback/computational",
            "path": "b.sv:Zone - Copy.Identifier",
            "line": 1,
            "message": "message two",
        },
    ], found
    # A line that does not parse comes back for the caller to fail on; blank
    # lines are not output. A colon inside a path parses, one before a space
    # does not.
    assert stray == ["/tmp/repo/c.py: message with no line", "not a finding"], stray


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


def test_python_compiles_check_sees_an_extensionless_script():
    """~/dot/script/yt-wl has a python shebang and no .py name; the globs hid it."""
    check = os.path.join(CHECKS, "python_compiles.py")
    with tempfile.TemporaryDirectory() as tmp:
        script = os.path.join(tmp, "yt-wl")
        with open(script, "w") as fh:
            fh.write("#!/usr/bin/env python3\ndef broken(:\n    pass\n")
        broken = subprocess.run([sys.executable, check, script], capture_output=True, text=True)
        assert "does not compile: invalid syntax" in broken.stdout, broken.stdout
        assert script in broken.stdout, broken.stdout
        prose = os.path.join(tmp, "notes.md")
        with open(prose, "w") as fh:
            fh.write("# prose, not python\n")
        clean = subprocess.run([sys.executable, check, script, prose], capture_output=True, text=True)
        assert prose not in clean.stdout, clean.stdout
        assert clean.stdout.count("does not compile") == 1, clean.stdout


def test_python_compiles_check_reaches_an_extensionless_script_through_the_dispatcher():
    """The gap was the glob, so the check must match with no applies patterns."""
    lint = load_lint()
    checks = {c["id"]: c for c in lint.load_checks()}
    check = checks["python_compiles"]
    assert lint.applies(check, "script/yt-wl"), check
    assert lint.applies(check, "harness/lint.py"), check


def test_interpreter_check_reads_a_rule_and_a_shebang():
    check = os.path.join(CHECKS, "interpreter_resolves.py")
    with tempfile.TemporaryDirectory() as tmp:
        # python3.99 does not exist, so the finding holds whatever this machine has installed.
        assert shutil.which("python3.99") is None, "python3.99 is installed; pick another made-up name"
        doc = os.path.join(tmp, "rules.md")
        with open(doc, "w") as fh:
            fh.write("Use a `#!/usr/bin/env python3.99` shebang.\n")
        proc = subprocess.run([sys.executable, check, doc], capture_output=True, text=True)
        assert "interpreter not on this machine: python3.99" in proc.stdout, proc.stdout
        good = os.path.join(tmp, "ok.md")
        with open(good, "w") as fh:
            fh.write("Use a `#!/usr/bin/env python3` shebang.\n")
        proc = subprocess.run([sys.executable, check, good], capture_output=True, text=True)
        assert proc.stdout == "", proc.stdout


def test_interpreter_check_reads_a_bare_code_span():
    """common.md names interpreters as bare spans: (`python3` is 3.14; `python3.15` ...)."""
    check = os.path.join(CHECKS, "interpreter_resolves.py")
    with tempfile.TemporaryDirectory() as tmp:
        assert shutil.which("python3.99") is None, "python3.99 is installed; pick another made-up name"
        doc = os.path.join(tmp, "rules.md")
        with open(doc, "w") as fh:
            fh.write("(`python3` is the default; `python3.99` is installed too)\n")
        proc = subprocess.run([sys.executable, check, doc], capture_output=True, text=True)
        assert "interpreter not on this machine: python3.99" in proc.stdout, proc.stdout
        # Names that only start like an interpreter are not interpreters.
        with open(doc, "w") as fh:
            fh.write("Install `python3.99-pip`, keep it `pythonic`, see `sh.99x`.\n")
        proc = subprocess.run([sys.executable, check, doc], capture_output=True, text=True)
        assert proc.stdout == "", proc.stdout


def test_nested_git_repo_check_reports_a_nested_repo_and_honours_the_allowlist():
    """A repo under mine is a finding; an allowed clone and a clean file are not."""
    check = os.path.join(CHECKS, "nested_git_repo.py")
    with tempfile.TemporaryDirectory() as tmp:
        outer = os.path.join(tmp, "outer")
        inner = os.path.join(outer, "vendored", "inner")
        os.makedirs(os.path.join(inner, ".git"))
        subprocess.run(["git", "init", "-q", outer], check=True)
        edited = os.path.join(inner, "kept.py")
        with open(edited, "w") as fh:
            fh.write("x = 1\n")
        elsewhere = os.path.join(tmp, "elsewhere", "clone")
        os.makedirs(os.path.join(elsewhere, ".git"))
        link = os.path.join(outer, "linked")
        os.symlink(elsewhere, link)
        proc = subprocess.run([sys.executable, check, edited], capture_output=True, text=True, cwd=outer)
        assert "nested git repo" in proc.stdout, proc.stdout
        assert "vendored/inner" in proc.stdout, proc.stdout
        assert "symlink to a git repo" in proc.stdout, proc.stdout
        os.unlink(link)
        # The allowlist lives in the private repo; this run points at a fixture.
        allow = os.path.join(tmp, "allow.txt")
        allowlist = {"allowed": "# a clone from the internet\nvendored/*\n", "empty": "# nothing yet\n"}
        spec = importlib.util.spec_from_file_location("nested_git_repo", check)
        module = importlib.util.module_from_spec(spec)
        old_argv, cwd = sys.argv, os.getcwd()
        sys.argv = ["nested_git_repo.py", edited]
        try:
            spec.loader.exec_module(module)
            os.chdir(outer)
            for name, body in allowlist.items():
                with open(allow, "w") as fh:
                    fh.write(body)
                module.ALLOW = allow
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    module.main()
                assert (buf.getvalue() == "") == (name == "allowed"), (name, buf.getvalue())
        finally:
            sys.argv, _ = old_argv, os.chdir(cwd)


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
        # A form the check matches (see the rule test), so only the marker keeps it quiet.
        with open(doc, "w") as fh:
            fh.write("Use a `#!/usr/bin/env python3.99` shebang. <!-- lint:ignore -->\n")
        proc = subprocess.run([sys.executable, check, doc], capture_output=True, text=True)
        assert proc.stdout == "", proc.stdout


def test_markdown_check_skips_a_code_span_that_wraps_a_line():
    """A wrapped command is still a command: the span opened on the line before."""
    check = os.path.join(CHECKS, "markdown_bare_path.py")
    with tempfile.TemporaryDirectory() as tmp:
        doc = os.path.join(tmp, "review.md")
        with open(doc, "w") as fh:
            fh.write("- evidence: `python3 lint.py\n")
            fh.write("  ~/tmp/definitely_absent_one.md ~/tmp/definitely_absent_two.md` printed 0 findings\n")
            fh.write("- fix: one line in ~/tmp/definitely_absent_three.md\n")
        proc = subprocess.run([sys.executable, check, doc], capture_output=True, text=True)
        assert ":1:" not in proc.stdout, proc.stdout
        assert ":2:" not in proc.stdout, proc.stdout
        assert ":3:" in proc.stdout, proc.stdout


def test_markdown_check_leaves_at_imports_alone():
    """common.md sanctions `@~/path` in AGENTS.md; a link there stops being an import."""
    check = os.path.join(CHECKS, "markdown_bare_path.py")
    with tempfile.TemporaryDirectory() as tmp:
        doc = os.path.join(tmp, "AGENTS.md")
        with open(doc, "w") as fh:
            fh.write("# AGENTS\n\n")
            fh.write("@~/tmp/definitely_absent_rules.md\n\n")
            fh.write("Read: ~/tmp/definitely_absent_notes.md\n")
        proc = subprocess.run([sys.executable, check, doc], capture_output=True, text=True)
        assert ":3:" not in proc.stdout, proc.stdout
        assert ":5:" in proc.stdout, proc.stdout


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
            # The help arm keeps cli_help quiet: a no-arg runnable owes it too.
            fh.write('#!/bin/sh\ncase "${1:-}" in -h|--help|help) echo "usage: tool.sh"; exit 0;; esac\necho hi\n')
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


def test_dispatcher_reports_a_name_that_is_not_snake_case():
    """Until 2026-10-09 file_naming printed `path: message` with no line number
    and the dispatcher dropped every one, so the rule never fired through lint."""
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "init", "-q", tmp], check=True)
        for rel in ("script/find-link.py", "docs/Old-Drafts/v1/note.txt"):
            os.makedirs(os.path.join(tmp, os.path.dirname(rel)))
            with open(os.path.join(tmp, rel), "w") as fh:
                fh.write("x = 1\n")
        proc = subprocess.run(
            [sys.executable, LINT, "--json"], capture_output=True, text=True, cwd=tmp
        )
        assert proc.returncode == 1, proc.stderr
        report = json.loads(proc.stdout)
        assert report["failures"] == [], report
        found = sorted((f["check"], f["path"], f["line"]) for f in report["findings"])
        assert found == [
            ("file_naming", "docs/Old-Drafts/v1/note.txt", 1),
            ("file_naming", "script/find-link.py", 1),
        ], report
        # The rename steers to the offending directory itself, not the file's
        # own directory, and to absolute paths on both sides.
        root = os.path.realpath(tmp)
        messages = {f["path"]: f["message"] for f in report["findings"]}
        assert messages["docs/Old-Drafts/v1/note.txt"].endswith(
            f"git mv {root}/docs/Old-Drafts {root}/docs/old_drafts"
        ), messages
        assert messages["script/find-link.py"].endswith(f"{root}/script/find_link.py"), messages


def test_dispatcher_fails_a_check_whose_output_does_not_parse():
    """A stdout line that is not `path:line: message` fails the check, exit 2,
    naming the check and the line: dropping it hid file_naming for good. The
    lines that do parse still count."""
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "init", "-q", tmp], check=True)
        checks = os.path.join(tmp, "scripts", "checks")
        os.makedirs(checks)
        with open(os.path.join(checks, "drift.py"), "w") as fh:
            fh.write(
                '# harness-check: {"id": "drift", "applies": ["*.txt"]}\n'
                "import sys\n"
                "for path in sys.stdin.read().splitlines():\n"
                '    print(f"{path}:3: a finding that parses")\n'
                '    print(f"{path}: a finding with no line")\n'
            )
        with open(os.path.join(tmp, "note.txt"), "w") as fh:
            fh.write("hi\n")
        proc = subprocess.run(
            [sys.executable, LINT, "--json"], capture_output=True, text=True, cwd=tmp
        )
        assert proc.returncode == 2, proc.stdout
        report = json.loads(proc.stdout)
        assert [(f["check"], f["path"], f["line"]) for f in report["findings"]] == [
            ("drift", "note.txt", 3)
        ], report
        assert [f["check"] for f in report["failures"]] == ["drift"], report
        assert "note.txt: a finding with no line" in report["failures"][0]["error"], report

        proc = subprocess.run([sys.executable, LINT], capture_output=True, text=True, cwd=tmp)
        assert proc.returncode == 2, proc.stdout
        assert "lint: check drift failed" in proc.stderr, proc.stderr
        assert "note.txt: a finding with no line" in proc.stderr, proc.stderr


def test_cli_help_check_wants_both_flags_and_names_the_missing_one():
    check = os.path.join(CHECKS, "cli_help.py")
    with tempfile.TemporaryDirectory() as tmp:
        script = os.path.join(tmp, "tool.sh")

        def run():
            proc = subprocess.run([sys.executable, check, script], capture_output=True, text=True)
            assert proc.returncode == 0, proc.stderr
            return proc.stdout

        with open(script, "w") as fh:
            fh.write('#!/bin/sh\nif [ "$#" -lt 1 ]; then exit 2; fi\necho "$1"\n')
        os.chmod(script, os.stat(script).st_mode | stat.S_IXUSR)
        assert "mentions neither -h nor --help" in run(), run()
        # -h alone is half the pair, and the finding says which half is missing.
        # `${1:-}' is the safe-quoting idiom and must count as option parsing too.
        with open(script, "w") as fh:
            fh.write('#!/bin/sh\ncase "${1:-}" in\n  -h) echo "usage: tool.sh"; exit 0;;\nesac\n')
        assert "mentions no --help" in run(), run()
        with open(script, "w") as fh:
            fh.write('#!/bin/sh\ncase "${1:-}" in\n  -h|--help) echo "usage: tool.sh"; exit 0;;\nesac\n')
        assert "mentions no `help` command" in run(), run()
        with open(script, "w") as fh:
            fh.write('#!/bin/sh\ncase "${1:-}" in\n  -h|--help) echo "usage: tool.sh"; exit 0;;\n'
                     '  help) echo "usage: tool.sh, in full"; exit 0;;\nesac\n')
        assert run() == ""


def test_cli_help_check_wants_help_from_a_no_arg_runnable_but_not_a_hook_or_test():
    """experimental.md: a program's docs live inside it, behind -h and --help,
    options or not. A no-arg git hook or test is called, not typed."""
    check = os.path.join(CHECKS, "cli_help.py")
    with tempfile.TemporaryDirectory() as tmp:

        def run(rel, body):
            path = os.path.join(tmp, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as fh:
                fh.write(body)
            os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
            proc = subprocess.run([sys.executable, check, path], capture_output=True, text=True)
            assert proc.returncode == 0, proc.stderr
            return proc.stdout

        bare = "#!/bin/sh\necho hi\n"
        out = run("tool.sh", bare)
        assert "runnable mentions neither -h nor --help" in out, out
        # Both ways out are named: a sourced file, and a callback.
        assert "chmod -x" in out and "cli_help_allow.txt" in out, out
        # The suggested idioms pass as written: shell prints its header comment,
        # python its docstring.
        shell = out.split("shell, from the header comment: `")[1].split("`")[0]
        assert run("tool.sh", f"#!/bin/sh\n# Say hi.\n{shell}\necho hi\n") == ""
        idiom = out.split("python, from the module docstring: `")[1].split("`")[0]
        assert run("tool.py", f'#!/usr/bin/env python3\n"""Say hi."""\nimport sys\n{idiom}\n') == ""
        # argparse with no option added still answers -h and --help ...
        parse = ('#!/usr/bin/env python3\nimport argparse\n'
                 'argparse.ArgumentParser(description="Say hi.").parse_args()\n')
        assert run("tool.py", parse).count("mentions no `help` command") == 1
        helped = parse.replace("import argparse\n", 'import argparse, sys\n'
                               'if sys.argv[1:2] == ["help"]: print(__doc__); sys.exit(0)\n')
        assert run("tool.py", helped) == ""
        # ... unless help is off, and another object's parse_args binds nothing.
        assert "mentions neither" in run("tool.py", parse.replace('description="Say hi."', "add_help=False"))
        other = ('#!/usr/bin/env python3\nimport sys\n'
                 'class C:\n    def parse_args(self, a):\n        return a\n'
                 'C().parse_args(sys.argv[1:])\n')
        assert "mentions neither" in run("tool.py", other)
        # A no-arg hook or a runner-collected test is exempt ...
        for rel in ("hooks/pre-commit", ".githooks/pre-push", "githooks/pre-push",
                    "test_tool.py", "tool_test.py", "tool.test.ts"):
            assert run(rel, bare) == "", rel
        # ... a typed runner is not, and neither is a hook that parses options.
        for rel in ("tests/run_all.sh", "test_collage.sh"):
            assert "runnable mentions" in run(rel, bare), rel
        parsed = '#!/bin/sh\nif [ "$#" -lt 1 ]; then exit 2; fi\n'
        assert "mentions neither -h nor --help" in run("hooks/commit-msg", parsed)


def test_cli_help_check_leaves_argparse_alone_unless_add_help_is_off():
    """argparse binds -h and --help by default; a long-only flag is fine here,
    because short aliases are the optional half of the rule."""
    check = os.path.join(CHECKS, "cli_help.py")
    with tempfile.TemporaryDirectory() as tmp:
        script = os.path.join(tmp, "app.py")
        head = ("#!/usr/bin/env python3\nimport argparse, sys\n"
                'if sys.argv[1:2] == ["help"]: print("long"); sys.exit(0)\n'
                "\np = argparse.ArgumentParser()\n")
        with open(script, "w") as fh:
            fh.write(head + 'p.add_argument("--only", action="append")\np.parse_args()\n')
        os.chmod(script, os.stat(script).st_mode | stat.S_IXUSR)

        def run():
            proc = subprocess.run([sys.executable, check, script], capture_output=True, text=True)
            return proc.stdout

        assert run() == ""
        with open(script, "w") as fh:
            fh.write(head.replace("ArgumentParser()", "ArgumentParser(add_help=False)")
                     + 'p.add_argument("--only", action="append")\np.parse_args()\n')
        assert "mentions neither -h nor --help" in run(), run()
        with open(script, "w") as fh:
            fh.write(head.replace("ArgumentParser()", "ArgumentParser(add_help=False)")
                     + 'p.add_argument("-h", "--help", action="help")\np.parse_args()\n')
        assert run() == ""
        # A shared-flags parser that only feeds parents= turns no help off.
        common = 'common = argparse.ArgumentParser(add_help=False)\ncommon.add_argument("-q")\n'
        with open(script, "w") as fh:
            fh.write(head + common + 'sub = p.add_subparsers()\n'
                     'sub.add_parser("build", parents=[common])\np.parse_args()\n')
        assert run() == ""
        # A subcommand built with add_help=False does lose its help.
        with open(script, "w") as fh:
            fh.write(head + common + 'sub = p.add_subparsers()\n'
                     'sub.add_parser("build", parents=[common], add_help=False)\np.parse_args()\n')
        assert "mentions neither -h nor --help" in run(), run()


def test_cli_help_check_wants_a_help_command():
    """experimental.md: -h and --help print short help, `<program> help` the long
    help. argparse's action="help" is the flag binding, not the command."""
    check = os.path.join(CHECKS, "cli_help.py")
    with tempfile.TemporaryDirectory() as tmp:

        def run(name, body):
            path = os.path.join(tmp, name)
            with open(path, "w") as fh:
                fh.write(body)
            os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
            proc = subprocess.run([sys.executable, check, path], capture_output=True, text=True)
            assert proc.returncode == 0, proc.stderr
            return proc.stdout

        head = "#!/usr/bin/env python3\nimport argparse\np = argparse.ArgumentParser()\n"
        assert "mentions no `help` command" in run("a.py", head + "p.parse_args()\n")
        off = head.replace("ArgumentParser()", "ArgumentParser(add_help=False)")
        out = run("a.py", off + 'p.add_argument("-h", "--help", action="help")\np.parse_args()\n')
        assert "mentions no `help` command" in out, out
        sub = head + 'sub = p.add_subparsers()\nsub.add_parser("help")\np.parse_args()\n'
        assert run("a.py", sub) == ""
        shell = ('#!/bin/sh\ncase "${1:-}" in -h|--help) echo short; exit 0;; esac\n'
                 'if [ "$1" = help ]; then echo long; exit 0; fi\n')
        assert run("b.sh", shell) == ""
        # The word in prose is not a command.
        prose = '#!/bin/sh\n# -h, --help: print some help\necho hi\n'
        assert "no `help` command" in run("b.sh", prose)


def test_cli_help_check_reads_code_not_strings():
    """A test that writes a fake CLI into a string mentions sys.argv without
    parsing a single option: flagging it asked a test file for -h and --help
    (found on test_reddit_dl.py). Real argv use still owes the pair."""
    check = os.path.join(CHECKS, "cli_help.py")
    with tempfile.TemporaryDirectory() as tmp:
        script = os.path.join(tmp, "test_tool.py")

        def run():
            proc = subprocess.run([sys.executable, check, script], capture_output=True, text=True)
            assert proc.returncode == 0, proc.stderr
            return proc.stdout

        # sys.argv inside a fixture string is not a file that parses options.
        with open(script, "w") as fh:
            fh.write("#!/usr/bin/env python3\n"
                     "FAKE = 'import sys\\nprint(sys.argv[-1])\\n'\n"
                     "open('fake.py', 'w').write(FAKE)\n")
        os.chmod(script, os.stat(script).st_mode | stat.S_IXUSR)
        assert run() == "", run()
        # The same read in code, not in a string, is a CLI that owes the pair.
        with open(script, "w") as fh:
            fh.write('#!/usr/bin/env python3\nimport sys\nprint(sys.argv[1:])\n')
        assert "mentions neither -h nor --help" in run(), run()
        with open(script, "w") as fh:
            fh.write('#!/usr/bin/env python3\nimport sys\n'
                     'if sys.argv[1:2] in (["-h"], ["--help"], ["help"]):\n'
                     '    print("usage: test_tool.py")\n    sys.exit(0)\n')
        assert run() == "", run()


def test_cli_help_check_skips_non_executables_and_honours_the_allowlist():
    check = os.path.join(CHECKS, "cli_help.py")
    with tempfile.TemporaryDirectory() as tmp:
        script = os.path.join(tmp, "tool.sh")
        with open(script, "w") as fh:
            fh.write('#!/bin/sh\nif [ "$#" -eq 0 ]; then exit 2; fi\n')
        # No exec bit yet: a file nobody runs is not a command.
        proc = subprocess.run([sys.executable, check, script], capture_output=True, text=True)
        assert proc.stdout == "", proc.stdout
        os.chmod(script, os.stat(script).st_mode | stat.S_IXUSR)
        # A harness check reads paths on stdin; it is not a command.
        os.makedirs(os.path.join(tmp, "harness", "checks"))
        inside = os.path.join(tmp, "harness", "checks", "tool.sh")
        with open(inside, "w") as fh:
            fh.write('#!/bin/sh\nif [ "$#" -eq 0 ]; then exit 2; fi\n')
        os.chmod(inside, os.stat(inside).st_mode | stat.S_IXUSR)
        # The allowlist lives in the private repo; this run points at a fixture.
        spec = importlib.util.spec_from_file_location("cli_help", check)
        module = importlib.util.module_from_spec(spec)
        old_argv, cwd = sys.argv, os.getcwd()
        sys.argv = ["cli_help.py", script, inside]
        allow = os.path.join(tmp, "allow.txt")
        try:
            spec.loader.exec_module(module)
            os.chdir(tmp)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                module.main()
            out = buf.getvalue()
            assert "tool.sh:1: mentions" in out, out
            assert "harness/checks" not in out, out
            with open(allow, "w") as fh:
                fh.write("# not a CLI app\n" + os.path.basename(script) + "\n")
            module.ALLOW = allow
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                module.main()
            assert buf.getvalue() == "", buf.getvalue()
        finally:
            sys.argv, _ = old_argv, os.chdir(cwd)


def test_cli_help_check_skips_the_scratch_dir():
    """A probe under ~/tmp dies with the session, so the six-months-later author
    the rule protects never meets it. The boundary is the scratch path: one
    directory over, the same file is a finding again."""
    check = os.path.join(CHECKS, "cli_help.py")
    with tempfile.TemporaryDirectory() as tmp:
        scratch = os.path.join(tmp, "tmp")
        os.makedirs(scratch)
        script = os.path.join(scratch, "probe.py")
        body = '#!/usr/bin/env python3\nimport sys\nprint(sys.argv[1])\n'
        with open(script, "w") as fh:
            fh.write(body)
        os.chmod(script, os.stat(script).st_mode | stat.S_IXUSR)
        spec = importlib.util.spec_from_file_location("cli_help", check)
        module = importlib.util.module_from_spec(spec)
        old_argv = sys.argv
        sys.argv = ["cli_help.py", script]
        try:
            spec.loader.exec_module(module)
            module.SCRATCH = os.path.realpath(scratch)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                module.main()
            assert buf.getvalue() == "", buf.getvalue()
            # Not the scratch dir: a temp file anywhere else still owes the pair.
            module.SCRATCH = os.path.realpath(os.path.join(tmp, "elsewhere"))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                module.main()
            assert "mentions neither -h nor --help" in buf.getvalue(), buf.getvalue()
        finally:
            sys.argv = old_argv


def test_skill_frontmatter_flags_a_missing_block():
    # The motivating case: a sweep that did not know frontmatter rewrote it away,
    # and the file stayed valid markdown, so nothing else fired.
    check = os.path.join(CHECKS, "skill_frontmatter.py")
    with tempfile.TemporaryDirectory() as tmp:
        skill = os.path.join(tmp, "skills", "demo", "SKILL.md")
        os.makedirs(os.path.dirname(skill))
        with open(skill, "w") as fh:
            fh.write("______________________________________________________________________\n\n## name: demo description: gone\n")
        proc = subprocess.run([sys.executable, check, skill], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        assert "no YAML frontmatter" in proc.stdout, proc.stdout
        assert "name: demo" in proc.stdout, proc.stdout  # the fix names the directory


def test_skill_frontmatter_wants_the_directory_name_and_a_description():
    check = os.path.join(CHECKS, "skill_frontmatter.py")
    with tempfile.TemporaryDirectory() as tmp:
        skill = os.path.join(tmp, "skills", "demo", "SKILL.md")
        os.makedirs(os.path.dirname(skill))
        with open(skill, "w") as fh:
            fh.write("---\nname: other\n---\n\n# demo\n")
        proc = subprocess.run([sys.executable, check, skill], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        assert "does not match the directory" in proc.stdout, proc.stdout
        assert "no description" in proc.stdout, proc.stdout


def test_skill_frontmatter_is_quiet_on_a_good_skill():
    check = os.path.join(CHECKS, "skill_frontmatter.py")
    with tempfile.TemporaryDirectory() as tmp:
        skill = os.path.join(tmp, "skills", "demo", "SKILL.md")
        os.makedirs(os.path.dirname(skill))
        with open(skill, "w") as fh:
            fh.write('---\nname: "demo"\ndescription: Use when testing the check.\n---\n\n# demo\n')
        proc = subprocess.run([sys.executable, check, skill], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "", proc.stdout


def mdformat_bin():
    """The pinned mdformat, or None when this machine has no pipx install."""
    override = os.environ.get("MDFORMAT_BIN")
    if override:
        return override if os.path.exists(override) else None
    pinned = os.path.expanduser("~/.local/bin/mdformat")
    if os.path.exists(pinned):
        return pinned
    return None


def test_mdformat_check_flags_an_unformatted_file_and_steers():
    # The motivating case: a blank-line mess in a repo that pinned the tool. The
    # message must carry the command that fixes it, or the next attempt
    # reformats nothing.
    bin_path = mdformat_bin()
    if not bin_path:
        return  # no pinned mdformat on this machine
    check = os.path.join(CHECKS, "mdformat_check.py")
    with tempfile.TemporaryDirectory() as tmp:
        open(os.path.join(tmp, ".mdformat.toml"), "w").write("number = true\n")
        doc = os.path.join(tmp, "prose.md")
        with open(doc, "w") as fh:
            fh.write("# Title\n\nProse.\n\n\n\nMore prose.\n")
        env = dict(os.environ, MDFORMAT_BIN=bin_path)
        proc = subprocess.run([sys.executable, check, doc], capture_output=True, text=True, env=env)
        assert proc.returncode == 0, proc.stderr
        assert doc in proc.stdout, proc.stdout
        assert "fix: " in proc.stdout, proc.stdout


def test_mdformat_check_skips_a_repo_that_did_not_pin_the_tool():
    # mdformat's output is config-dependent, so without .mdformat.toml there is
    # no pinned invocation and nothing to enforce. The file is left alone.
    bin_path = mdformat_bin()
    if not bin_path:
        return
    check = os.path.join(CHECKS, "mdformat_check.py")
    with tempfile.TemporaryDirectory() as tmp:
        doc = os.path.join(tmp, "prose.md")
        with open(doc, "w") as fh:
            fh.write("# Title\n\nProse.\n\n\n\nMore prose.\n")
        env = dict(os.environ, MDFORMAT_BIN=bin_path)
        proc = subprocess.run([sys.executable, check, doc], capture_output=True, text=True, env=env)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "", proc.stdout


def test_mdformat_check_is_quiet_on_a_clean_file():
    bin_path = mdformat_bin()
    if not bin_path:
        return
    check = os.path.join(CHECKS, "mdformat_check.py")
    with tempfile.TemporaryDirectory() as tmp:
        open(os.path.join(tmp, ".mdformat.toml"), "w").write("number = true\n")
        doc = os.path.join(tmp, "prose.md")
        with open(doc, "w") as fh:
            fh.write("# Title\n\nProse.\n\nMore prose.\n")
        subprocess.run([bin_path, doc], check=True, capture_output=True)
        env = dict(os.environ, MDFORMAT_BIN=bin_path)
        proc = subprocess.run([sys.executable, check, doc], capture_output=True, text=True, env=env)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "", proc.stdout


def test_mdformat_check_refuses_a_binary_without_the_plugin():
    # Without mdformat-frontmatter, mdformat rewrites SKILL.md frontmatter into
    # a setext heading. That is a broken tool, not a finding, so: exit 2 and a
    # steering message, never a finding on stdout.
    check = os.path.join(CHECKS, "mdformat_check.py")
    with tempfile.TemporaryDirectory() as tmp:
        open(os.path.join(tmp, ".mdformat.toml"), "w").write("number = true\n")
        fake = os.path.join(tmp, "mdformat")
        with open(fake, "w") as fh:
            fh.write("#!/bin/sh\necho 'mdformat 1.0.0'\nexit 0\n")
        os.chmod(fake, 0o755)
        doc = os.path.join(tmp, "prose.md")
        with open(doc, "w") as fh:
            fh.write("# Title\n")
        env = dict(os.environ, MDFORMAT_BIN=fake)
        proc = subprocess.run([sys.executable, check, doc], capture_output=True, text=True, env=env)
        assert proc.returncode == 2, (proc.returncode, proc.stdout, proc.stderr)
        assert "mdformat-frontmatter" in proc.stderr, proc.stderr
        assert proc.stdout.strip() == "", proc.stdout


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
