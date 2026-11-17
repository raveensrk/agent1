#!/usr/bin/env python3
"""Ishikari's own tool: sets up a run and writes the boards.

The workflow scripts cannot touch files, and an ant rewriting a markdown
table by hand gets it wrong. Every board write goes through this tool, so
tables stay aligned and no row is lost.

  ishikari.py setup <repo>
      Make the state folder for <repo> and print the run's env as JSON:
      {repo, state, run, main, tool, workflows}, plus testCommand and
      checkCommand once they are saved. workflows holds the paths of the
      plan, build and finish scripts, copied into <repo>/.git/ishikari/,
      inside the working directory, where the Workflow tool may load them.
      Everything else Ishikari keeps (boards, plans, worktrees, config)
      lives in the state folder, outside the repo, so none of it is ever
      committed.

  ishikari.py config <state> <key> <value>
      Save testCommand or checkCommand for this repo; setup prints them
      in env from then on. An empty value forgets the key.

  ishikari.py req add <file>                    entry text on stdin
      Append a requirement entry to an org file, after one blank line.

  ishikari.py req done <file> <id>...
      Mark the headings with these :ID:s DONE: :LAST_EDITED: and
      :IMPLEMENTED: become today, and :APPROVED: is added if missing.

  ishikari.py boards write <state> <board>      rows as JSON on stdin
      Add rows, or replace the row with the same first cell. A "Time"
      cell left as "-" or "" gets the current time.

  ishikari.py boards add <state> <board> <prefix>   rows as JSON on stdin
      Add rows without an id: each gets the id <prefix>-<n>.

  ishikari.py boards remove <state> <board>     ids as JSON on stdin
      Remove the rows with these first cells.

Boards: bulletin, bounty, critiques.
"""

import contextlib
import datetime
import fcntl
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
CONFIG_KEYS = ("testCommand", "checkCommand")


def die(msg):
    print(f"ishikari: {msg}", file=sys.stderr)
    sys.exit(1)


def read_text(path):
    """Read a file as text with "\n" lines, and say which line ending it used."""
    with open(path, newline="") as f:
        raw = f.read()
    return raw.replace("\r\n", "\n"), ("\r\n" if "\r\n" in raw else "\n")


def write_atomic(path, text, eol="\n"):
    """Write via a temp file and rename, so a crash never leaves half a file.
    The file keeps its line ending, so a CRLF file stays CRLF."""
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", newline="") as f:
        f.write(text.replace("\n", eol))
    os.replace(tmp, path)


@contextlib.contextmanager
def locked(path):
    """Hold an exclusive lock on path: two runs never lose each other's rows.
    Lock files live under ~/.ishikari/locks, never beside a file in the repo."""
    folder = os.path.join(os.path.expanduser("~"), ".ishikari", "locks")
    os.makedirs(folder, exist_ok=True)
    name = hashlib.sha1(os.path.realpath(path).encode()).hexdigest()[:16]
    with open(os.path.join(folder, f"{name}.lock"), "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def read_json_stdin(what):
    try:
        return json.load(sys.stdin)
    except ValueError as e:
        die(f"{what}: stdin is not valid JSON ({e})")


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
        "workflows": copy_workflows(top),
    }
    env.update(read_config(state))
    print(json.dumps(env, indent=2))


def copy_workflows(top):
    """Copy the scripts under .git: inside the working directory, never committed."""
    common = git(top, "rev-parse", "--path-format=absolute", "--git-common-dir") or die(f"no git dir in {top}")
    dest = os.path.join(common, "ishikari", "workflows")
    os.makedirs(dest, exist_ok=True)
    out = {}
    for k in ("plan", "build", "finish"):
        name = f"ishikari-{k}.js"
        shutil.copy(os.path.join(HERE, name), os.path.join(dest, name))
        out[k] = os.path.join(dest, name)
    return out


def config_path(state):
    return os.path.join(state, "config.json")


def read_config(state):
    try:
        data = json.load(open(config_path(state)))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if k in CONFIG_KEYS and v}


def config(state, key, value):
    if key not in CONFIG_KEYS:
        die(f"unknown key {key}; use one of {', '.join(CONFIG_KEYS)}")
    if not os.path.isdir(state):
        die(f"missing {state}; run setup first")
    data = read_config(state)
    if value:
        data[key] = value
    else:
        data.pop(key, None)
    write_atomic(config_path(state), json.dumps(data, indent=2))
    print(json.dumps(data))


def req_add(path):
    entry = sys.stdin.read().strip("\n")
    if not entry:
        die("req add needs the entry on stdin")
    with locked(path):
        text, eol = read_text(path) if os.path.exists(path) else ("", "\n")
        entry = entry.replace("\r\n", "\n")
        write_atomic(path, (text.rstrip("\n") + "\n\n" if text.strip() else "") + entry + "\n", eol)
    print(f"{path}: entry added")


def req_done(path, ids):
    if not os.path.exists(path):
        die(f"missing {path}")
    with locked(path):
        req_done_locked(path, ids)


def req_done_locked(path, ids):
    text, eol = read_text(path)
    lines = text.split("\n")
    today = datetime.date.today().isoformat()
    heads = [k for k, l in enumerate(lines) if re.match(r"^\*+ ", l)]
    found = []
    # Walk from the end, so editing one block never moves an earlier one.
    for a, b in reversed(list(zip(heads, heads[1:] + [len(lines)]))):
        block = lines[a:b]
        m = next((re.match(r"^:ID:\s+(\S+)", l) for l in block if l.startswith(":ID:")), None)
        if not m or m.group(1) not in ids:
            continue
        found.append(m.group(1))
        block[0] = re.sub(r"^(\*+) (OPEN|TODO) ", r"\1 DONE ", block[0])
        has_approved = any(l.startswith(":APPROVED:") for l in block)
        has_edited = any(l.startswith(":LAST_EDITED:") for l in block)
        stamp = [f":LAST_EDITED: {today}"] + ([] if has_approved else [f":APPROVED:    {today}"]) + [f":IMPLEMENTED: {today}"]
        out, placed = [], False
        for l in block:
            if l.startswith(":IMPLEMENTED:"):
                continue
            if not placed and (l.startswith(":LAST_EDITED:") or (l == ":END:" and not has_edited)):
                out += stamp if l.startswith(":LAST_EDITED:") else stamp + [l]
                placed = True
                continue
            out.append(l)
        lines[a:b] = out
    missing = [i for i in ids if i not in found]
    if missing:
        die(f"no heading with :ID: {', '.join(missing)} in {path}")
    write_atomic(path, "\n".join(lines), eol)
    print(f"{path}: done {', '.join(reversed(found))}")


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
    write_atomic(path, "\n".join(before + table + after).rstrip("\n") + "\n")


def boards(op, state, board, extra):
    if board not in BOARDS:
        die(f"unknown board {board}; use one of {', '.join(BOARDS)}")
    path = os.path.join(state, "boards", f"{board}.md")
    if not os.path.exists(path):
        die(f"missing {path}; run setup first")
    data = read_json_stdin(f"boards {op}")
    if not isinstance(data, list):
        die(f"boards {op}: stdin must be a JSON list")
    if op == "remove":
        if not all(isinstance(k, (str, int)) for k in data):
            die("boards remove: stdin must be a JSON list of ids")
    elif not all(isinstance(r, list) and r for r in data):
        die(f"boards {op}: each row must be a non-empty JSON list of cells")
    with locked(path):
        boards_locked(op, path, board, extra, data)


def boards_locked(op, path, board, extra, data):
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
        too_long = [r for r in data if len(r) > len(head)]
        if too_long:
            die(f"boards {op}: {board} has {len(head)} columns ({', '.join(head)}); a row has {len(too_long[0])} cells")
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
    if len(argv) == 4 and argv[0] == "config":
        return config(argv[1], argv[2], argv[3])
    if len(argv) == 3 and argv[:2] == ["req", "add"]:
        return req_add(argv[2])
    if len(argv) >= 4 and argv[:2] == ["req", "done"]:
        return req_done(argv[2], argv[3:])
    die(__doc__)


if __name__ == "__main__":
    run(sys.argv[1:])
