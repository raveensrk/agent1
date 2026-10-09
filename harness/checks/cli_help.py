#!/usr/bin/env python3
# harness-check: {"id": "cli_help", "applies": ["*"], "quadrant": "feedback/computational"}
"""Every CLI app carries -h, --help and a `help` command. That rule is hard.

experimental.md: -h and --help print the short help, `<program> help` the long
help. The check decides presence only - all three must be handled - and never
reads what they print. argparse binds -h and --help but no `help` command, so
an argparse file owes that one by hand: `sub.add_parser("help")`, or a
`sys.argv[1:2] == ["help"]` test before parse_args. `action="help"` is the
-h/--help binding, not the command, and does not count.

common.md: "The --help|-h is a hard rule. Every CLI program/app must have these
two flags. The long/short pairing is optional: when possible add a short flag,
the long flag is the default."

So this check decides the hard half only:

  * A file that parses options - argparse, getopts, `$#`, sys.argv - must mention
    both `-h` and `--help`. argparse's default `add_help` binds both for free,
    and with it each subcommand too, so an argparse file passes without a word;
    only `add_help=False` asks for the explicit pair, and not on a parser that
    only feeds `parents=`: that is the shared-flags idiom, and every parser
    built from it still binds both. A hand-parsed script needs
    both spellings, and the finding names the one that is missing. Option
    parsing is read from code, never from a string or a comment: a test that
    writes a fake CLI into a fixture owns no flags.
  * A runnable that takes no options owes the pair too: experimental.md puts a
    program's docs inside it, behind -h and --help. Exempt from that branch
    only: a script under a hooks dir (`hooks/`, `.githooks/`, `githooks/`,
    `git_hooks/`) and a file a test runner collects (`test_*.py`, `*_test.py`,
    `*.test.[jt]s`) - called, never typed. A typed runner like `tests/run_all.sh`
    or `test_collage.sh` owes it. A hook or test that parses options owes the
    pair, as before.
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

Measured 2026-10-09 over 390 tracked executables in ~/repos and ~/dot: the
no-arg branch added 204 findings to the 31 option-parser ones. 6 of the 204 are
not typed - 3 sourced files carrying a stray exec bit, 3 callbacks (ranger's
scope.sh, ptpython's startup file, a lazygit command) - so the finding names
both ways out. The trigger lints only edited files: old gaps surface when touched.

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
# A `help` command: the quoted word (not argparse's action="help"), a shell case
# arm like `help)` or `|help)`, or a test like `[ "$1" = help ]`. The lookbehind
# keeps `--help)` out.
HELP_CMD = re.compile(
    r"""(?<!action=)["']help["']|(?<![\w-])help\s*[|)]|\$\{?1(:-)?\}?["']?\s*==?\s*["']?help\b""")
HAND_PARSED = re.compile(r"getopts|sys\.argv|\$#|case\s+\"?\$\{?1")
HARNESS_TOOLS = re.compile(r"(^|/)harness/(checks|guards)/")
BACKUP = re.compile(r"\.(bak|orig|rej|save)([._~-]|$)|~$")
# Run by git or collected by a test runner, never typed: a no-arg one owes no help.
# e.g. config/git/hooks/pre-commit, test_wiki.py, wiki_test.py, wiki.test.ts.
# A typed runner - tests/run_all.sh, personal/ffmpeg/test_collage.sh - is not exempt.
UNTYPED = re.compile(r"(^|/)(\.githooks|githooks|git_hooks|hooks)/|(^|/)test_[^/]*\.py$|_test\.py$|\.test\.[jt]s$")
# argparse's parse calls bind -h and --help even with no option added; another
# object's parse_args does not, so these count only when argparse is imported.
PARSE = {"parse_args", "parse_known_args"}


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


def argparsed(text: str) -> bool | None:
    """True when a python file runs argparse, False when it does not, and nil
    when it does not parse - the python_compiles check owns that.

    `ArgumentParser(description=__doc__).parse_args()` adds no option and still
    answers -h and --help, so a parse call counts as much as an added option -
    when argparse is imported. `Config().parse_args(argv)` binds nothing."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    imported = any(
        isinstance(node, ast.Import) and any(a.name == "argparse" for a in node.names)
        or isinstance(node, ast.ImportFrom) and node.module == "argparse"
        for node in ast.walk(tree)
    )
    calls = {node.func.attr for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    return "add_argument" in calls or bool(imported and calls & PARSE)


def help_off(text: str) -> bool:
    """True when a parser really turns argparse's -h and --help off.

    `add_help=False` on a parser passed only as `parents=` turns nothing off.
    Reading every `add_help=False` as an opt-out flagged marriage_notes_2's
    publish/wiki.py on 2026-10-09, whose `wiki -h` and `wiki build -h` both work.
    An `add_help=False` parser not bound to a plain name still counts as off.
    """
    tree = ast.parse(text)
    parents = {name.id for node in ast.walk(tree)
               if isinstance(node, ast.keyword) and node.arg == "parents"
               for name in ast.walk(node.value) if isinstance(name, ast.Name)}
    bound = {id(node.value): node.targets[0].id for node in ast.walk(tree)
             if isinstance(node, ast.Assign) and len(node.targets) == 1
             and isinstance(node.targets[0], ast.Name)}
    return any(
        bound.get(id(node)) not in parents
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and any(kw.arg == "add_help" and isinstance(kw.value, ast.Constant)
                and kw.value.value is False for kw in node.keywords)
    )


def findings(rel: str, text: str) -> list[str]:
    """This REL file's findings, worded for the repo-relative path."""
    lines = text.splitlines()
    python = bool(lines) and "python" in lines[0]
    adds: bool | None = False
    if python:
        adds = argparsed(text)
        if adds is None:
            return []                      # does not parse; python_compiles owns it
    # argparse binds -h and --help by default, per parser and per subcommand.
    bound = bool(adds) and not help_off(text)
    parsed = text if not python else code_only(text)
    takes = adds or bool(HAND_PARSED.search(parsed))
    if not takes and UNTYPED.search(rel):
        return []                          # a no-arg hook or test: nobody types it
    missing = [flag for flag, found in (("-h", bound or SHORT_HELP.search(text)),
                                        ("--help", bound or LONG_HELP.search(text)),
                                        ("help", HELP_CMD.search(text)))
               if not found]
    if not missing:
        return []
    flags = [m for m in missing if m != "help"]
    parts = (["neither -h nor --help"] if len(flags) == 2 else [f"no {f}" for f in flags])
    parts += ["no `help` command"] if "help" in missing else []
    lacks = ", and ".join(parts)

    # A no-arg runnable owes all three too: its docs live inside it (experimental.md).
    if not takes:
        return [
            f"{rel}:1: runnable mentions {lacks} - fix: every runnable answers -h "
            "and --help with short help and `help` with its full docs (content: "
            "~/repos/agent1/cli.md), exits 0 and does nothing else; python, from "
            "the module docstring: `if sys.argv[1:2] in ([\"-h\"], [\"--help\"], "
            "[\"help\"]): print(__doc__ if sys.argv[1] == \"help\" else "
            "__doc__.split(\"\\n\\n\")[0]); sys.exit(0)`, shell, from the header "
            "comment: `case \"${1:-}\" in -h|--help) sed -n '2s/^# \\{0,1\\}//p' "
            "\"$0\"; exit 0;; help) sed -n '2,/^[^#]/s/^# \\{0,1\\}//p' \"$0\"; "
            "exit 0;; esac`; sourced, not run: `chmod -x` it; run by another "
            "program, not typed: list its repo-relative path in "
            "~/repos/agent2/harness/data/cli_help_allow.txt"
        ]
    return [
        f"{rel}:1: mentions {lacks} - fix: -h and --help (short help) and a "
        "`help` command (long help) are the hard rule for a CLI; handle all three "
        "and exit 0 (argparse's add_help gives -h and --help free, `help` needs "
        '`sub.add_parser("help")` or a `sys.argv[1:2] == ["help"]` test before '
        'parse_args; a shell script needs `case "$1" in -h|--help) usage; exit 0;; '
        "help) usage_long; exit 0;; esac`)"
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
