#!/usr/bin/env python3
"""Open one lazygit tab per repo this session wrote to that has uncommitted changes.

Reads the pi session jsonl ($PI_SESSION_FILE, or the newest session under
~/.pi/agent/sessions), collects every path the session wrote to (edit/write
tool calls, plus bash `>`, `>>` and `tee` targets), maps each to its git repo
root, and keeps the roots whose `git status --porcelain` is non-empty.

Then opens one lazygit per repo: an unfocused Herdr tab inside Herdr, an iTerm
tab, or a Terminal.app window. Herdr takes precedence over an inherited
TERM_PROGRAM=iTerm.app.

Usage:
  open_dirty_repos.py [--dry-run] [--terminal auto|herdr|iterm|terminal]
                      [--session-file PATH] [--repo PATH]... [--self-test]

`--repo PATH` skips the session scan and opens that repo whether it is clean or
not - the user named it, so the dirty filter does not apply. Repeatable.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

WRITE_TOOLS = {"edit", "write"}
REDIRECT_RE = re.compile(r"(?:^|[\s;|&(])>>?\s*(\"[^\"]+\"|'[^']+'|[^\s;|&<>()]+)")
TEE_RE = re.compile(r"(?:^|[\s;|&(])tee(?:\s+-a)?\s+(\"[^\"]+\"|'[^']+'|[^\s;|&<>()]+)")


def session_path(explicit: str | None) -> Path:
    """The session jsonl to read: explicit flag, then $PI_SESSION_FILE, then newest."""
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get("PI_SESSION_FILE")
    if env and Path(env).is_file():
        return Path(env)
    root = Path.home() / ".pi" / "agent" / "sessions"
    files = sorted(root.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    if not files:
        raise SystemExit(f"ERROR: no session file. Not under {root} and PI_SESSION_FILE unset.")
    return files[-1]


def unquote(token: str) -> str:
    return token[1:-1] if len(token) > 1 and token[0] in "'\"" else token


def bash_targets(command: str) -> list[str]:
    """Paths a bash command writes to via redirection or tee."""
    found = [unquote(m.group(1)) for m in REDIRECT_RE.finditer(command)]
    found += [unquote(m.group(1)) for m in TEE_RE.finditer(command)]
    keep = []
    for raw in found:
        if raw.startswith("&") or raw.startswith("/dev/") or raw in {"-", "/"}:
            continue
        keep.append(raw)
    return keep


def session_writes(path: Path) -> tuple[list[str], Path]:
    """Raw write targets in first-touch order, plus the session cwd."""
    targets: list[str] = []
    cwd = Path.cwd()
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("type") == "session" and entry.get("cwd"):
            cwd = Path(entry["cwd"])
            continue
        for call in tool_calls(entry):
            name = call.get("name", "")
            args = call.get("args") or call.get("arguments") or call.get("input") or {}
            if not isinstance(args, dict):
                continue
            if name in WRITE_TOOLS and args.get("path"):
                targets.append(str(args["path"]))
            elif name == "bash" and args.get("command"):
                targets.extend(bash_targets(str(args["command"])))
    return targets, cwd


def tool_calls(entry: dict) -> list[dict]:
    """Tool call records in one session entry, for the shapes pi has written."""
    message = entry.get("message") if isinstance(entry.get("message"), dict) else entry
    content = message.get("content")
    calls = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") in ("toolCall", "tool_use"):
                calls.append(block)
    if message.get("type") in ("toolCall", "tool_use"):
        calls.append(message)
    return calls


def repo_root(target: str, cwd: Path) -> Path | None:
    """Walk up from a written path to the directory holding .git."""
    path = Path(target).expanduser()
    if not path.is_absolute():
        path = cwd / path
    start = path if path.is_dir() else path.parent
    for candidate in [start, *start.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    ).stdout


def dirty_state(root: Path) -> tuple[int, int, str] | None:
    """(changed, untracked, branch), or None when the repo is clean."""
    status = git(root, "status", "--porcelain")
    lines = [l for l in status.splitlines() if l.strip()]
    if not lines:
        return None
    untracked = sum(1 for l in lines if l.startswith("??"))
    changed = len(lines) - untracked
    branch = git(root, "symbolic-ref", "--short", "-q", "HEAD").strip() or "detached"
    return changed, untracked, branch


def collect(targets: list[str], cwd: Path) -> list[tuple[str, Path, tuple[int, int, str]]]:
    """Dirty repos in first-touch order: (name, root, (changed, untracked, branch))."""
    rows: list[tuple[str, Path, tuple[int, int, str]]] = []
    seen: set[Path] = set()
    for target in targets:
        root = repo_root(target, cwd)
        if root is None or root in seen:
            continue
        seen.add(root)
        state = dirty_state(root)
        if state is not None:
            rows.append((root.name, root, state))
    return rows


def named_repo(target: str) -> tuple[str, Path, tuple[int, int, str]] | None:
    """One repo the user named by path, clean or dirty; None when it is not a repo."""
    root = repo_root(target, Path.cwd())
    if root is None:
        return None
    branch = git(root, "symbolic-ref", "--short", "-q", "HEAD").strip() or "detached"
    return root.name, root, dirty_state(root) or (0, 0, branch)


def pick_terminal(requested: str) -> str:
    if requested in ("herdr", "iterm", "terminal"):
        return requested
    if os.environ.get("HERDR_ENV") == "1":
        return "herdr"
    program = os.environ.get("TERM_PROGRAM", "")
    if program == "iTerm.app":
        return "iterm"
    if program == "Apple_Terminal":
        return "terminal"
    running = subprocess.run(["pgrep", "-fq", "iTerm.app/Contents/MacOS/iTerm2"], check=False)
    return "iterm" if running.returncode == 0 else "terminal"


def applescript_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def shell_command(root: Path, name: str) -> str:
    """cd into the repo, title the tab after lazygit has set its own, run lazygit.

    lazygit overwrites the tab title at startup, so the title (OSC 1) is set
    from the same tty one second later. `exec` closes the tab when lazygit quits.
    """
    title = shlex.quote(f"lazygit: {name}")
    return (
        f"cd {shlex.quote(str(root))} && "
        f"{{ ( sleep 1; printf '\\033]1;%s\\007' {title} ) & exec lazygit; }}"
    )


def open_herdr(rows: list[tuple[str, Path, tuple[int, int, str]]]) -> None:
    """Create an unfocused tab in the current Herdr workspace for each repo."""
    if os.environ.get("HERDR_ENV") != "1":
        raise SystemExit("ERROR: Herdr tabs require HERDR_ENV=1. Run from a Herdr pane instead.")
    workspace = os.environ.get("HERDR_WORKSPACE_ID")
    if not workspace:
        raise SystemExit("ERROR: HERDR_WORKSPACE_ID missing. Run from a Herdr pane instead.")
    if not shutil.which("herdr"):
        raise SystemExit("ERROR: herdr not on PATH. Install Herdr or use --terminal iterm.")

    for name, root, _ in rows:
        created = subprocess.run(
            ["herdr", "tab", "create", "--workspace", workspace, "--cwd", str(root),
             "--label", f"lazygit: {name}", "--no-focus"],
            capture_output=True, text=True, check=False,
        )
        if created.returncode:
            raise SystemExit(f"ERROR: herdr tab create failed: {created.stderr.strip()}")
        try:
            pane = json.loads(created.stdout)["result"]["root_pane"]["pane_id"]
        except (ValueError, KeyError, TypeError):
            raise SystemExit(f"ERROR: herdr tab create returned no pane ID: {created.stdout.strip()}") from None

        started = subprocess.run(
            ["herdr", "pane", "run", pane, "exec lazygit"],
            capture_output=True, text=True, check=False,
        )
        if started.returncode:
            raise SystemExit(f"ERROR: herdr pane run failed for {pane}: {started.stderr.strip()}")


def terminal_has_idle_prompt() -> bool:
    """Whether Terminal.app's front window holds an idle shell prompt.

    `do script` types into that shell instead of opening a window, which would
    eat a shell the user has open - so that case prints commands instead.
    """
    script = (
        'tell application id "com.apple.Terminal"\n'
        "  if (count of windows) is 0 then return \"no\"\n"
        '  if (count of tabs of front window) is 0 then return "no"\n'
        '  if busy of selected tab of front window then return "no"\n'
        '  return "yes"\n'
        "end tell"
    )
    done = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)
    return done.stdout.strip() == "yes"


def open_tabs(rows: list[tuple[str, Path, tuple[int, int, str]]], mode: str) -> None:
    if mode == "herdr":
        open_herdr(rows)
        return
    records = ", ".join(
        "{" + applescript_string(name) + ", " + applescript_string(shell_command(root, name)) + "}"
        for name, root, _ in rows
    )
    body = f"set repos to {{{records}}}\n"
    if mode == "tabs":
        body += """
tell current window
  repeat with r in repos
    set t to create tab with default profile
    tell current session of t
      write text (item 2 of r)
    end tell
  end repeat
end tell
"""
        app = 'application id "com.googlecode.iterm2"'
    elif mode == "commands":
        # Terminal.app has no tab creation in AppleScript, and `do script`
        # would type into the idle shell in front of it.
        for _, root, _ in rows:
            print(f"  cd {shlex.quote(str(root))} && exec lazygit")
        return
    else:
        # Terminal.app cannot make tabs or windows: `make new window` fails and
        # `do script X in front window` types into the current tab. `do script
        # X` opens a window only while the tab in front of it is busy.
        body += """
repeat with r in repos
  do script (item 2 of r)
end repeat
"""
        app = 'application id "com.apple.Terminal"'
    script = f"tell {app}\n{body}end tell\n"
    done = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise SystemExit(f"ERROR: osascript failed: {done.stderr.strip()}")


def report(rows, what: str) -> None:
    if not rows:
        print("No dirty repos found in this session.")
        return
    all_dirty = all(changed or untracked for _, _, (changed, untracked, _) in rows)
    head = f"{len(rows)} repos with uncommitted changes" if all_dirty else f"{len(rows)} repos"
    print(f"{head}, {what}")
    width = max(len(name) for name, _, _ in rows)
    for name, _, (changed, untracked, branch) in rows:
        state = f"{changed} changed, {untracked} untracked" if changed or untracked else "clean"
        print(f"  {name:<{width}}  {state}  ({branch})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="list repos, open nothing")
    parser.add_argument(
        "--terminal", choices=("auto", "herdr", "iterm", "terminal"), default="auto", help="which terminal to use"
    )
    parser.add_argument("--session-file", help="session jsonl to read instead of the current one")
    parser.add_argument(
        "--repo",
        action="append",
        metavar="PATH",
        help="open this repo whether clean or not, skipping the session scan; repeatable",
    )
    parser.add_argument("--self-test", action="store_true", help="run the built-in check")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    if not shutil.which("lazygit"):
        raise SystemExit("ERROR: lazygit not on PATH. Install it: brew install lazygit")

    if args.repo:
        rows: list[tuple[str, Path, tuple[int, int, str]]] = []
        for target in args.repo:
            row = named_repo(target)
            if row is None:
                raise SystemExit(f"ERROR: no git repo at {target}")
            if all(row[1] != existing[1] for existing in rows):
                rows.append(row)
    else:
        path = session_path(args.session_file)
        targets, cwd = session_writes(path)
        rows = collect(targets, cwd)
    terminal = pick_terminal(args.terminal)
    if terminal == "herdr":
        mode, what = "herdr", "opening tabs in Herdr"
    elif terminal == "iterm":
        mode, what = "tabs", "opening tabs in iTerm"
    elif terminal_has_idle_prompt():
        mode, what = "commands", "Terminal.app has an idle shell in front: paste these"
    else:
        mode, what = "windows", f"Terminal.app cannot open tabs: opening {len(rows)} window(s)"
    if args.dry_run:
        what = "dry run, nothing opened"
    report(rows, what)
    if rows and not args.dry_run:
        open_tabs(rows, mode)
    return 0


def self_test() -> int:
    """Check repo discovery and terminal launch paths on a scratch repo."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "scratch_repo"
        (repo / "src").mkdir(parents=True)
        run = lambda *a: subprocess.run(a, cwd=repo, capture_output=True, check=True)
        run("git", "init", "-q")
        (repo / "src" / "tracked.txt").write_text("one\n")
        run("git", "add", ".")
        # staged-and-modified, plus untracked: dirty without any commit.
        (repo / "src" / "tracked.txt").write_text("two\n")
        (repo / "src" / "fresh.txt").write_text("x\n")

        session = Path(tmp) / "session.jsonl"
        entries = [
            {"type": "session", "cwd": tmp},
            {
                "type": "message",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "toolCall", "name": "edit", "args": {"path": f"{repo}/src/tracked.txt"}},
                        {"type": "toolCall", "name": "read", "args": {"path": "/etc/hosts"}},
                        {"type": "toolCall", "name": "bash", "args": {"command": f"echo hi > {repo}/src/fresh.txt 2>/dev/null"}},
                        {"type": "toolCall", "name": "bash", "args": {"command": "which lazygit | tee /dev/null"}},
                    ],
                },
            },
            # a format variant, and a duplicate of the same repo
            {"type": "toolCall", "name": "write", "args": {"path": "scratch_repo/src/fresh.txt"}},
            {"type": "message", "message": {"role": "assistant", "content": [{"type": "tool_use", "name": "write", "input": {"path": "/nope/not/here.txt"}}]}},
        ]
        session.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

        targets, cwd = session_writes(session)
        assert bash_targets(f"cat > {repo}/a && echo x >> {repo}/b | tee {repo}/c") == [
            f"{repo}/a", f"{repo}/b", f"{repo}/c"
        ], "redirect/tee extraction"
        assert "/dev/null" not in targets, "device targets dropped"
        assert f"{repo}/src/fresh.txt" in targets, "redirect target kept"
        rows = collect(targets, cwd)
        assert len(rows) == 1 and rows[0][:2] == ("scratch_repo", repo), rows
        changed, untracked, branch = rows[0][2]
        assert (changed, untracked) == (1, 1) and branch, rows
        assert repo_root("relative/thing.py", cwd) is None, "non-repo path yields no root"

        with patch.dict(os.environ, {"HERDR_ENV": "1", "HERDR_WORKSPACE_ID": "w1", "TERM_PROGRAM": "iTerm.app"}), \
             patch("shutil.which", return_value="herdr"), patch("subprocess.run") as cli:
            cli.side_effect = [
                subprocess.CompletedProcess([], 0, '{"result":{"root_pane":{"pane_id":"w1:p9"}}}', ""),
                subprocess.CompletedProcess([], 0, "", ""),
            ]
            assert pick_terminal("auto") == "herdr"
            assert pick_terminal("iterm") == "iterm", "explicit override wins"
            open_herdr(rows)
            assert [call.args[0] for call in cli.call_args_list] == [
                ["herdr", "tab", "create", "--workspace", "w1", "--cwd", str(repo),
                 "--label", "lazygit: scratch_repo", "--no-focus"],
                ["herdr", "pane", "run", "w1:p9", "exec lazygit"],
            ], "Herdr tab stays in the current workspace without stealing focus"

        with patch.dict(os.environ, {"HERDR_ENV": "", "TERM_PROGRAM": "iTerm.app"}):
            assert pick_terminal("auto") == "iterm", "outside Herdr, keep iTerm behavior"
            try:
                open_herdr(rows)
                assert False, "Herdr outside a managed pane must fail"
            except SystemExit as exc:
                assert "HERDR_ENV=1" in str(exc)

        with patch.dict(os.environ, {"HERDR_ENV": "", "TERM_PROGRAM": "Apple_Terminal"}):
            assert pick_terminal("auto") == "terminal", "outside Herdr, keep Terminal.app behavior"

        with patch.dict(os.environ, {"HERDR_ENV": "1", "HERDR_WORKSPACE_ID": "w1"}), \
             patch("shutil.which", return_value="herdr"), \
             patch("subprocess.run", return_value=subprocess.CompletedProcess([], 1, "", "no server")):
            try:
                open_herdr(rows)
                assert False, "a failed Herdr command must stop"
            except SystemExit as exc:
                assert "no server" in str(exc)

        print("self-test ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
