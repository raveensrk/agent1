#!/usr/bin/env python3
"""Ishikari's own tool: sets up a run and writes the boards.

The workflow scripts cannot touch files, and an ant rewriting a markdown
table by hand gets it wrong. Every board write goes through this tool, so
tables stay aligned and no row is lost.

  ishikari.py setup <repo>
      Make the state folder for <repo> and print the run's env as JSON:
      {repo, state, run, main, tool, workflows}. workflows holds the
      absolute paths of the plan, build and finish scripts. Everything Ishikari keeps (boards,
      plans, worktrees) lives in the state folder, outside the repo, so
      none of it is ever committed.

  ishikari.py boards write <state> <board>      rows as JSON on stdin
      Add rows, or replace the row with the same first cell. A "Time"
      cell left as "-" or "" gets the current time.

  ishikari.py boards add <state> <board> <prefix>   rows as JSON on stdin
      Add rows without an id: each gets the id <prefix>-<n>.

  ishikari.py boards remove <state> <board>     ids as JSON on stdin
      Remove the rows with these first cells.

Boards: bulletin, bounty, critiques.
"""

import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(os.path.dirname(HERE), "assets", "boards")
BOARDS = ("bulletin", "bounty", "critiques")


def die(msg):
    print(f"ishikari: {msg}", file=sys.stderr)
    sys.exit(1)


def git(repo, *args):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def main_branch(repo):
    head = git(repo, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    if head and "/" in head:
        return head.split("/", 1)[1]
    for name in ("main", "master", "trunk"):
        if git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}"):
            return name
    return git(repo, "branch", "--show-current") or die(f"no main branch found in {repo}")


def setup(repo):
    top = git(os.path.abspath(repo), "rev-parse", "--show-toplevel")
    if not top:
        die(f"not a git repo: {repo}")
    top = os.path.realpath(top)
    tag = hashlib.sha1(top.encode()).hexdigest()[:8]
    state = os.path.join(os.path.expanduser("~"), ".ishikari", f"{os.path.basename(top)}-{tag}")
    for sub in ("boards", "plans", "worktrees"):
        os.makedirs(os.path.join(state, sub), exist_ok=True)
    for name in BOARDS:
        dst = os.path.join(state, "boards", f"{name}.md")
        if not os.path.exists(dst):
            shutil.copy(os.path.join(TEMPLATES, f"{name}.md"), dst)
    env = {
        "repo": top,
        "state": state,
        "run": datetime.datetime.now().strftime("%Y%m%d-%H%M%S"),
        "main": main_branch(top),
        "tool": os.path.abspath(__file__),
        "workflows": {k: os.path.join(HERE, f"ishikari-{k}.js") for k in ("plan", "build", "finish")},
    }
    print(json.dumps(env, indent=2))


def cell(value):
    text = " ".join(str(value).split())
    return text.replace("|", "\\|") or "-"


def split_row(line):
    parts = re.split(r"(?<!\\)\|", line.strip())[1:-1]
    return [p.strip() for p in parts]


def load(path):
    lines = open(path).read().splitlines()
    for i in range(len(lines) - 1):
        if lines[i].startswith("|") and re.match(r"^\|(\s*:?-+:?\s*\|)+$", lines[i + 1].strip()):
            head = split_row(lines[i])
            end = i + 2
            while end < len(lines) and lines[end].startswith("|"):
                end += 1
            rows = [split_row(line) for line in lines[i + 2:end]]
            return lines[:i], head, rows, lines[end:]
    die(f"no table in {path}")


def save(path, before, head, rows, after):
    rows = [(r + ["-"] * len(head))[: len(head)] for r in rows]
    widths = [max([len(head[k])] + [len(r[k]) for r in rows] + [3]) for k in range(len(head))]
    fmt = lambda r: "| " + " | ".join(c.ljust(widths[k]) for k, c in enumerate(r)) + " |"
    table = [fmt(head), "| " + " | ".join("-" * w for w in widths) + " |"] + [fmt(r) for r in rows]
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write("\n".join(before + table + after).rstrip("\n") + "\n")
    os.replace(tmp, path)


def boards(op, state, board, extra):
    if board not in BOARDS:
        die(f"unknown board {board}; use one of {', '.join(BOARDS)}")
    path = os.path.join(state, "boards", f"{board}.md")
    if not os.path.exists(path):
        die(f"missing {path}; run setup first")
    data = json.load(sys.stdin)
    before, head, rows, after = load(path)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    time_col = head.index("Time") if "Time" in head else None
    if op == "remove":
        gone = {cell(k) for k in data}
        rows = [r for r in rows if r and r[0] not in gone]
    else:
        if op == "add":
            prefix = extra or die("boards add needs an id prefix")
            taken = {r[0] for r in rows if r}
            n, fresh = 0, []
            for r in data:
                n += 1
                while f"{prefix}-{n}" in taken:
                    n += 1
                fresh.append([f"{prefix}-{n}", *r])
            data = fresh
        index = {r[0]: k for k, r in enumerate(rows) if r}
        for raw in data:
            new = [cell(v) for v in raw]
            new = (new + ["-"] * len(head))[: len(head)]
            if time_col is not None and new[time_col] in ("-", ""):
                new[time_col] = now
            if new[0] in index:
                rows[index[new[0]]] = new
            else:
                index[new[0]] = len(rows)
                rows.append(new)
    save(path, before, head, rows, after)
    print(f"{board}: {len(rows)} rows")


def run(argv):
    if len(argv) == 2 and argv[0] == "setup":
        return setup(argv[1])
    if len(argv) in (4, 5) and argv[0] == "boards" and argv[1] in ("write", "add", "remove"):
        return boards(argv[1], argv[2], argv[3], argv[4] if len(argv) == 5 else None)
    die(__doc__)


if __name__ == "__main__":
    run(sys.argv[1:])
