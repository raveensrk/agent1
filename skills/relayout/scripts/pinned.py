#!/usr/bin/env python3
"""List the paths in a git repo that a relayout must not move. Read-only.

    python3 pinned.py [DIR] [--root PATH ...]
    python3 pinned.py -h|--help    short help
    python3 pinned.py help         this text

Prints one line per pinned path, `PATH: KIND: EVIDENCE`, sorted by path, then
a count line. KIND is one of:

  outside  a file outside the repo names the path: another repo, a dotfile,
           a setting. EVIDENCE is the first such file and line, and how many
           more there are.
  tool     a tool finds the path by its name: Cargo's src/main.rs, SwiftPM's
           Sources/, a Claude plugin's skills/, a skill's folder.
  root     a root file every repo keeps: a README, AGENTS.md, a license, a
           build file, a dotfile.

A path ending in `/` is the folder itself: it keeps its name and place, while
the files inside may still move. A path ending in `/**` is the folder and
everything in it.

Outside references come from one `rg` run over the roots that exist: ~/repos,
~/dot, the git and shell dotfiles in ~, Claude's and pi's settings, prompts
and skills, ~/.agents and ~/Library/LaunchAgents. `--root` replaces that list.
A reference counts only when it is anchored: `~/repos/NAME/PATH`,
`$HOME/repos/NAME/PATH`, the absolute path, or `../NAME/PATH` from a sibling.
A bare `NAME/PATH` in prose does not count, and neither does a reference to a
path git does not track. Logs (`*.jsonl`, `*.log`), `.git`, `node_modules`,
`target` and the repo itself are skipped.

Options:
  DIR            a path inside the repo; default the current directory
  --root, -r     search this root for outside references instead of the
                 defaults; repeat it for more roots

Env: HOME, for ~. Reads: `git ls-files` and `git config` of the repo, and the
files under the roots. Writes nothing. Needs git and rg (ripgrep).

Exit codes: 0 when the list printed; 1 on a refusal or a failure - not a git
repo, a missing root, rg missing or past its 50 s limit - with
`pinned.py: <message>` on stderr.

Example: python3 pinned.py ~/repos/agent1
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import urllib.parse

PROG = "pinned.py"
RG_TIMEOUT = 50  # seconds: one bash call gets 60

# Searched for outside references, relative to ~, when they exist.
DEFAULT_ROOTS = (
    "repos",
    "dot",
    ".gitconfig",
    ".zshrc",
    ".zprofile",
    ".zshenv",
    ".bashrc",
    ".bash_profile",
    ".profile",
    ".claude/CLAUDE.md",
    ".claude/settings.json",
    ".claude/settings.local.json",
    ".claude/skills",
    ".claude/commands",
    ".claude/agents",
    ".claude/hooks",
    ".claude/plugins/installed_plugins.json",
    ".claude/plugins/known_marketplaces.json",
    ".pi/AGENTS.md",
    ".pi/settings.json",
    ".pi/mcp.json",
    ".pi/agent",
    ".pi/extensions",
    ".pi/prompts",
    ".pi/bin",
    ".agents",
    "Library/LaunchAgents",
)
SKIP_GLOBS = ("!.git", "!node_modules", "!target", "!*.jsonl", "!*.log")
PATH_CHARS = r"[A-Za-z0-9_.@%+/-]"

PYTHON = ("pyproject.toml", "setup.py", "setup.cfg", "src/", "tests/", "conftest.py",
          "uv.lock", "poetry.lock")
# A marker file, a reason, then the paths beside the marker that a tool finds
# by name. A marker may sit at any depth: a workspace member has its own.
TOOL_RULES = (
    ("Cargo.toml", "Cargo", ("Cargo.toml", "Cargo.lock", "build.rs", "src/main.rs",
                             "src/lib.rs", "src/bin/", "tests/", "benches/", "examples/")),
    ("Package.swift", "SwiftPM", ("Package.swift", "Package.resolved", "Sources/", "Tests/",
                                  "Plugins/")),
    ("deps.edn", "Clojure deps.edn", ("deps.edn", "build.clj", "src/", "test/", "resources/")),
    ("project.clj", "Leiningen", ("project.clj", "src/", "test/", "resources/")),
    ("go.mod", "Go", ("go.mod", "go.sum", "go.work", "cmd/", "internal/", "vendor/")),
    ("pyproject.toml", "Python", PYTHON),
    ("setup.py", "Python", PYTHON),
    ("package.json", "npm", ("package.json", "package-lock.json", "yarn.lock",
                             "pnpm-lock.yaml", "bun.lock", "bun.lockb", "tsconfig.json")),
    (".claude-plugin/plugin.json", "Claude plugin", (".claude-plugin/**", "skills/",
                                                     "commands/", "agents/", "hooks/",
                                                     ".mcp.json")),
)
ROOT_FILE = re.compile(
    r"(README|LICEN[CS]E|COPYING|CHANGELOG|CONTRIBUTING|NOTICE|AGENTS|CLAUDE|GEMINI)"
    r"([-_.]|$)", re.IGNORECASE)
ROOT_NAMES = {"Makefile", "GNUmakefile", "justfile", "Justfile", "Dockerfile", "Brewfile",
              "compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml",
              "flake.nix", "flake.lock", "shell.nix"}


def fail(message: str) -> None:
    print(f"{PROG}: {message}", file=sys.stderr)
    sys.exit(1)


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # a refusal exits 1, not argparse's 2
        fail(f"{message}; see {PROG} --help")


def parse(argv: list[str]) -> argparse.Namespace:
    parser = Parser(prog=PROG, description=__doc__.split("\n\n", 1)[0],
                    epilog=f"Long help: {PROG} help")
    parser.add_argument("dir", nargs="?", default=".", metavar="DIR",
                        help="a path inside the repo (default: the current directory)")
    parser.add_argument("--root", "-r", action="append", metavar="PATH",
                        help="search PATH for outside references instead of the "
                             "defaults; repeat it for more roots")
    return parser.parse_args(argv)


def git(where: str, *args: str) -> str | None:
    try:
        proc = subprocess.run(["git", "-C", where, *args], capture_output=True, text=True,
                              timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def rx(text: str) -> str:
    """Escape TEXT so Python's re and rg's Rust regex both read it literally."""
    return re.sub(r"([\\.+*?()|\[\]{}^$#&~-])", r"\\\1", text)


def anchors(root: str) -> list[str]:
    """Regexes that name a path inside ROOT from outside it. Group `p` is the path."""
    raw = os.path.expanduser("~")
    real = os.path.realpath(raw)
    rel = os.path.relpath(root, real)
    tail = f"/(?P<p>{PATH_CHARS}*)"
    if rel.startswith(".."):
        first = rx(root) + tail
    else:
        homes = ["~", r"\$HOME", r"\$\{HOME\}"] + [rx(h) for h in dict.fromkeys((raw, real))]
        first = f"(?:{'|'.join(homes)})/{rx(rel)}" + tail
    return [first, rf"\.\./{rx(os.path.basename(root))}" + tail]


def outside_pins(root: str, roots: list[str], tracked: set[str],
                 dirs: set[str]) -> dict[str, str]:
    """Tracked paths that files under ROOTS name, with the first place each is named."""
    patterns = anchors(root)
    # -H: name the file even when the only root is a file, like ~/.gitconfig.
    cmd = ["rg", "--no-config", "--color", "never", "-H", "-o", "-n", "--null", "--hidden",
           "--no-messages", "--max-filesize", "4M"]
    for glob in SKIP_GLOBS:
        cmd += ["-g", glob]
    for pattern in patterns:  # rg joins them into one regex: no group names
        cmd += ["-e", pattern.replace("?P<p>", "")]
    try:
        proc = subprocess.run(cmd + ["--", *roots], capture_output=True, encoding="utf-8",
                              errors="replace", timeout=RG_TIMEOUT)
    except FileNotFoundError:
        fail("rg not found; install ripgrep: brew install ripgrep")
    except subprocess.TimeoutExpired:
        fail(f"rg ran past {RG_TIMEOUT} s; search fewer roots: {PROG} DIR --root PATH")
    if proc.returncode == 2:
        print(f"{PROG}: warning: rg could not read some files", file=sys.stderr)
    compiled = [re.compile(p) for p in patterns]
    inside = root + os.sep
    seen: dict[str, list[str]] = {}
    real: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        source, _, rest = line.partition("\0")
        lineno, _, text = rest.partition(":")
        if source not in real:
            real[source] = os.path.realpath(source)
        if real[source].startswith(inside):
            continue
        match = next((m for m in (c.fullmatch(text) for c in compiled) if m), None)
        if not match:
            continue
        rel = os.path.normpath(urllib.parse.unquote(match.group("p").rstrip(".")))
        if rel in tracked:
            key = rel
        elif rel in dirs:
            key = rel + "/**"
        else:
            continue  # the repo root itself, a path outside it, or one git does not track
        seen.setdefault(key, []).append(f"{source}:{lineno}")
    return {key: where[0] + (f" (+{len(where) - 1} more)" if len(where) > 1 else "")
            for key, where in seen.items()}


def exists(path: str, tracked: set[str], dirs: set[str]) -> bool:
    if path.endswith("/**"):
        return path[:-3] in dirs
    if path.endswith("/"):
        return path[:-1] in dirs
    return path in tracked


def tool_pins(root: str, tracked: set[str], dirs: set[str]) -> dict[str, str]:
    pins: dict[str, str] = {}
    for path in sorted(tracked):
        for marker, reason, names in TOOL_RULES:
            if path == marker or path.endswith("/" + marker):
                base = path[: len(path) - len(marker)]
                for name in names:
                    if exists(base + name, tracked, dirs):
                        pins.setdefault(base + name, reason)
        if os.path.basename(path) == "SKILL.md":
            folder = os.path.dirname(path)
            if folder:
                pins.setdefault(folder + "/", "skill; the folder name is the skill name")
            pins.setdefault(path, "skill; the file name is fixed")
    for folder in sorted(dirs):
        if folder.endswith((".xcodeproj", ".xcworkspace")):
            pins.setdefault(folder + "/**", "Xcode; it lists files by path")
    hooks = (git(root, "config", "--local", "--get", "core.hooksPath") or "").strip()
    if hooks:
        rel = os.path.relpath(os.path.realpath(os.path.join(root, os.path.expanduser(hooks))),
                              root)
        if rel in dirs:
            pins.setdefault(rel + "/**", "git core.hooksPath")
    return pins


def root_pins(tracked: set[str], dirs: set[str]) -> dict[str, str]:
    pins: dict[str, str] = {}
    for top in sorted({path.split("/", 1)[0] for path in tracked}):
        if top.startswith("."):
            pins[top + "/**" if top in dirs else top] = "dotfile at the root"
        elif top in tracked and (ROOT_FILE.match(top) or top in ROOT_NAMES):
            pins[top] = "root file"
    return pins


def main(argv: list[str]) -> int:
    args = parse(argv)
    target = os.path.expanduser(args.dir)
    if not os.path.isdir(target):
        fail(f"no such folder: {args.dir}")
    top = (git(target, "rev-parse", "--show-toplevel") or "").strip()
    if not top:
        fail(f"not a git repo: {args.dir}; relayout needs git to undo its moves")
    root = os.path.realpath(top)
    listing = git(root, "ls-files", "-z")
    if listing is None:
        fail(f"git ls-files failed in {root}")
    tracked = {path for path in listing.split("\0") if path}
    dirs: set[str] = set()
    for path in tracked:
        folder = os.path.dirname(path)
        while folder and folder not in dirs:
            dirs.add(folder)
            folder = os.path.dirname(folder)
    home = os.path.expanduser("~")
    if args.root:
        roots = [os.path.expanduser(r) for r in args.root]
        for r in roots:
            if not os.path.exists(r):
                fail(f"no such root: {r}")
    else:
        roots = [p for p in (os.path.join(home, r) for r in DEFAULT_ROOTS) if os.path.exists(p)]
    pins: dict[str, tuple[str, str]] = {}
    # Later kinds win a tie: outside over tool over root.
    for kind, found in (("root", root_pins(tracked, dirs)),
                        ("tool", tool_pins(root, tracked, dirs)),
                        ("outside", outside_pins(root, roots, tracked, dirs) if roots else {})):
        for path, evidence in found.items():
            pins[path] = (kind, evidence)
    for path in [p for p in pins if p.endswith("/") and p + "**" in pins]:
        del pins[path]
    for path in sorted(pins):
        kind, evidence = pins[path]
        print(f"{path}: {kind}: {evidence}")
    count = {k: sum(1 for kind, _ in pins.values() if kind == k)
             for k in ("outside", "tool", "root")}
    print(f"pinned: {len(pins)} (outside {count['outside']}, tool {count['tool']}, "
          f"root {count['root']})")
    return 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["help"]:
        print(__doc__.rstrip())
        sys.exit(0)
    sys.exit(main(sys.argv[1:]))
