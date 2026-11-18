#!/usr/bin/env python3
"""Ishikari's own tool: sets up a run and keeps the logbook.

The workflow scripts cannot touch files, and an ant editing a shared file by
hand gets it wrong. Every logbook write goes through this tool, under a lock,
so no entry is lost and the file stays a valid recfile.

  ishikari.py setup <repo> [--main <branch>]
      Make the state folder for <repo> and print the run's env as JSON:
      {repo, state, run, main, tool, workflows}, plus testCommand and
      checkCommand once they are saved. workflows holds the paths of the
      plan, build and finish scripts, copied into <repo>/.git/ishikari/,
      inside the working directory, where the Workflow tool may load them.
      Everything else Ishikari keeps (logbook, plans, worktrees, config)
      lives in the state folder, outside the repo, so none of it is ever
      committed. The main branch is origin/HEAD, else main, master or
      trunk; pass --main when none exists. The repo must be checked out
      on it with no uncommitted changes.

  ishikari.py config <state> <key> <value>
      Save testCommand or checkCommand for this repo; setup prints them
      in env from then on. An empty value forgets the key.

  ishikari.py req add <file>                    entry text on stdin
      Append a requirement entry to an org file, after one blank line.

  ishikari.py req done <file> <id>...
      Mark the headings with these :ID:s DONE: :LAST_EDITED: and
      :IMPLEMENTED: become today, and :APPROVED: is added if missing.

  ishikari.py log append <state>                entries as JSON on stdin
      Append entries to <state>/logbook.rec, a GNU recfile (read it with
      recsel, grep or any editor). Each entry is an object with run, who
      and event, and optionally task, detail, tries and score. Time is
      added. The logbook is append only: nothing is ever changed or removed.

  ishikari.py log note <state> <text>...
      Append your own note (Who: you). Ants never act on notes.

  ishikari.py log status <state> [<run>]
      Print each task's latest event, oldest first, for one run or all.
"""

import contextlib
import datetime
import fcntl
import hashlib
import json
import os
import re
import shutil
import secrets
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOGBOOK = "logbook.rec"
LOG_FIELDS = ("run", "task", "who", "event", "detail", "tries", "score")
LOG_HEAD = """# Ishikari logbook: one entry per event, append only.
# Write with `ishikari.py log append` or `ishikari.py log note`; read with recsel.
%rec: Entry
%mandatory: Time Run Who Event
%type: Time date
"""
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
    name = head.split("/", 1)[1] if head and "/" in head else None
    if name and git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}"):
        return name
    for name in ("main", "master", "trunk"):
        if git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}"):
            return name
    die(f"no main branch in {repo}: no origin/HEAD, main, master or trunk; pass --main <branch>")


def check_main(top, main):
    if not git(top, "rev-parse", "--verify", "--quiet", f"refs/heads/{main}"):
        die(f"main branch {main} does not exist in {top}; pass --main <branch>")
    current = git(top, "branch", "--show-current")
    if current != main:
        die(f"{top} is on {current or 'a detached HEAD'}, not the main branch {main}; check out {main} first")
    if git(top, "status", "--porcelain", "--untracked-files=no"):
        die(f"{top} has uncommitted changes; commit or stash them first")


def run_id():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)


def setup(repo, main=None):
    top = git(os.path.abspath(repo), "rev-parse", "--show-toplevel")
    if not top:
        die(f"not a git repo: {repo}")
    top = os.path.realpath(top)
    common = git(top, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if common and os.path.basename(common) == ".git":
        top = os.path.realpath(os.path.dirname(common))  # a linked worktree: use the main checkout
    main = main or main_branch(top)
    check_main(top, main)
    tag = hashlib.sha1(top.encode()).hexdigest()[:8]
    state = os.path.join(os.path.expanduser("~"), ".ishikari", f"{os.path.basename(top)}-{tag}")
    for sub in ("plans", "worktrees"):
        os.makedirs(os.path.join(state, sub), exist_ok=True)
    book = os.path.join(state, LOGBOOK)
    with locked(book):
        if not os.path.exists(book):
            write_atomic(book, LOG_HEAD)
    env = {
        "repo": top,
        "state": state,
        "run": run_id(),
        "main": main,
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


def rec_value(value):
    """One recfile value: extra lines continue with "+ ", blanks become "-"."""
    lines = str(value).replace("\r\n", "\n").split("\n")
    lines = [" ".join(l.split()) for l in lines]
    while lines and not lines[-1]:
        lines.pop()
    return "\n+ ".join(lines) or "-"


def log_path(state):
    path = os.path.join(state, LOGBOOK)
    if not os.path.exists(path):
        die(f"missing {path}; run setup first")
    return path


def log_append(state, entries):
    path = log_path(state)
    if not isinstance(entries, list) or not entries:
        die("log append: stdin must be a non-empty JSON list of entries")
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    records = []
    for e in entries:
        if not isinstance(e, dict):
            die("log append: each entry must be a JSON object")
        unknown = sorted(set(e) - set(LOG_FIELDS))
        if unknown:
            die(f"log append: unknown field {unknown[0]}; use {', '.join(LOG_FIELDS)}")
        missing = [k for k in ("run", "who", "event") if not str(e.get(k, "")).strip()]
        if missing:
            die(f"log append: an entry has no {missing[0]}")
        rec = [f"Time: {now}"] + [f"{k.capitalize()}: {rec_value(e[k])}" for k in LOG_FIELDS if e.get(k) not in (None, "")]
        records.append("\n".join(rec))
    with locked(path):
        with open(path, "a") as f:
            f.write("".join(f"\n{r}\n" for r in records))
    print(f"logbook: {len(records)} entries added")


def log_read(state):
    """Every entry as a dict, oldest first."""
    out, cur, last = [], {}, None
    for line in read_text(log_path(state))[0].split("\n") + [""]:
        if not line.strip():
            if cur:
                out.append(cur)
            cur, last = {}, None
        elif line.startswith(("#", "%")):
            continue
        elif line.startswith("+") and last:
            cur[last] += "\n" + line[2:]
        elif ":" in line:
            last, value = line.split(":", 1)
            cur[last] = value.strip()
    return out


def log_status(state, run=None):
    latest = {}
    for e in log_read(state):
        if e.get("Task") and (run is None or e.get("Run") == run):
            latest[(e.get("Run"), e["Task"])] = e
    rows = [(f"{k[0]}/{k[1]}", e.get("Event", ""), e.get("Who", ""), e.get("Time", "")) for k, e in latest.items()]
    if not rows:
        print("no tasks in the logbook" + (f" for run {run}" if run else ""))
        return
    widths = [max(len(r[i]) for r in rows) for i in range(4)]
    for r in rows:
        print("  ".join(c.ljust(widths[i]) for i, c in enumerate(r)).rstrip())


def run(argv):
    if argv[:1] == ["setup"]:
        rest, main = argv[1:], None
        if "--main" in rest:
            k = rest.index("--main")
            main = rest[k + 1] if k + 1 < len(rest) else None
            rest = rest[:k] + rest[k + 2:]
            if not main:
                die("setup: --main needs a branch name")
        if len(rest) == 1:
            return setup(rest[0], main)
    if len(argv) == 3 and argv[:2] == ["log", "append"]:
        return log_append(argv[2], read_json_stdin("log append"))
    if len(argv) >= 4 and argv[:2] == ["log", "note"]:
        return log_append(argv[2], [{"run": "-", "who": "you", "event": "note", "detail": " ".join(argv[3:])}])
    if len(argv) in (3, 4) and argv[:2] == ["log", "status"]:
        return log_status(argv[2], argv[3] if len(argv) == 4 else None)
    if len(argv) == 4 and argv[0] == "config":
        return config(argv[1], argv[2], argv[3])
    if len(argv) == 3 and argv[:2] == ["req", "add"]:
        return req_add(argv[2])
    if len(argv) >= 4 and argv[:2] == ["req", "done"]:
        return req_done(argv[2], argv[3:])
    die(__doc__)


if __name__ == "__main__":
    run(sys.argv[1:])
