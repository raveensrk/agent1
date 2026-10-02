#!/usr/bin/env python3
# harness-check: {"id": "python_compiles", "applies": ["*.py"], "quadrant": "feedback/computational"}
"""A .py file that does not parse is a broken edit no test may reach.

Caught live: an edit dropped the '#' from a comment line in a downloader
script and the syntax error only surfaced because that file happens to have
fixture tests. compile() is free and catches the same class of edit in every
.py file the session touched, tested or not.

    python_compiles.py FILE...      (or paths on stdin)
"""
import pathlib
import sys

# Paths arrive on stdin from the dispatcher, or as arguments when run by hand.
FILES = sys.argv[1:]
if not FILES and not sys.stdin.isatty():
    FILES = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]

for path in FILES:
    if not path:
        continue
    try:
        compile(pathlib.Path(path).read_text(), path, "exec")
    except SyntaxError as err:
        print(f"{path}:{err.lineno or 1}: does not compile: {err.msg}; "
              f"fix: read the file around line {err.lineno or 1} and repair the edit")
    except (OSError, UnicodeDecodeError):
        pass  # unreadable here is not a syntax finding