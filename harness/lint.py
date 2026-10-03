#!/usr/bin/env python3
"""harness lint - one command that runs every discovered check.

A check is an executable script in a `checks/` directory whose first lines
carry a header:

    # harness-check: {"id": "script_exec_bit", "applies": ["*.py", "*.sh"],
    #                  "quadrant": "feedback/computational"}

The dispatcher hands the candidate file paths to the check on stdin, one per
line. The check prints findings as `path:line: message` and exits 0. A nonzero
exit means the check itself is broken and is reported as a check failure, not
as a finding. Adding a check is dropping a file in `checks/`; nothing here
needs to change.

Usage:
  lint.py                       check this repo: git-tracked and untracked files
  lint.py --changed             check only what changed against HEAD, plus untracked files
  lint.py FILE...               check only those files
  lint.py --repos               check every git repo under ~/repos
  lint.py --list                list the checks and their quadrant
  lint.py --check ID            run one check only
  lint.py --json                machine-readable output
  lint.py --timing              print how long each check took

Exit: 0 clean, 1 findings, 2 a check failed.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.realpath(__file__))
REPOS = os.path.expanduser("~/repos")
# Public checks live with this file. agent2 is the private machine config, so
# its checks are picked up only when that directory exists - the same rule
# common.md uses for agent2/AGENTS.md.
CHECK_DIRS = [os.path.join(HERE, "checks"), os.path.join(REPOS, "agent2", "harness", "checks")]
HEADER = re.compile(r"^#\s*harness-check:\s*(\{.*\})\s*$")
FINDING = re.compile(r"^(?P<path>[^:]*?):(?P<line>\d+):\s*(?P<message>.*)$")
MAX_BYTES = 1_000_000
TRASH = os.path.expanduser("~/.Trash")


def git(cwd: str, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", cwd, *args], capture_output=True, text=True, timeout=120
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout if proc.returncode == 0 else ""


def repo_root(path: str) -> str | None:
    root = git(path, "rev-parse", "--show-toplevel").strip()
    return root or None


def repo_files(root: str) -> list[str]:
    """Tracked files plus untracked files that are not git-ignored."""
    listing = git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    return _existing(root, listing.split("\0"))


def changed_files(root: str) -> list[str]:
    """Files this session touched: changed against HEAD, plus untracked ones.

    The trigger uses this so a repo full of old findings does not nag on every
    run; the full-population run is a deliberate act, not a side effect.
    """
    names = git(root, "diff", "--name-only", "--diff-filter=d", "HEAD").splitlines()
    names += git(root, "ls-files", "-z", "--others", "--exclude-standard").split("\0")
    if not names:
        return repo_files(root)
    return _existing(root, names)


def _existing(root: str, names) -> list[str]:
    out = []
    for name in names:
        if not name:
            continue
        path = os.path.join(root, name)
        try:
            if os.path.isfile(path) and os.path.getsize(path) <= MAX_BYTES:
                out.append(path)
        except OSError:
            continue
    return sorted(set(out))


def load_checks(directories: list[str] | None = None) -> list[dict]:
    """Read every check header under the given directories, repo-local last."""
    checks: dict[str, dict] = {}
    for directory in directories if directories is not None else CHECK_DIRS:
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            path = os.path.join(directory, name)
            if not os.path.isfile(path) or name.startswith("_"):
                continue
            try:
                with open(path, encoding="utf-8") as fh:
                    head = [next(fh, "") for _ in range(12)]
            except OSError:
                continue
            meta = None
            for line in head:
                m = HEADER.match(line.strip())
                if m:
                    try:
                        meta = json.loads(m.group(1))
                    except json.JSONDecodeError:
                        meta = None
                    break
            if not meta or "id" not in meta:
                print(f"lint: {path}: no harness-check header, skipped", file=sys.stderr)
                continue
            meta["path"] = path
            meta.setdefault("applies", [])
            meta.setdefault("quadrant", "feedback/computational")
            # A check in the repo under test overrides a machine-wide one with
            # the same id, so a project can tighten or replace a shared check.
            checks[meta["id"]] = meta
    return [checks[key] for key in sorted(checks)]


def repo_check_dirs(root: str) -> list[str]:
    """Checks the repo under test carries itself."""
    return [os.path.join(root, "scripts", "checks")]


def applies(check: dict, rel: str) -> bool:
    """`applies` globs select the files a check sees; a leading `!` drops them."""
    patterns = check["applies"]
    if not patterns:
        return True
    base = os.path.basename(rel)
    keep = False
    for pattern in patterns:
        drop = pattern.startswith("!")
        glob = pattern[1:] if drop else pattern
        # `**/x` must also match a path that starts with x, since fnmatch has no
        # real globstar.
        globs = {glob, glob[3:] if glob.startswith("**/") else glob}
        if any(fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(base, g) for g in globs):
            if drop:
                return False
            keep = True
    return keep


def convert(check_id: str, quadrant: str, root: str, label: str, found: list[dict]) -> list[dict]:
    out = []
    for line in found:
        if not line.strip():
            continue
        m = FINDING.match(line)
        if not m:
            continue
        path = m.group("path")
        if os.path.isabs(path):
            path = os.path.relpath(path, root)
        out.append(
            {
                "check": check_id,
                "quadrant": quadrant,
                "path": f"{label}/{path}" if label else path,
                "line": int(m.group("line")),
                "message": m.group("message").strip(),
            }
        )
    return out


def run_check(check: dict, root: str, label: str, files: list[str]):
    started = time.monotonic()
    try:
        proc = subprocess.run(
            [sys.executable, check["path"]],
            input="\n".join(files),
            capture_output=True,
            text=True,
            cwd=root,
            timeout=300,
        )
    except (OSError, subprocess.SubprocessError) as e:
        return [], f"{type(e).__name__}: {e}", time.monotonic() - started
    elapsed = time.monotonic() - started
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        return [], f"exit {proc.returncode}: {detail[-1] if detail else 'no output'}", elapsed
    return convert(check["id"], check["quadrant"], root, label, proc.stdout.splitlines()), None, elapsed


SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache", ".tox"}
NESTED_DEPTH = 3


def nested_repos(root: str) -> list[str]:
    """Repo roots below ROOT, to a bounded depth: vendored drops and clones.

    Their findings are warnings rather than findings, because nobody here edits
    a third-party checkout. A found repo is not descended into: it is one unit.
    """
    base = root.rstrip("/").count("/")
    found: list[str] = []
    for here, dirs, files in os.walk(root):
        # Test for .git before pruning it: a linked worktree carries it as a file.
        if here != root and (".git" in dirs or ".git" in files):
            found.append(here)
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        if here.count("/") - base >= NESTED_DEPTH:
            dirs[:] = []
    return found


def link_findings() -> list[dict]:
    """Symlinks under ~/repos that point at a repo. The rule forbids them.

    nested_git_repo.py decides the rule where a repo owns the link. A link in a
    plain folder - `income_tax_fy_2025_2026/ledger -> ~/repos/ledger` - has no
    repo, so no check run ever sees it; the walker reports it here instead, as a
    finding, because the link is the user's own and the fix is his to make.
    """
    out = []
    for name in sorted(os.listdir(REPOS)):
        top = os.path.join(REPOS, name)
        if not os.path.isdir(top):
            continue
        for here, dirs, files in os.walk(top):
            if here.count("/") - top.rstrip("/").count("/") >= NESTED_DEPTH:
                dirs[:] = []
            else:
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for entry in list(dirs) + files:
                path = os.path.join(here, entry)
                if not os.path.islink(path) or not os.path.isdir(path):
                    continue
                if not os.path.exists(os.path.join(path, ".git")):
                    continue
                out.append({
                    "path": path,
                    "line": 1,
                    "check": "nested_git_repo",
                    "message": (f"symlink to a git repo: {os.path.relpath(path, REPOS)} -> "
                                f"{os.path.realpath(path)} - fix: rm {path} "
                                "(a symlink to a repo is never allowed here)"),
                })
    return out


def collect_targets(args) -> list[tuple[str, list[str], str, bool]]:
    """(repo root, candidate files, label, nested) tuples.

    `nested` marks a repo that lives inside another one: its findings print as
    warnings and never change the exit code.
    """
    if args.files:
        by_root: dict[str, list[str]] = {}
        for path in args.files:
            absolute = os.path.abspath(path)
            # Trash is not project content: a session that removes a file should
            # not be told about the corpse it left there.
            if absolute.startswith(TRASH + os.sep):
                continue
            root = repo_root(os.path.dirname(absolute) or ".") or os.getcwd()
            by_root.setdefault(root, []).append(absolute)
        return [(root, files, "", False) for root, files in sorted(by_root.items())]
    if args.repos:
        out = []
        for name in sorted(os.listdir(REPOS)):
            top = os.path.join(REPOS, name)
            if not os.path.isdir(top):
                continue
            if os.path.isdir(os.path.join(top, ".git")):
                files = changed_files(top) if args.changed else repo_files(top)
                out.append((top, files, name, False))
            # Repos under this directory: nested inside the repo above, or one
            # of the few top-level folders that only hold checkouts.
            for root in nested_repos(top):
                files = changed_files(root) if args.changed else repo_files(root)
                out.append((root, files, os.path.relpath(root, REPOS), True))
        return out
    root = repo_root(os.getcwd())
    if not root:
        sys.exit(f"lint: {os.getcwd()} is not inside a git repo (use FILE... or --repos)")
    return [(root, changed_files(root) if args.changed else repo_files(root), "", False)]


def main() -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("files", nargs="*", help="files to check instead of the whole repo")
    parser.add_argument("--changed", action="store_true", help="only files changed against HEAD")
    parser.add_argument("--repos", action="store_true", help="check every repo under ~/repos")
    parser.add_argument("--list", action="store_true", help="list discovered checks")
    parser.add_argument("--check", help="run one check by id")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--timing", action="store_true", help="print per-check duration")
    args = parser.parse_args()

    machine_checks = load_checks()
    if args.check:
        machine_checks = [c for c in machine_checks if c["id"] == args.check]
    if args.list:
        listing = load_checks(CHECK_DIRS + repo_check_dirs(repo_root(os.getcwd()) or os.getcwd()))
        for check in listing:
            patterns = " ".join(check["applies"]) or "*"
            print(f"{check['id']:28s} {check['quadrant']:26s} {patterns}")
        return 0

    findings: list[dict] = link_findings() if args.repos else []
    warnings: list[dict] = []
    failures: list[dict] = []
    timings: list[str] = []
    scanned = 0
    nested_seen: set[str] = set()
    checks_seen: set[str] = set()
    for root, files, label, nested in collect_targets(args):
        if nested:
            nested_seen.add(root)
        scanned += len(files)
        if not files:
            continue
        checks = machine_checks + [
            c for c in load_checks(repo_check_dirs(root)) if c["id"] not in {m["id"] for m in machine_checks}
        ]
        checks_seen.update(c["id"] for c in checks)
        for check in checks:
            wanted = [f for f in files if applies(check, os.path.relpath(f, root))]
            if not wanted:
                continue
            found, error, elapsed = run_check(check, root, label, wanted)
            if error:
                failures.append({"check": check["id"], "root": root, "error": error})
            # A vendored or cloned repo is not ours to fix: warn, never act.
            (warnings if nested else findings).extend(found)
            if args.timing:
                timings.append(f"{check['id']:28s} {elapsed:6.2f}s {len(found):4d} findings")

    if args.json:
        print(json.dumps({"findings": findings, "warnings": warnings, "failures": failures}, indent=2))
    else:
        for t in timings:
            print(t)
        for finding in sorted(findings, key=lambda f: (f["path"], f["line"], f["check"])):
            location = f"{finding['path']}:{finding['line']}" if finding["path"] else "-"
            print(f"{location}: {finding['check']}: {finding['message']}")
        for warning in sorted(warnings, key=lambda f: (f["path"], f["line"], f["check"])):
            location = f"{warning['path']}:{warning['line']}" if warning["path"] else "-"
            print(f"warning: {location}: {warning['check']}: {warning['message']}")
        for failure in failures:
            print(f"lint: check {failure['check']} failed in {failure['root']}: {failure['error']}",
                  file=sys.stderr)
        summary = f"{len(checks_seen)} checks, {scanned} files, {len(findings)} findings"
        if warnings:
            summary += (f", {len(warnings)} warnings in {len(nested_seen)} nested repos "
                        "(warned only, never acted on)")
        if failures:
            summary += f", {len(failures)} check failures"
        print(summary)

    if failures:
        return 2
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
