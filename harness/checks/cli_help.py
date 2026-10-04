#!/usr/bin/env python3
# harness-check: {"id": "cli_help", "applies": ["*"], "quadrant": "feedback/computational"}
"""Every CLI app carries -h and --help. That rule is hard.

common.md: "The --help|-h is a hard rule. Every CLI program/app must have these
two flags. The long/short pairing is optional: when possible add a short flag,
the long flag is the default."

So this check decides the hard half only:

  * A file that parses options - argparse, getopts, `$#`, sys.argv - must mention
    both `-h` and `--help`. argparse's default `add_help` binds both for free,
    and with it each subcommand too, so an argparse file passes without a word;
    only `add_help=False` asks for the explicit pair. A hand-parsed script needs
    both spellings, and the finding names the one that is missing. Option
    parsing is read from code, never from a string or a comment: a test that
    writes a fake CLI into a fixture owns no flags.
  * Which short letter a long flag takes stays prose, because "when possible" is
    a judgement: the free letters are not knowable from one file. The check never
    asks for a short alias for anything but help, and it never picks a letter.

Files under `harness/checks/` are exempt: the dispatcher
hands them file paths on stdin, they are not commands somebody types. So is a
backup copy (`box.sh.bak_codex`): nobody runs it. So is anything under `~/tmp`:
the scratch dir holds probes and copies that die with the session, and the
six-months-later author this rule protects never meets them. Measured 2026-10-04:
12 executables under `~/tmp` parse options, and not one is a command anybody
types. The scratch path is the exemption, not "outside a repo": a script in any
other temp dir still owes the pair, which the tests below exercise.

Measured before writing it: 46 tracked scripts through the dispatcher and 6 in
~/dot parse options and are missing the pair; every argparse CLI that day passed,
because add_help binds both flags for free.

    cli_help.py FILE...      (or paths on stdin)
"""
from __future__ import annotations

import ast
import fnmatch
import io
import os
import re
import stat
import sys
import tokenize

REPOS = os.path.expanduser("~/repos")
ALLOW = os.path.join(REPOS, "agent2", "harness", "data", "cli_help_allow.txt")
# The scratch dir: throwaway probes, not commands anybody types.
SCRATCH = os.path.realpath(os.path.expanduser("~/tmp"))

# Enough for any script; a bigger file is not a hand-written CLI.
MAX_BYTES = 400_000

# Paths arrive on stdin from the dispatcher, or as arguments when run by hand.
FILES = sys.argv[1:]
if not FILES and not sys.stdin.isatty():
    FILES = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]

# `-h` as its own token: quoted, or bare like `-h)` in a case arm. The lookaround
# keeps it out of `--help` and out of words like `-helpful`.
SHORT_HELP = re.compile(r"""["']-h["']|(?<![\w-])-h(?![\w-])|getopts[^\n]*h""")
LONG_HELP = re.compile(r"--help")
HAND_PARSED = re.compile(r"getopts|sys\.argv|\$#|case\s+\"?\$\{?1")
HARNESS_TOOLS = re.compile(r"(^|/)harness/(checks|guards)/")
BACKUP = re.compile(r"\.(bak|orig|rej|save)([._~-]|$)|~$")


def shebang(path: str) -> str | None:
    """The first line, when it is a shebang."""
    try:
        with open(path, "rb") as fh:
            first = fh.readline(200)
    except OSError:
        return None
    if not first.startswith(b"#!"):
        return None
    return first.decode("utf-8", "replace").strip()


def executable(path: str) -> bool:
    try:
        return bool(os.stat(path).st_mode & stat.S_IXUSR)
    except OSError:
        return False


def text_of(path: str) -> str:
    try:
        with open(path, "rb") as fh:
            return fh.read(MAX_BYTES).decode("utf-8", "replace")
    except OSError:
        return ""


def allow_patterns() -> list[str]:
    """Globs relative to the repo root, one per line, `#` comments ignored."""
    try:
        with open(ALLOW, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return []
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def allowed(rel: str, patterns: list[str]) -> bool:
    base = os.path.basename(rel)
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(base, p) for p in patterns)


def in_scratch(path: str) -> bool:
    """True for a probe under ~/tmp. Realpaths, so a symlinked scratch dir and
    the `/private` prefix macOS puts in front of `/tmp` compare equal."""
    p = os.path.realpath(path)
    return p == SCRATCH or p.startswith(SCRATCH + os.sep)


def code_only(text: str) -> str:
    """The file with its string and comment tokens dropped.

    `sys.argv` inside a string is not a file that parses options: a test that
    writes a fake CLI into a fixture, or a docstring showing an example, takes
    no arguments at all. Reading those as option parsing asked test files for
    -h and --help.
    """
    skip = {tokenize.STRING, tokenize.COMMENT}
    skip |= {tok for name in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END")
             if (tok := getattr(tokenize, name, None)) is not None}
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        # Joined with no separator: `sys` `.` `argv` must stay adjacent for the
        # regexes to see the same code they saw before strings were dropped.
        return "".join(tok.string for tok in tokens if tok.type not in skip)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return text  # unreadable source is not this check's finding


def adds_options(text: str) -> bool | None:
    """True when a python file adds argparse options, False when it adds none,
    and nil when it does not parse - the python_compiles check owns that."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_argument"
        for node in ast.walk(tree)
    )


def findings(rel: str, text: str) -> list[str]:
    """This REL file's findings, worded for the repo-relative path."""
    lines = text.splitlines()
    python = bool(lines) and "python" in lines[0]
    adds: bool | None = False
    if python:
        adds = adds_options(text)
        if adds is None:
            return []                      # does not parse; python_compiles owns it
    # argparse binds -h and --help by default, per parser and per subcommand.
    if adds and "add_help=False" not in text:
        return []
    parsed = text if not python else code_only(text)
    if not adds and not HAND_PARSED.search(parsed):
        return []                          # takes no options at all
    missing = [flag for flag, found in (("-h", SHORT_HELP.search(text)),
                                        ("--help", LONG_HELP.search(text)))
               if not found]
    if not missing:
        return []
    lacks = "neither -h nor --help" if len(missing) == 2 else f"no {missing[0]}"
    return [
        f"{rel}:1: mentions {lacks} - fix: -h and --help are the hard rule for a "
        "CLI; handle both and exit 0 (argparse's add_help gives both free, a shell "
        'script needs `case "$1" in -h|--help) usage; exit 0;; esac`)'
    ]


def main() -> int:
    patterns = allow_patterns()
    for path in FILES:
        rel = os.path.relpath(path)
        if (HARNESS_TOOLS.search(rel) or BACKUP.search(os.path.basename(rel))
                or in_scratch(path) or allowed(rel, patterns)):
            continue
        if not shebang(path) or not executable(path):
            continue
        for line in findings(rel, text_of(path)):
            print(line)
    # Findings go to stdout; the dispatcher owns the exit code. Nonzero here
    # would be reported as this check being broken.
    return 0


if __name__ == "__main__":
    sys.exit(main())
