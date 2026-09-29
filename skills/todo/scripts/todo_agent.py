#!/usr/bin/env python3
"""The todo skill's helper: wrap the org CLI for board work.

org is the writer; this script composes its calls, reads the skill config,
resolves the board, and keeps the fragile bits - the state word, :ID:,
:CREATED:, revision hashes, claim ids - out of ad hoc shell.

Config: ~/dot_local/config/todo_skill.toml
  default_dirs   directories read when none is named
  ignore         path patterns dropped from reads
  review_actor   the human who approves board work

Overrides, used by tests: TODO_SKILL_CONFIG, ORG_BIN.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
import uuid
from datetime import date
from pathlib import Path

DEFAULT_CONFIG = Path.home() / "dot_local" / "config" / "todo_skill.toml"
BOARD = "todo.org"
SCAFFOLD = (
    "#+TITLE: TODO\n"
    "#+TODO: TODO IN_PROGRESS OPTIONAL LATER | DONE OBSOLETE\n"
    "#+STARTUP: logdone\n\n* Tasks\n"
)
INBOX_SCAFFOLD = "#+TITLE: INBOX\n"


class Fail(Exception):
    """A user-facing failure: print the message, exit 1."""


# --------------------------------------------------------------------------
# org and config plumbing


def org_bin() -> str:
    path = os.environ.get("ORG_BIN") or shutil.which("org") or str(Path.home() / ".local/bin/org")
    if not Path(path).exists():
        raise Fail("org CLI not found; install dcprevere/org-cli or set ORG_BIN")
    version = subprocess.run(
        [path, "--version"], capture_output=True, text=True
    ).stdout.strip()
    if not version.startswith("org 2."):
        raise Fail(f"org 2.x required, found: {version or 'unknown'}")
    return path


def load_config() -> dict:
    path = Path(os.environ.get("TODO_SKILL_CONFIG", DEFAULT_CONFIG)).expanduser()
    data = tomllib.loads(path.read_text()) if path.is_file() else {}
    return {
        "default_dirs": [Path(d).expanduser() for d in data.get("default_dirs", [])],
        "ignore": list(data.get("ignore", [])),
        "review_actor": data.get("review_actor"),
    }


def org(directory: Path, *args: str):
    """One org call. Every call takes -d and -f json."""
    cmd = [org_bin(), "-d", str(directory), "-f", "json", *args]
    done = subprocess.run(cmd, capture_output=True, text=True)
    try:
        payload = json.loads(done.stdout)
    except json.JSONDecodeError:
        raise Fail(f"org returned no JSON: {' '.join(cmd)}\n{done.stderr.strip()}")
    if not payload.get("ok"):
        raise Fail(payload.get("error", {}).get("message", "org call failed"))
    return payload.get("data")


# --------------------------------------------------------------------------
# paths and patterns


def git_root(start: Path) -> Path | None:
    done = subprocess.run(
        ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    return Path(done.stdout.strip()) if done.returncode == 0 else None


def board_for(start: Path) -> Path:
    """The board to write: the repo root's todo.org, else the nearest above,
    else todo.org at the start directory."""
    root = git_root(start)
    if root is not None:
        return root / BOARD
    for candidate in (start, *start.parents):
        if (candidate / BOARD).is_file():
            return candidate / BOARD
    return start / BOARD


def inbox_for(start: Path) -> Path:
    root = git_root(start)
    return (root or start) / "inbox.org"


def is_ignored(path: Path, patterns: list[str]) -> bool:
    """Main_Quest config semantics: a bare name matches a component at any
    depth, a multi-segment entry matches that run of components, a glob is a
    glob, and an absolute or ~ entry matches that exact path and below."""
    text = str(path)
    for pattern in patterns:
        if pattern.startswith(("~", "/")):
            base = str(Path(pattern).expanduser())
            if text == base or text.startswith(base + os.sep):
                return True
        elif any(ch in pattern for ch in "*?["):
            if fnmatch.fnmatch(text, pattern) or fnmatch.fnmatch(path.name, pattern):
                return True
        elif "/" in pattern:
            if text == pattern or text.endswith("/" + pattern) or f"/{pattern}/" in text:
                return True
        elif pattern in path.parts:
            return True
    return False


def first_state(board: Path) -> str:
    """The file's own open state: the first keyword on #+TODO:, before the |."""
    for line in board.read_text().splitlines():
        if line.startswith("#+TODO:"):
            open_states = line[len("#+TODO:") :].split("|")[0].split()
            if open_states:
                return open_states[0]
    raise Fail(f"no #+TODO: line in {board}")


HEADING = re.compile(r"^(\*+)\s+(.*)$")
PRIORITY = re.compile(r"\[#([A-C])\]\s+(.*)$")
TAG_BLOCK = re.compile(r"\s+(:[^:\s]+(?::[^:\s]+)*:)\s*$")


def declared_states(board: Path) -> list[str]:
    for line in board.read_text(encoding="utf-8").splitlines():
        if line.startswith("#+TODO:"):
            open_states, _, done_states = line[len("#+TODO:") :].partition("|")
            return open_states.split() + done_states.split()
    return ["TODO", "DONE"]


def split_heading(line: str, states: list[str]) -> tuple[str, str, str, str, str]:
    """(stars, state, priority, title, tags) from one heading, or Fail when the
    line is not a task."""
    match = HEADING.match(line.rstrip("\n"))
    if not match:
        raise Fail(f"not a heading: {line!r}")
    stars, rest = match.groups()
    tags = ""
    found = TAG_BLOCK.search(rest)
    if found:
        tags, rest = found.group(1), rest[: found.start()].rstrip()
    state, _, rest = rest.partition(" ")
    if state not in states:
        raise Fail(f"not a task heading: {line!r}")
    priority = ""
    found = PRIORITY.match(rest)
    if found:
        priority, rest = f"[#{found.group(1)}]", found.group(2)
    return stars, state, priority, rest, tags


def join_heading(stars: str, state: str, priority: str, title: str, tags: str) -> str:
    line = f"{stars} {state}"
    if priority:
        line += f" {priority}"
    if title:
        line += f" {title}"
    if tags:
        line += f" {tags}"
    return line


def ensure_board(board: Path) -> None:
    """Create the scaffold, and the Tasks container, when they are missing.
    Both are file structure, not task entries, so a hand write is allowed."""
    if not board.exists():
        board.parent.mkdir(parents=True, exist_ok=True)
        board.write_text(SCAFFOLD)
        return
    if not re.search(r"^\*+ Tasks\s*$", board.read_text(), re.M):
        with board.open("a") as handle:
            if not board.read_text().endswith("\n"):
                handle.write("\n")
            handle.write("* Tasks\n")


# --------------------------------------------------------------------------
# verbs


def board_tasks(board_dir: Path, board: Path) -> list[dict]:
    """Tasks from this one board. --files, not -d, so a home-directory board
    never makes org walk ~/.Trash and the rest of the tree."""
    return org(board_dir, "--files", str(board), "todo", "list")


def resolve_id(board_dir: Path, board: Path, ref: str) -> str:
    """id:<uuid> passes through; a title is resolved through the board."""
    if ref.startswith("id:"):
        return ref[3:]
    matches = [item for item in board_tasks(board_dir, board) if item["title"] == ref]
    if len(matches) != 1:
        raise Fail(f"{ref!r} matches {len(matches)} tasks in {board}; use id:<uuid>")
    return matches[0]["id"]


def revision(board_dir: Path, task_id: str) -> str:
    return org(board_dir, "task", "show", f"id:{task_id}")["revision"]


def actor() -> str:
    name = os.environ.get("ORG_ACTOR")
    if not name:
        raise Fail("ORG_ACTOR is unset; set it or ask which actor to use")
    return name


def cmd_create(args) -> dict:
    board = Path(args.file).expanduser().resolve() if args.file else board_for(Path.cwd())
    ensure_board(board)
    directory = board.parent
    state = args.state or first_state(board)
    task_id = org(
        directory,
        "add",
        str(board),
        args.title,
        "--todo",
        state,
        "--under",
        args.container,
    )["id"]
    org(directory, "property", "set", str(board), f"id:{task_id}", "CREATED", date.today().isoformat())
    if args.deadline:
        org(directory, "deadline", str(board), f"id:{task_id}", args.deadline)
    if args.priority:
        org(directory, "priority", str(board), f"id:{task_id}", args.priority)
    for tag in args.tag:
        org(directory, "tag", "add", str(board), f"id:{task_id}", tag)
    if args.note:
        org(directory, "append", str(board), f"id:{task_id}", args.note)
    return {"id": task_id, "file": str(board), "state": state, "title": args.title}


def board_and_id(args) -> tuple[Path, Path, str]:
    board = Path(args.file).expanduser().resolve() if getattr(args, "file", None) else board_for(Path.cwd())
    return board.parent, board, resolve_id(board.parent, board, args.ref)


def cmd_ref_verb(args, prefix: tuple[str, ...], *extra: str) -> dict:
    """Run a verb whose form is `PREFIX <file> <ref> <args>`, such as
    `todo set`, `tag add`, `deadline`, `append` or `archive`."""
    directory, board, task_id = board_and_id(args)
    return org(directory, *prefix, str(board), f"id:{task_id}", *extra)


def cmd_rename(args) -> dict:
    """Change a title. org has no rename verb, so this rewrites exactly one
    heading line - stars, state, priority and tags preserved - refuses if the
    board changed underneath, and verifies the task through org afterwards.
    The one hand write the skill makes."""
    if not args.title.strip():
        raise Fail("the title must not be empty")
    directory, board, task_id = board_and_id(args)
    states = declared_states(board)
    item = next((i for i in board_tasks(directory, board) if i["id"] == task_id), None)
    if item is None:
        raise Fail(f"task {task_id} is not on {board}")
    original = board.read_text(encoding="utf-8")
    tags = f":{':'.join(item['tags'])}:" if item["tags"] else ""
    targets = []
    for line in original.splitlines(keepends=True):
        try:
            stars, state, priority, title, line_tags = split_heading(line, states)
        except Fail:
            continue
        if (state, title, line_tags) == (item["todo"], item["title"], tags):
            targets.append((line, stars, state, priority, line_tags))
    if len(targets) != 1:
        raise Fail(f"{len(targets)} headings match {item['title']!r} on {board}; refine the ref")
    old_line, stars, state, priority, line_tags = targets[0]
    new_line = join_heading(stars, state, priority, args.title, line_tags)
    if new_line == old_line.rstrip("\n"):
        return {"id": task_id, "title": args.title, "unchanged": True}
    if board.read_text(encoding="utf-8") != original:
        raise Fail("the board changed while renaming; retry")
    tmp = board.with_name(board.name + ".tmp")
    tmp.write_text(original.replace(old_line, new_line + "\n", 1), encoding="utf-8")
    os.replace(tmp, board)
    shown = org(directory, "read", str(board), f"id:{task_id}")
    first_line = shown.splitlines()[0] if isinstance(shown, str) and shown else ""
    if args.title not in first_line:
        raise Fail(f"verification failed after rename: {first_line!r}")
    return {"id": task_id, "title": args.title, "file": str(board)}


def cmd_delete(args) -> dict:
    """Remove the task subtree. org has no delete verb, so this is a guarded
    hand write: it removes exactly the heading and its body, refuses if the
    board changed underneath, and verifies the task is gone afterwards."""
    directory, board, task_id = board_and_id(args)
    item = next((i for i in board_tasks(directory, board) if i["id"] == task_id), None)
    if item is None:
        raise Fail(f"task {task_id} is not on {board}")
    states = declared_states(board)
    original = board.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    tags = f":{':'.join(item['tags'])}:" if item["tags"] else ""
    index, level = None, 0
    for position, line in enumerate(lines):
        try:
            stars, state, _priority, title, line_tags = split_heading(line, states)
        except Fail:
            continue
        if (state, title, line_tags) == (item["todo"], item["title"], tags):
            if index is not None:
                raise Fail(f"more than one heading matches {item['title']!r}; refine the ref")
            index, level = position, len(stars)
    if index is None:
        raise Fail(f"{item['title']!r} not found on {board}")
    end = len(lines)
    for position in range(index + 1, len(lines)):
        match = HEADING.match(lines[position].rstrip("\n"))
        if match and len(match.group(1)) <= level:
            end = position
            break
    if board.read_text(encoding="utf-8") != original:
        raise Fail("the board changed while deleting; retry")
    tmp = board.with_name(board.name + ".tmp")
    tmp.write_text("".join(lines[:index] + lines[end:]), encoding="utf-8")
    os.replace(tmp, board)
    if any(i["id"] == task_id for i in board_tasks(directory, board)):
        raise Fail("verification failed: the task is still on the board")
    return {"id": task_id, "title": item["title"], "file": str(board), "removed_lines": end - index}


def cmd_capture(args) -> dict:
    inbox = Path(args.inbox).expanduser().resolve() if args.inbox else inbox_for(Path.cwd())
    if not inbox.exists():
        inbox.parent.mkdir(parents=True, exist_ok=True)
        inbox.write_text(INBOX_SCAFFOLD)
    with inbox.open("a") as handle:
        handle.write(f"* {args.text}\n")
    return {"file": str(inbox), "title": args.text}


def scan_dir(directory: Path, ignore: list[str]) -> list[dict]:
    items = []
    for item in org(directory, "todo", "list"):
        full = directory / item["file"]
        if not is_ignored(full, ignore):
            item["path"] = str(full)
            items.append(item)
    return items


def scan_files(paths: list[Path]) -> list[dict]:
    by_name = {path.name: path for path in paths}
    items = org(Path.cwd(), "--files", *[str(p) for p in paths], "todo", "list")
    for item in items:
        item["path"] = str(by_name.get(item["file"], Path(item["file"])))
    return items


def cmd_read(args) -> list[dict]:
    """Read the named dirs, or the configured dirs plus the board the cwd is
    on - so a task just created here is also read here."""
    config = load_config()
    items: list[dict] = []
    if args.dir:
        for directory in (Path(d).expanduser() for d in args.dir):
            if directory.is_dir():
                items.extend(scan_dir(directory, config["ignore"]))
    else:
        for directory in config["default_dirs"]:
            if directory.is_dir():
                items.extend(scan_dir(directory, config["ignore"]))
        cwd_board = board_for(Path.cwd()).resolve()
        covered = any(
            directory.is_dir() and cwd_board.is_relative_to(directory.resolve())
            for directory in config["default_dirs"]
        )
        if cwd_board.is_file() and not covered and not is_ignored(cwd_board, config["ignore"]):
            items.extend(scan_files([cwd_board]))
    if args.state:
        items = [i for i in items if i["todo"] == args.state]
    if args.tag:
        items = [i for i in items if args.tag in i["tags"]]
    return items


def cmd_claim(args) -> dict:
    _, board, task_id = board_and_id(args)
    claim_id = args.claim_id or str(uuid.uuid4())
    data = org(
        board.parent,
        "task",
        "claim",
        f"id:{task_id}",
        "--actor",
        actor(),
        "--claim-id",
        claim_id,
        "--lease-minutes",
        str(args.lease_minutes),
        "--expected-revision",
        revision(board.parent, task_id),
    )
    return {"id": task_id, "claim_id": claim_id, "status": data.get("status")}


def cmd_claim_step(args, verb: str, evidence: str | None) -> dict:
    _, board, task_id = board_and_id(args)
    extra = ["--actor", actor(), "--claim-id", args.claim_id]
    if evidence is not None:
        extra += ["--evidence", evidence]
    extra += ["--expected-revision", revision(board.parent, task_id)]
    data = org(board.parent, "task", verb, f"id:{task_id}", *extra)
    return {"id": task_id, "status": data.get("status")}


def cmd_approve(args) -> dict:
    _, board, task_id = board_and_id(args)
    config = load_config()
    reviewer = args.actor or config["review_actor"]
    if not reviewer:
        raise Fail("no review_actor in the skill config; ask the human which actor approves")
    if reviewer == os.environ.get("ORG_ACTOR"):
        raise Fail(f"the reviewer must differ from ORG_ACTOR ({reviewer})")
    data = org(
        board.parent,
        "task",
        "approve",
        f"id:{task_id}",
        "--actor",
        reviewer,
        "--evidence",
        args.evidence,
        "--expected-revision",
        revision(board.parent, task_id),
    )
    return {"id": task_id, "state": data.get("state"), "reviewed_by": reviewer}


# --------------------------------------------------------------------------
# cli


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="todo_agent.py", description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="machine output")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_ref(name: str, help_text: str):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("ref", help="id:<uuid> or an exact title")
        p.add_argument("--file", help="board file (default: resolve from cwd)")
        return p

    read = sub.add_parser("read", help="list tasks across the configured dirs")
    read.add_argument("--dir", action="append", default=[], help="dir to scan (repeatable)")
    read.add_argument("--state")
    read.add_argument("--tag")

    create = sub.add_parser("create", help="create a task")
    create.add_argument("title")
    create.add_argument("--file")
    create.add_argument("--state")
    create.add_argument("--container", default="Tasks")
    create.add_argument("--deadline", help="bare YYYY-MM-DD; org fills the day name")
    create.add_argument("--priority", choices=["A", "B", "C"])
    create.add_argument("--tag", action="append", default=[])
    create.add_argument("--note")

    rename = add_ref("rename", "change a task title (a guarded hand write)")
    rename.add_argument("title")

    add_ref("delete", "remove a task subtree (not recoverable outside git)")

    capture = sub.add_parser("capture", help="append a plain heading to inbox.org")
    capture.add_argument("text")
    capture.add_argument("--inbox")

    ref_verbs = {
        "set-state": ("todo_set", "set the state keyword"),
        "set-deadline": ("deadline", "set DEADLINE"),
        "add-tag": ("tag_add", "add a tag"),
        "remove-tag": ("tag_remove", "remove a tag"),
        "append": ("append", "append text to the subtree body"),
        "archive": ("archive", "move the subtree to <file>.org_archive"),
        "obsolete": ("obsolete", "mark the task OBSOLETE"),
    }
    for name, (_, help_text) in ref_verbs.items():
        p = add_ref(name, help_text)
        if name in ("set-state", "set-deadline", "add-tag", "remove-tag", "append"):
            p.add_argument("value", help="state, date, tag or text")

    claim = add_ref("claim", "claim a task; prints the claim id to reuse")
    claim.add_argument("--claim-id")
    claim.add_argument("--lease-minutes", type=int, default=30)

    for name in ("renew", "release", "submit"):
        p = add_ref(name, f"{name} a claimed task")
        p.add_argument("--claim-id", required=True)
        if name != "renew":
            p.add_argument("--evidence", required=True)

    sub.add_parser("review", help="list tasks awaiting approval")

    approve = add_ref("approve", "approve a submitted task as the human reviewer")
    approve.add_argument("--evidence", required=True)
    approve.add_argument("--actor", help="override review_actor from the config")

    resolve = sub.add_parser("resolve", help="print the board file and directory")
    resolve.add_argument("--dir", default=".")

    sub.add_parser("config", help="print the loaded skill config")

    return parser


def dispatch(args) -> object:
    if args.command == "read":
        return cmd_read(args)
    if args.command == "create":
        return cmd_create(args)
    if args.command == "capture":
        return cmd_capture(args)
    if args.command == "rename":
        return cmd_rename(args)
    if args.command == "delete":
        return cmd_delete(args)
    if args.command == "resolve":
        start = Path(args.dir).expanduser().resolve()
        board = board_for(start)
        return {"file": str(board), "dir": str(board.parent), "exists": board.is_file()}
    if args.command == "config":
        config = load_config()
        return {k: [str(d) for d in v] if isinstance(v, list) else v for k, v in config.items()}
    if args.command == "claim":
        return cmd_claim(args)
    if args.command == "renew":
        return cmd_claim_step(args, "renew", None)
    if args.command == "release":
        return cmd_claim_step(args, "release", args.evidence)
    if args.command == "submit":
        return cmd_claim_step(args, "submit", args.evidence)
    if args.command == "approve":
        return cmd_approve(args)
    if args.command == "review":
        return org(board_for(Path.cwd()).parent, "task", "review")["tasks"]
    if args.command == "obsolete":
        _, board, task_id = board_and_id(args)
        return org(board.parent, "todo", "set", str(board), f"id:{task_id}", "OBSOLETE")
    prefixes = {
        "set-state": ("todo", "set"),
        "set-deadline": ("deadline",),
        "add-tag": ("tag", "add"),
        "remove-tag": ("tag", "remove"),
        "append": ("append",),
        "archive": ("archive",),
    }
    if args.command in prefixes:
        value = getattr(args, "value", None)
        return cmd_ref_verb(args, prefixes[args.command], *([value] if value is not None else []))
    raise Fail(f"unknown command {args.command}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = dispatch(args)
    except Fail as failure:
        print(str(failure), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    elif isinstance(result, list):
        for item in result:
            print(f"{item.get('todo', ''):<12} {item.get('title', '')}  ({item.get('path', item.get('file', ''))})")
    elif isinstance(result, dict):
        for key, value in result.items():
            print(f"{key}: {value}")
    else:
        print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
