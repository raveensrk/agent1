#!/usr/bin/env python3
"""Find the slow, hanging and repeated commands behind a session, and in history.

Two sources, both already on disk:

    analyze_commands.py --session [FILE]   pairs each tool call with its result
                                           in the pi transcript and times it
    analyze_commands.py --history [FILE]   mines ~/.bash_history for repeats,
                                           hang-prone shapes and prompt candidates
    analyze_commands.py --selftest         fixtures for the parsing and patterns

The point is a number, not an impression: "the review felt slow" is a finding
nobody can act on, "one call was 111s of a 137s session" is one you can.

Why the transcript and not the shell: bash on this machine records no duration
and no exit code. `grep -c '^#[0-9]\\{10\\}' ~/.bash_history` returns 0, so
history lines carry neither. Two ways to add them were probed and rejected -
PS0 runs its command substitution in a subshell, so the start time never
reaches the parent, and a DEBUG trap that sets it stops the prompt from being
printed. Timing user-typed commands needs its own verified change. A multi-line
paste still counts one line per command, and `set -o` state dumps are dropped
by name.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime

SLOW_SECONDS = 5.0
LONG_COMMAND = 140
# tools that spend their time on the user, not on the machine
WAIT_TOOLS = {"ask_user"}

# (id, regex, fix). Hang-prone shapes, not style preferences: each one has cost
# real minutes on this machine or blocks forever with no output. The guard in
# harness/extensions/command_guard.ts refuses the same two shapes the session
# hits most (recursive grep, a fetch with no timeout) before they run; keep the
# two lists in step when a shape moves from prose to a guard.
PATTERNS = [
    (
        "recursive-grep",
        re.compile(r"(?<![\w-])(grep|egrep|fgrep)\s+(-\w*[rR]|--recursive)"),
        'rg -n "pattern" path  # rg skips .git and node_modules by default',
    ),
    (
        "unbounded-find",
        re.compile(r"(?<![\w-])find\s+(/\S*|~|\$HOME)(?=[\s]|$)(?![^\n]*(-maxdepth|-prune))"),
        "find PATH -maxdepth 3 ...  # or rg --files PATH",
    ),
    (
        "find-exec",
        re.compile(r"(?<![\w-])find\b[^\n]*-exec\b"),
        "rg --files -0 | xargs -0 ...  # find -exec walks everything you never wanted",
    ),
    (
        "curl-no-timeout",
        re.compile(r"(?<![\w-])(curl|wget)\b(?![^\n]*(--max-time|--connect-timeout|-m\s))"),
        "curl --max-time 20 URL  # without it, a dead host blocks forever",
    ),
    (
        "tail-f",
        re.compile(r"(?<![\w-])tail\s+-\w*f"),
        "timeout 20 tail -f FILE  # never returns on its own",
    ),
    (
        "ssh-no-timeout",
        re.compile(r"(?<![\w-])ssh\b(?![^\n]*(ConnectTimeout|BatchMode))"),
        "ssh -o ConnectTimeout=5 -o BatchMode=yes HOST  # otherwise it waits on a prompt or a dead host",
    ),
    (
        "interactive-pager",
        re.compile(r"(?<![\w-])(less|more|vim|nano)\s+[\w./~-]"),
        "rg -n pattern FILE  # in a session, an editor waits for a human key",
    ),
    (
        "server-in-foreground",
        re.compile(r"(?<![\w-])(http\.server|runserver|flask run|rails (s|server))\b"),
        "cmd > /tmp/out.log 2>&1 & sleep 2  # a foreground server never returns",
    ),
]

TRIVIAL = {
    "cd", "ls", "q", "exit", "clear", "pwd", "ll", "la", "l", "history",
    "cdi", "cls", "c", "h",
}
# pi's own command line, so `pi update` is never read as a typed prompt
PI_SUBCOMMANDS = {
    "update", "install", "uninstall", "list", "help", "config", "login",
    "logout", "models", "sessions", "doctor", "extensions",
}


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def seconds(start: datetime | None, end: datetime | None) -> float | None:
    if not start or not end:
        return None
    return (end - start).total_seconds()


def read_transcript(path: str) -> tuple[list[dict], dict[str, dict], list[datetime]]:
    """Return (calls, results by toolCallId, every timestamp seen)."""
    calls: list[dict] = []
    results: dict[str, dict] = {}
    stamps: list[datetime] = []
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            stamp = parse_ts(entry.get("timestamp"))
            if stamp:
                stamps.append(stamp)
            message = entry.get("message") or {}
            content = message.get("content")
            if not isinstance(content, list):
                continue
            # a result is a message whose role says so; its content blocks are plain text
            if message.get("role") == "toolResult":
                text = " ".join(
                    b.get("text", "") for b in content if isinstance(b, dict)
                )
                results[message.get("toolCallId")] = {
                    "ts": stamp,
                    "text": text,
                    "error": bool(message.get("isError")),
                }
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "toolCall":
                    calls.append(
                        {
                            "id": block.get("id"),
                            "name": block.get("name"),
                            "args": block.get("arguments") or {},
                            "ts": stamp,
                        }
                    )
    return calls, results, stamps


def command_of(call: dict) -> str:
    args = call.get("args") or {}
    if call.get("name") == "bash":
        return str(args.get("command", ""))
    for key in ("path", "command", "query", "file_path", "pattern"):
        if key in args:
            return f"{key}={args[key]}"
    return json.dumps(args)[:120]


def status_of(result: dict | None, name: str = "") -> str:
    if result is None:
        return "unfinished"
    if name in WAIT_TOOLS:
        # a question waits for a human: think time, not tool slowness
        return "waiting"
    text, error = result.get("text", ""), result.get("error")
    if error and re.search(r"Command aborted|operation was aborted", text):
        return "aborted"
    # the words appear in ordinary output too, so only isError decides
    return "error" if error else "ok"


HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?")


def shell_of(command: str) -> str:
    """The command with quoted spans and heredoc bodies dropped.

    Writing a script that mentions `grep -r` is not running one, and a heredoc
    body is data. Both produced noise the first time this ran over its own
    session.
    """
    kept, heredoc = [], None
    for line in command.splitlines():
        if heredoc:
            if line.strip() == heredoc:
                heredoc = None
            continue
        match = HEREDOC.search(line)
        if match:
            heredoc = match.group(1)
            kept.append(line)
            continue
        kept.append(re.sub(r"'[^']*'|\"[^\"]*\"", "''", line))
    return "\n".join(kept)


def scan_patterns(text: str) -> list[tuple[str, str]]:
    command = shell_of(text)
    hits = []
    for name, pattern, fix in PATTERNS:
        if pattern.search(command):
            hits.append((name, fix))
    return hits


def report_session(path: str) -> int:
    calls, results, stamps = read_transcript(path)
    if not stamps:
        print(f"{path}: no timestamps found")
        return 2

    rows = []
    for call in calls:
        result = results.get(call.get("id"))
        rows.append(
            {
                "name": call.get("name"),
                "command": command_of(call),
                "seconds": seconds(call.get("ts"), (result or {}).get("ts")),
                "status": status_of(result, str(call.get("name"))),
            }
        )

    wall = seconds(min(stamps), max(stamps)) or 0.0
    tool_time = sum(r["seconds"] or 0.0 for r in rows)
    waiting = [r for r in rows if r["status"] == "waiting"]
    slow = sorted(
        (r for r in rows if r["status"] != "waiting" and (r["seconds"] or 0.0) >= SLOW_SECONDS),
        key=lambda r: r["seconds"] or 0.0,
        reverse=True,
    )
    aborted = [r for r in rows if r["status"] == "aborted"]
    failed = [r for r in rows if r["status"] == "error"]

    print(f"=== session: {os.path.basename(path)}")
    print(
        f"wall clock {wall:.1f}s, {len(rows)} tool calls, tool time {tool_time:.1f}s "
        f"({100 * tool_time / wall:.0f}% of the session)"
        if wall
        else f"{len(rows)} tool calls, tool time {tool_time:.1f}s"
    )
    top = rows and max(rows, key=lambda r: r["seconds"] or 0.0)
    if top and top["seconds"]:
        print(
            f"slowest call {top['seconds']:.1f}s = {100 * top['seconds'] / wall:.0f}% of wall clock: "
            f"{top['command'][:100]}"
        )

    if waiting:
        waited = sum(r["seconds"] or 0.0 for r in waiting)
        longest = max(r["seconds"] or 0.0 for r in waiting)
        print(
            f"\n=== waiting on the user: {len(waiting)} questions, {waited:.1f}s total, "
            f"longest {longest:.1f}s (think time, excluded from the slow list)"
        )

    print(f"\n=== over {SLOW_SECONDS:.0f}s ({len(slow)})")
    for row in slow:
        print(f"{row['seconds']:7.1f}s  {row['status']:10} {row['command'][:110]}")
    if not slow:
        print("none")

    if aborted or failed:
        print(f"\n=== aborted ({len(aborted)}) or failed ({len(failed)})")
        for row in aborted + failed:
            print(f"{row['status']:10} {row['command'][:110]}")

    seen: dict[str, int] = {}
    for row in rows:
        if row["name"] != "bash":
            continue
        seen[row["command"]] = seen.get(row["command"], 0) + 1
    repeats = {c: n for c, n in seen.items() if n > 1}
    print(f"\n=== repeated calls in one session ({len(repeats)})")
    for command, count in sorted(repeats.items(), key=lambda kv: -kv[1])[:5]:
        print(f"{count}x  {command[:110]}")
    if not repeats:
        print("none")

    hits = []
    for row in rows:
        for name, fix in scan_patterns(row["command"]):
            hits.append((name, row["command"], fix))
    print(f"\n=== hang-prone shapes ({len(hits)})")
    for name, command, fix in hits:
        print(f"{name}: {command[:90]}\n    fix: {fix}")
    if not hits:
        print("none")
    return 0


def read_history(path: str) -> list[str]:
    lines = []
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line or re.fullmatch(r"#\d{9,}", line):
                continue
            # `set -o` state dumps paste as dozens of lines; they are one act,
            # not 32 commands (observed: 32 of them in ~/.bash_history)
            if re.match(r"^set [+-]o\s", line):
                continue
            lines.append(line)
    return lines


def report_history(path: str) -> int:
    lines = read_history(path)
    if not lines:
        print(f"{path}: nothing to read")
        return 2
    print(f"=== history: {path} ({len(lines)} commands)")

    counts: dict[str, int] = {}
    prefixes: dict[str, int] = {}
    prompts: dict[str, int] = {}
    for line in lines:
        counts[line] = counts.get(line, 0) + 1
        words = line.split()
        if words and words[0] not in TRIVIAL:
            prefixes[" ".join(words[:2])] = prefixes.get(" ".join(words[:2]), 0) + 1
        if words and words[0] == "pi":
            rest = line[3:].strip()
            # `pi -r`, `pi update` and the rest of the CLI are subcommands, not prompts
            if rest.lstrip("'\"").startswith("-") or not rest[:1].isalpha():
                continue
            if rest.split()[0] in PI_SUBCOMMANDS:
                continue
            prompt = re.sub(r"\s+", " ", rest).strip().strip("'\"")[:100]
            if prompt:
                prompts[prompt] = prompts.get(prompt, 0) + 1

    print("\n=== repeated prefixes (3+), alias or script candidates")
    for prefix, count in sorted(prefixes.items(), key=lambda kv: -kv[1])[:12]:
        if count >= 3:
            print(f"{count:4}x  {prefix}")

    print("\n=== exact repeats (3+), a script, an alias, or a broken first attempt")
    for command, count in sorted(counts.items(), key=lambda kv: -kv[1])[:12]:
        if count >= 3 and command.split()[0] not in TRIVIAL:
            print(f"{count:4}x  {command[:110]}")

    long_ones = sorted((c for c in counts if len(c) >= LONG_COMMAND), key=lambda c: -counts[c])
    print(f"\n=== long one-liners ({len(long_ones)}), script candidates")
    for command in long_ones[:8]:
        print(f"{counts[command]:4}x  {command[:110]}")

    print(f"\n=== pi prompts typed more than once ({len(prompts)}), prompt-template candidates")
    for prompt, count in sorted(prompts.items(), key=lambda kv: -kv[1])[:8]:
        if count > 1:
            print(f"{count:4}x  {prompt[:100]}")
    if not any(n > 1 for n in prompts.values()):
        print("none")

    hits: dict[str, tuple[str, int, str]] = {}
    for line in lines:
        for name, fix in scan_patterns(line):
            _, count, _ = hits.get(name, (fix, 0, ""))
            hits[name] = (fix, count + 1, hits.get(name, (fix, 0, line))[2])
    print(f"\n=== hang-prone shapes ({len(hits)})")
    for name, (fix, count, example) in sorted(hits.items(), key=lambda kv: -kv[1][1]):
        print(f"{count:4}x  {name}")
        print(f"      eg: {example[:100]}")
        print(f"      fix: {fix}")
    if not hits:
        print("none")

    print(
        "\nno durations or exit codes in this file"
        f" (`grep -c '^#[0-9]\\{{10\\}}' {path}` = "
        f"{sum(1 for line in open(path, encoding='utf-8', errors='replace') if re.match(r'^#\\d{9,}', line))}),"
        "\nso this ranks by frequency, not by time. Durations come from --session."
    )
    return 0


def selftest() -> int:
    import tempfile

    call = {
        "type": "message",
        "timestamp": "2026-10-02T18:24:57.980Z",
        "message": {
            "role": "assistant",
            "content": [{"type": "toolCall", "id": "c1", "name": "bash",
                         "arguments": {"command": 'grep -rn "x" ~/repos'}}],
        },
    }
    result = {
        "type": "message",
        "timestamp": "2026-10-02T18:26:49.611Z",
        "message": {"role": "toolResult", "toolCallId": "c1", "isError": True,
                    "content": [{"type": "text", "text": "Command aborted"}]},
    }
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as handle:
        handle.write(json.dumps(call) + "\n" + json.dumps(result) + "\n")
        path = handle.name
    calls, results, stamps = read_transcript(path)
    os.unlink(path)

    assert len(calls) == 1 and calls[0]["id"] == "c1", calls
    assert round(seconds(calls[0]["ts"], results["c1"]["ts"])) == 112, results
    assert status_of(results["c1"]) == "aborted", status_of(results["c1"])
    assert status_of(None) == "unfinished"
    assert next(s for s in scan_patterns(calls[0]["args"]["command"]))[0] == "recursive-grep"

    blocked = [p[1] for p in PATTERNS if p[0] == "recursive-grep"][0]
    for bad in ["grep -rn x .", "grep -R x .", "grep --recursive x .", "egrep -r x ."]:
        assert blocked.search(bad), bad
    for good in ["rg -n x .", "grep -n x f", "xnargs -r grep", "git grep -n x"]:
        assert not blocked.search(good), good

    find_bad = [p[1] for p in PATTERNS if p[0] == "unbounded-find"][0]
    assert find_bad.search("find / -name x")
    assert find_bad.search("find ~ -iname '*bookmark*'")
    assert not find_bad.search("find . -maxdepth 3 -name x")
    assert not find_bad.search("find ~/repos -prune -name x")

    curl = [p[1] for p in PATTERNS if p[0] == "curl-no-timeout"][0]
    assert curl.search("curl https://example.com")
    assert not curl.search("curl --max-time 20 https://example.com")

    assert read_history.__name__ == "read_history"
    with tempfile.NamedTemporaryFile("w", suffix=".hist", delete=False) as handle:
        handle.write("#1790966367\nsleep 1\n\n  ls  \nsleep 1\nset +o keyword\n")
        hist = handle.name
    assert read_history(hist) == ["sleep 1", "ls", "sleep 1"], read_history(hist)
    os.unlink(hist)

    print("selftest ok: 111s call paired, aborted detected, patterns and history parsing hold")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    mode = args[0]
    target = args[1] if len(args) > 1 else None
    if mode == "--selftest":
        return selftest()
    if mode == "--session":
        path = target or os.environ.get("PI_SESSION_FILE")
        if not path:
            print("no transcript: pass a file or set PI_SESSION_FILE")
            return 2
        return report_session(path)
    if mode == "--history":
        path = target or os.path.expanduser("~/.bash_history")
        if not os.path.exists(path):
            print(f"{path}: not found")
            return 2
        return report_history(path)
    print(f"unknown mode {mode}; try --session, --history or --selftest")
    return 2


if __name__ == "__main__":
    sys.exit(main())
