#!/usr/bin/env python3
"""The ant skills' fixed steps, done by code instead of by an agent.

Shared by investigator-ant, janitor-ant, judge-ant, detective-ant and
retrospective-ant. Every command prints JSON (base prints one line) and calls
no model.

  ant.py base    [--repo R] [--base B]      the branch to compare against
  ant.py scope   [--repo R] [--base B]      changed files and line ranges
  ant.py tests   [--repo R] [--base B] [--timeout S] -- CMD...
                                            run CMD on the base and on HEAD
  ant.py session [--session ID] [--projects DIR]
                                            tool calls, errors and repeats of
                                            a Claude Code session

  ant.py help                               this long help
  ant.py -h, --help                         short help

Exit codes: 0 ok, 2 usage or git error.
"""
import argparse
import collections
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

TAIL = 40  # output lines kept per test run


def git(repo, *args, check=True):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    if check and r.returncode:
        sys.exit(f"ant.py: git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.strip() if r.returncode == 0 else None


def has_ref(repo, ref):
    return git(repo, "rev-parse", "--verify", "--quiet", ref + "^{commit}", check=False) is not None


def find_base(repo, given=None):
    """The named branch if it exists; else origin's HEAD, main, then master."""
    if given:
        if has_ref(repo, given):
            return given
        sys.exit(f"ant.py: base {given!r} not found")
    head = git(repo, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD", check=False)
    if head:
        local = head.split("/", 1)[1]
        return local if has_ref(repo, local) else head
    for name in ("main", "master"):
        if has_ref(repo, name):
            return name
    sys.exit("ant.py: no main or master branch; pass --base")


HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def scope(repo, base):
    """Files and new-side line ranges changed from the merge base to HEAD."""
    mb = git(repo, "merge-base", base, "HEAD")
    out = git(repo, "diff", "-U0", "--no-color", "--no-ext-diff", mb, "HEAD")
    files, cur = [], None
    for line in out.splitlines():
        if line.startswith("+++ "):
            path = line[4:]
            cur = None if path == "/dev/null" else {"path": path[2:] if path.startswith("b/") else path, "ranges": []}
            if cur:
                files.append(cur)
        elif cur is not None and (m := HUNK.match(line)):
            start, count = int(m.group(1)), int(m.group(2) or 1)
            if count:
                cur["ranges"].append([start, start + count - 1])
    deleted = [p for p in (git(repo, "diff", "--name-only", "--diff-filter=D", mb, "HEAD") or "").splitlines() if p]
    lines = sum(b - a + 1 for f in files for a, b in f["ranges"])
    return {"base": base, "mergeBase": mb, "head": git(repo, "rev-parse", "HEAD"),
            "files": files, "deleted": deleted, "linesChanged": lines}


def run_cmd(cmd, cwd, timeout):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        code, text = r.returncode, (r.stdout + r.stderr)
    except subprocess.TimeoutExpired as e:
        code, text = None, f"timed out after {timeout} s\n" + str(e.output or "")
    except OSError as e:
        code, text = None, str(e)
    return {"exit": code, "tail": "\n".join(text.splitlines()[-TAIL:])}


def tests(repo, base, cmd, timeout):
    """Run cmd at the merge base (a throwaway worktree) and in the repo as it is."""
    mb = git(repo, "merge-base", base, "HEAD")
    tmp = tempfile.mkdtemp(prefix="ant-base-")
    tree = os.path.join(tmp, "tree")
    try:
        git(repo, "worktree", "add", "--detach", "--quiet", tree, mb)
        before = run_cmd(cmd, tree, timeout)
    finally:
        git(repo, "worktree", "remove", "--force", tree, check=False)
        shutil.rmtree(tmp, ignore_errors=True)
    after = run_cmd(cmd, repo, timeout)
    ok = lambda r: r["exit"] == 0
    verdict = ("pass" if ok(after) else "new-failure") if ok(before) else ("fixed" if ok(after) else "already-failing")
    return {"base": base, "mergeBase": mb, "before": before, "after": after, "verdict": verdict}


def find_transcript(session, projects):
    hits = glob.glob(os.path.join(projects, "*", session + ".jsonl"))
    if not hits:
        sys.exit(f"ant.py: no transcript for session {session} under {projects}")
    return max(hits, key=os.path.getmtime)


def session_stats(path):
    """Tool calls, failed calls and repeated identical calls, from a transcript."""
    calls, results = {}, {}
    for line in open(path, encoding="utf-8", errors="replace"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") not in ("assistant", "user"):
            continue
        content = (d.get("message") or {}).get("content")
        for x in content if isinstance(content, list) else []:
            if not isinstance(x, dict):
                continue
            if x.get("type") == "tool_use" and x.get("id"):
                calls[x["id"]] = (x.get("name", "?"), json.dumps(x.get("input"), sort_keys=True))
            elif x.get("type") == "tool_result" and x.get("tool_use_id"):
                body = x.get("content")
                text = body if isinstance(body, str) else " ".join(
                    c.get("text", "") for c in body or [] if isinstance(c, dict))
                results[x["tool_use_id"]] = (bool(x.get("is_error")), text)
    by_tool = collections.Counter(n for n, _ in calls.values())
    errors = []
    for cid, (name, inp) in calls.items():
        err, text = results.get(cid, (False, ""))
        if err:
            errors.append({"tool": name, "input": inp[:200], "error": text.strip()[:300],
                           "rejected": "doesn't want to proceed" in text})
    repeats = [{"tool": n, "input": i[:200], "times": k}
               for (n, i), k in collections.Counter(calls.values()).items() if k > 1]
    return {"transcript": path, "toolCalls": len(calls), "byTool": dict(by_tool.most_common()),
            "errors": errors, "repeats": sorted(repeats, key=lambda r: -r["times"])}


def main(argv):
    if argv[:1] == ["help"]:
        print(__doc__)
        return 0
    p = argparse.ArgumentParser(prog="ant.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("base", "scope", "tests"):
        s = sub.add_parser(name)
        s.add_argument("--repo", default=".")
        s.add_argument("--base")
        if name == "tests":
            s.add_argument("--timeout", type=int, default=600)
            s.add_argument("command", nargs=argparse.REMAINDER)
    s = sub.add_parser("session")
    s.add_argument("--session", default=os.environ.get("CLAUDE_CODE_SESSION_ID"))
    s.add_argument("--projects", default=os.path.expanduser("~/.claude/projects"))
    a = p.parse_args(argv)
    if a.cmd == "session":
        if not a.session:
            sys.exit("ant.py: no session id; pass --session or set CLAUDE_CODE_SESSION_ID")
        out = session_stats(find_transcript(a.session, a.projects))
    else:
        repo = git(a.repo, "rev-parse", "--show-toplevel")
        base = find_base(repo, a.base)
        if a.cmd == "base":
            print(base)
            return 0
        if a.cmd == "scope":
            out = scope(repo, base)
        else:
            cmd = a.command[1:] if a.command[:1] == ["--"] else a.command
            if not cmd:
                sys.exit("ant.py tests: give the test command after --")
            out = tests(repo, base, cmd, a.timeout)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except SystemExit as e:
        if isinstance(e.code, str):
            print(e.code, file=sys.stderr)
            sys.exit(2)
        raise
