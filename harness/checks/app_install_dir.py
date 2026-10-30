#!/usr/bin/env python3
# harness-check: {"id": "app_install_dir", "applies": ["*", "!**/archive/**", "!harness/checks/app_install_dir.py", "!harness/tests/**", "!**/node_modules/**", "!**/target/**", "!**/build/**", "!**/.build/**", "!**/_site/**", "!**/venv/**", "!**/zig-pkg/**", "!**/notes/**", "!**/content/**", "!**/deck/**", "!*.html", "!*.json", "!*.rec", "!*.elim", "!*.txt", "!*.lock"], "quadrant": "feedback/computational"}
"""Apps from ~/repos install in ~/Applications/My_Apps and never touch the Dock.

Felis is the one exception: ~/Applications/MosaixDesign_Apps/Felis.

macos.md: not ~/Applications itself, not /Applications, no pinning, no
`killall Dock`. A line is an install when it copies, moves or assigns an app
folder (cp, ditto, rsync, mv, copytree, an `app`/`dest` variable) and names an
Applications folder that is not My_Apps; a lookup such as finding Chrome in
/Applications is not an install and is not reported. Markdown is checked only
inside fenced code, so prose that explains the rule does not trip it. A line
containing `lint:ignore` is not reported.

    app_install_dir.py FILE...      (or paths on stdin)
"""
from __future__ import annotations

import re
import sys

FILES = sys.argv[1:]
if not FILES and not sys.stdin.isatty():
    FILES = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]

DOCK = re.compile(r"killall\W+Dock\b|persistent-apps|favorite-apps|\bdockutil\b")
# A path-like Applications: after / " ' or ~, and not /System/Applications.
APPS = re.compile(r"""(?<!/System)(?<=[/"'~])Applications\b""")
MY_APPS = re.compile(r"""\s*(/|"\s*/\s*"|",\s*"|'\s*/\s*'|',\s*')(My_Apps|MosaixDesign_Apps/Felis)\b""")
INSTALL = re.compile(
    r"\b(cp|ditto|rsync|mv|install|copytree|copy2|rename)\b|-app\b"
    r"|\b(app|apps|dest|app_dir|apps_dir|app-dir|stage|target)\w*\s*:?=",
    re.IGNORECASE,
)
FIX_DIR = ('installs a Mac app outside ~/Applications/My_Apps; install into '
           '"$HOME/Applications/My_Apps/<Name>.app" (agent1 macos.md)')
FIX_DOCK = ("touches the Dock; drop it - apps from ~/repos are never pinned, "
            "the user pins one by hand (agent1 macos.md)")
MAX_BYTES = 1_000_000


def bad_dir(line: str) -> bool:
    if not INSTALL.search(line):
        return False
    return any(not MY_APPS.match(line, m.end()) for m in APPS.finditer(line))


def code_lines(path: str, lines: list[str]):
    """(number, line) pairs worth checking: all of them, or fenced code in Markdown."""
    if not path.endswith(".md"):
        yield from enumerate(lines, 1)
        return
    fence = None
    for number, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if fence is None and stripped.startswith(("```", "~~~")):
            fence = stripped[:3]
        elif fence and stripped.startswith(fence):
            fence = None
        elif fence:
            yield number, line


def main() -> int:
    for path in FILES:
        try:
            with open(path, "rb") as fh:
                raw = fh.read(MAX_BYTES + 1)
        except (FileNotFoundError, IsADirectoryError):
            continue
        if len(raw) > MAX_BYTES or b"\0" in raw:
            continue
        try:
            lines = raw.decode("utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for number, line in code_lines(path, lines):
            if "lint:ignore" in line:
                continue
            if DOCK.search(line):
                print(f"{path}:{number}: {FIX_DOCK}")
            elif bad_dir(line):
                print(f"{path}:{number}: {FIX_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
