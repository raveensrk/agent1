#!/usr/bin/env python3
# harness-check: {"id": "interpreter_resolves", "applies": ["*.py", "*.sh", "*.bash", "*.zsh", "*.rb", "*.pl", "*.md"], "quadrant": "feedback/computational"}
"""Every interpreter named by a shebang or a rule must exist on this machine.

A shebang naming an interpreter that is not installed fails with
`command not found`, and a rule naming one sends every future session down the
same dead end. This check reads both: the first line of every script it is
given, and interpreter-like tokens inside code spans of any markdown it is
given - a bare span like `python3.N` as well as a `#!/usr/bin/env python3.N`
shebang. The fix hint lists the same family found on PATH, so it never goes
stale against what is installed.

    interpreter_resolves.py FILE...      (or paths on stdin)

The checks honour the same escape hatch as the tool this is shaped after: a
line containing `lint:ignore` is not reported. It is greppable on purpose.
"""
from __future__ import annotations

import os
import re
import shutil
import sys

FILES = sys.argv[1:]
if not FILES and not sys.stdin.isatty():
    FILES = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]

INTERPRETER = re.compile(
    r"(?:#!/usr/bin/env\s+|#!/[\w/.-]+/|[\s(`])"
    r"((?:python|ruby|node|deno|bun|bash|zsh|sh|perl|lua|swift|elixir|php|uv)[0-9.]*)"
    r"(?![-\w])"
)
CODE_SPAN = re.compile(r"`[^`]*`")
RESOLVES: dict[str, bool] = {}


def resolves(name: str) -> bool:
    if name not in RESOLVES:
        RESOLVES[name] = bool(shutil.which(name))
    return RESOLVES[name]


def installed_like(name: str) -> list[str]:
    """Executables on PATH from the same family as name: python3.99 -> python3, python3.14, ..."""
    family = re.match(r"[^\d.]+", name)
    if not family:
        return []
    pattern = re.compile(re.escape(family.group(0)) + r"[0-9.]*")
    found: set[str] = set()
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        try:
            entries = os.listdir(directory)
        except OSError:
            continue
        found.update(e for e in entries if pattern.fullmatch(e) and resolves(e))
    return sorted(found, key=lambda e: [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", e)])


def names_in_shebang(line: str) -> list[str]:
    body = line.strip()[2:].strip()
    parts = body.split()
    if not parts:
        return []
    exe = parts[0]
    if os.path.basename(exe) in ("env", "uv") and len(parts) > 1:
        exe = parts[1].lstrip("-")
    if exe == "uv" and len(parts) > 2 and parts[1] == "run":
        exe = parts[2].lstrip("-")
    return [os.path.basename(exe)]


def main() -> int:
    for path in FILES:
        try:
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        fenced = False
        for number, line in enumerate(lines, 1):
            if line.lstrip().startswith("```"):
                fenced = not fenced
                continue
            if "lint:ignore" in line:
                continue  # an explicit, greppable escape hatch, like `# rubocop:disable`
            candidates: list[str] = []
            if number == 1 and line.startswith("#!"):
                candidates = names_in_shebang(line)
            elif path.endswith(".md") and not fenced:
                for span in CODE_SPAN.findall(line):
                    candidates += [m.group(1) for m in INTERPRETER.finditer(span)]
                if not candidates and "#!/usr/bin/env" in line:
                    candidates += [m.group(1) for m in INTERPRETER.finditer(line)]
            for name in dict.fromkeys(candidates):
                if not resolves(name):
                    here = ", ".join(installed_like(name))
                    here = f" ({here} here)" if here else ""
                    print(
                        f"{path}:{number}: interpreter not on this machine: {name} - "
                        f"fix: name an interpreter that exists{here} or install {name}"
                    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
