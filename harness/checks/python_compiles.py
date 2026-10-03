#!/usr/bin/env python3
# harness-check: {"id": "python_compiles", "quadrant": "feedback/computational"}
"""Python must parse wherever it runs, whatever the file is named.

Caught live: an edit dropped the '#' from a comment line in a downloader
script and the syntax error only surfaced because that file happens to have
fixture tests. compile() is free and catches the same class of edit in every
file the session touched, tested or not.

Extension globs hid the second half of that. `~/dot/script` holds extensionless
commands with a python shebang - yt-wl, bookmark, pi-clear, pi-completion-gen -
and `applies: ["*.py"]` never handed one to this check: a lint run over two
extensionless scripts, one syntax-broken and one missing its exec bit, printed
"5 checks, 2 files, 0 findings", while the same two files named .py printed
both findings. Adding a .py to the name was the only way to get checked.

So this check takes every file and decides from the first line. The sniff costs
0.1s over the whole ~/repos population, where 137 files carry a python shebang
and none of them fails to parse.

    python_compiles.py FILE...      (or paths on stdin)
"""
import pathlib
import re
import sys

SHEBANG = re.compile(rb"^#!.*\bpython[0-9.]*")

# Paths arrive on stdin from the dispatcher, or as arguments when run by hand.
FILES = sys.argv[1:]
if not FILES and not sys.stdin.isatty():
    FILES = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]


def runs_python(path: str) -> bool:
    """A .py file, or a file whose first line asks for Python."""
    if path.endswith(".py"):
        return True
    try:
        with open(path, "rb") as fh:
            return bool(SHEBANG.match(fh.readline(200)))
    except OSError:
        return False


for path in FILES:
    if not path or not runs_python(path):
        continue
    try:
        compile(pathlib.Path(path).read_text(), path, "exec")
    except SyntaxError as err:
        print(f"{path}:{err.lineno or 1}: does not compile: {err.msg}; "
              f"fix: read the file around line {err.lineno or 1} and repair the edit")
    except (OSError, UnicodeDecodeError):
        pass  # unreadable here is not a syntax finding
