#!/usr/bin/env python3
# harness-check: {"id": "script_exec_bit", "applies": ["*.py", "*.sh", "*.bash", "*.zsh", "*.rb", "*.pl", "*.lua", "harness/githooks/*", "**/.githooks/*"], "quadrant": "feedback/computational"}
"""A file with a shebang is a script somebody runs, so it needs the exec bit.

common.md: "Scripts meant to be run must always be executable. Add a shebang on
line 1, then chmod +x it." This checks both halves of that rule, and both halves
have two remedies: a shebang is either made executable, or dropped when the file
is never run directly - an imported module, a pasted fragment in ~/tmp, a file
only ever passed to python3. The message names both, because a fragment with a
copied shebang trips this twice a session and only the chmod remedy was offered.

    script_exec_bit.py FILE...      (or paths on stdin)

Git hooks are in scope too: git silently ignores a hook without the exec bit,
which is the quietest way for a guard to stop guarding.
"""
from __future__ import annotations

import os
import stat
import sys

# Paths arrive on stdin from the dispatcher, or as arguments when run by hand.
FILES = sys.argv[1:]
if not FILES and not sys.stdin.isatty():
    FILES = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]


def shebang(path: str) -> str | None:
    try:
        with open(path, "rb") as fh:
            first = fh.readline(200)
    except OSError:
        return None
    if not first.startswith(b"#!"):
        return None
    return first.decode("utf-8", "replace").strip()


def main() -> int:
    for path in FILES:
        line = shebang(path)
        executable = bool(os.stat(path).st_mode & stat.S_IXUSR)
        if line and not executable:
            print(
                f"{path}:1: shebang but no exec bit - fix: chmod +x {path}, "
                "or drop the shebang line if the file is never run directly (a module, "
                "an imported helper, a pasted fragment)"
            )
        elif executable and not line:
            print(
                f"{path}:1: exec bit but no shebang - fix: add a shebang line "
                f"(see the interpreter_resolves check for the interpreters that exist here), "
                f"or drop the exec bit with chmod -x {path}"
            )
    # Findings go to stdout; the dispatcher owns the exit code. Nonzero here
    # would be reported as this check being broken.
    return 0


if __name__ == "__main__":
    sys.exit(main())
