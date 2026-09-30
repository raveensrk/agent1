#!/usr/bin/env python3
"""Install skills and commands into each agent harness, as symlinks.

Every installed item is a symlink back to its source, so `git pull` in that
source updates every harness at once. Skills go to each harness's own
directory: ~/.claude/skills for Claude Code and ~/.codex/skills for Codex.

Pi reads skills from ~/.agents/skills, so Pi gets symlinks there too. Links
that older versions installed into ~/.agents/skills for Codex are pruned when
they are no longer installed.

Usage:
  ./install.py                          install or update this repo's items
  ./install.py --dry-run                show what would change, change nothing
  ./install.py --force                  also replace symlinks that point elsewhere
  ./install.py --skill PATH             also install skills from PATH (repeatable)
  ./install.py --skill                  prompt for the path, with tab completion

`--skill PATH` accepts either a single skill (a directory holding SKILL.md) or a
directory that contains several, such as another repo's skills/ folder. Each
skill is installed under its directory name.

install.py records every link it creates in a manifest. Run ./uninstall.py to
remove them.

Safety:
  - Never deletes or overwrites a real file or directory, even with --force.
  - Pruning only touches symlinks that point into this checkout or that appear
    in the manifest.
  - A harness that is not installed (its home directory is missing) is skipped.

To add a harness or item type, add a line to HARNESSES or TARGETS.
"""
import argparse
import glob
import json
import os
import sys

REPO = os.path.dirname(os.path.realpath(__file__))
PROMPT_SENTINEL = "\x00prompt\x00"

# Harness name -> directory whose presence means the harness is installed.
HARNESSES = {
    "claude": "~/.claude",
    "codex": "~/.codex",
    "pi": "~/.pi",
}

# (source glob in this repo, destination directory, harnesses that read it).
# A glob ending in SKILL.md installs the directory holding it, so a stray file
# in skills/ is never installed as a skill.
TARGETS = [
    ("skills/*/SKILL.md", "~/.claude/skills", ["claude"]),
    ("skills/*/SKILL.md", "~/.codex/skills", ["codex"]),
    ("skills/*/SKILL.md", "~/.agents/skills", ["pi"]),
    ("commands/*.md", "~/.claude/commands", ["claude"]),
    ("commands/*.md", "~/.pi/agent/prompts", ["pi"]),  # Codex has no custom commands
]

# Skills from --skill go only to the skill directories, one link per directory.
SKILL_TARGETS = [
    ("~/.claude/skills", ["claude"]),
    ("~/.codex/skills", ["codex"]),
    ("~/.agents/skills", ["pi"]),
]

STORE_DIR = os.path.join(
    os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"),
    "agent-skills",
)
MANIFEST = os.path.join(STORE_DIR, "installed.json")

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}


def expand(path):
    return os.path.realpath(os.path.expanduser(path))


def sources(pattern):
    out = []
    for path in sorted(glob.glob(os.path.join(REPO, pattern))):
        if os.path.basename(path) == "SKILL.md":
            path = os.path.dirname(path)
        elif not os.path.isfile(path):
            continue
        out.append(path)
    return out


def link_target(link):
    """Absolute, resolved path a symlink points to (it may not exist)."""
    return os.path.realpath(os.path.join(os.path.dirname(link), os.readlink(link)))


def ours(link):
    return os.path.islink(link) and link_target(link).startswith(REPO + os.sep)


def find_skill_dirs(root, max_depth=4):
    """Every directory holding a SKILL.md at or under root."""
    root = expand(root)
    if os.path.isfile(os.path.join(root, "SKILL.md")):
        return [root]
    if not os.path.isdir(root):
        return []
    found = []
    root_depth = root.rstrip(os.sep).count(os.sep)
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            name for name in dirnames
            if name not in SKIP_DIRS and not name.startswith(".")
        )
        if current.count(os.sep) - root_depth >= max_depth:
            dirnames[:] = []
        if "SKILL.md" in filenames:
            found.append(current)
            dirnames[:] = []
    return sorted(found)


def _completer_candidates(line):
    directory, _, fragment = line.rpartition(os.sep)
    prefix = directory + os.sep if directory else ""
    base = os.path.expanduser(directory or ".")
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return []
    out = []
    for name in names:
        if not name.startswith(fragment):
            continue
        full = os.path.join(base, name)
        out.append(prefix + name + (os.sep if os.path.isdir(full) else ""))
    return out


def prompt_for_skill():
    """Read a path with readline tab completion. Requires an interactive tty."""
    if not sys.stdin.isatty():
        sys.exit("ERROR: --skill needs a path; pass --skill PATH or run it interactively")
    try:
        import readline
    except ImportError:
        readline = None
    if readline is not None:
        def completer(text, state):
            candidates = _completer_candidates(readline.get_line_buffer())
            return candidates[state] if state < len(candidates) else None

        readline.set_completer(completer)
        try:
            readline.parse_and_bind("tab: complete")
            readline.parse_and_bind("bind ^I rl_complete")  # macOS libedit
        except Exception:
            pass
    try:
        value = input("skill path: ").strip()
    except (EOFError, KeyboardInterrupt):
        sys.exit("\nERROR: no path given")
    if not value:
        sys.exit("ERROR: no path given")
    return value


def load_manifest():
    try:
        with open(MANIFEST) as handle:
            data = json.load(handle)
    except (IOError, ValueError):
        return {}
    out = {}
    for entry in data.get("links", []):
        dest, source = entry.get("dest"), entry.get("source")
        if dest and source:
            out[dest] = source
    return out


def save_manifest(managed):
    if not managed:
        try:
            os.unlink(MANIFEST)
        except OSError:
            pass
        return
    os.makedirs(STORE_DIR, exist_ok=True)
    payload = {"links": [{"dest": dest, "source": source}
                         for dest, source in sorted(managed.items())]}
    tmp = MANIFEST + ".tmp"
    with open(tmp, "w") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, MANIFEST)


class Run:
    def __init__(self, dry, force):
        self.dry, self.force, self.conflicts, self.errors = dry, force, 0, 0

    def apply(self, fn, *args):
        """Run one change; report an OS error and carry on with the rest."""
        try:
            fn(*args)
        except OSError as e:
            self.errors += 1
            self.say("error", args[-1], "%s" % (e.strerror or e))

    def say(self, action, path, note=""):
        home = os.path.expanduser("~")
        path = "~" + path[len(home):] if path.startswith(home + os.sep) else path
        print("%-9s %s%s" % (action, path, "  " + note if note else ""))

    def remove(self, link, note):
        self.say("remove", link, note)
        if not self.dry:
            self.apply(os.unlink, link)

    def link(self, src, dest):
        if os.path.islink(dest):
            if link_target(dest) == os.path.realpath(src):
                return self.say("ok", dest)
            if not (self.force or ours(dest)):
                self.conflicts += 1
                return self.say("conflict", dest, "symlink to %s; use --force" % os.readlink(dest))
            self.say("replace", dest, "was -> %s" % os.readlink(dest))
            if not self.dry:
                self.apply(os.unlink, dest)
        elif os.path.lexists(dest):
            self.conflicts += 1
            return self.say("conflict", dest, "real file or directory; move it away by hand")
        else:
            self.say("link", dest)
        if not self.dry:
            self.apply(self._symlink, src, dest)

    @staticmethod
    def _symlink(src, dest):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        os.symlink(src, dest)

    def prune(self, dest_dir, wanted, managed):
        """Remove symlinks we own whose source is gone or no longer installed."""
        if not os.path.isdir(dest_dir):
            return
        for name in sorted(os.listdir(dest_dir)):
            path = os.path.join(dest_dir, name)
            if name in wanted or not os.path.islink(path):
                continue
            if ours(path) or path in managed:
                self.remove(path, "stale")
                managed.pop(path, None)


def installed(harness):
    return os.path.isdir(os.path.expanduser(HARNESSES[harness]))


def harness_present(readers):
    return any(installed(h) for h in readers)


def build_plan(run, skill_dirs):
    """Return (dest_dirs, wanted, plan) after checking for name clashes."""
    dest_dirs = sorted({expand(d) for _, d, _ in TARGETS})
    wanted = {d: set() for d in dest_dirs}
    plan = []

    def add(src, dest_dir):
        name = os.path.basename(src.rstrip(os.sep))
        if name in wanted[dest_dir]:
            sys.exit("ERROR: two sources named %s target %s; rename one" % (name, dest_dir))
        wanted[dest_dir].add(name)
        plan.append((src, os.path.join(dest_dir, name)))

    for pattern, dest_dir, readers in TARGETS:
        dest_dir = expand(dest_dir)
        if not harness_present(readers):
            run.say("skip", dest_dir, "%s not installed" % ", ".join(readers))
            continue
        for src in sources(pattern):
            add(src, dest_dir)

    for src in skill_dirs:
        for dest_dir, readers in SKILL_TARGETS:
            dest_dir = expand(dest_dir)
            if harness_present(readers):
                add(src, dest_dir)

    return dest_dirs, wanted, plan


def reconcile_manifest(managed, dest_dirs, plan, dry):
    """Capture legacy links, record new ones, drop entries that no longer hold."""
    for dest_dir in dest_dirs:
        if not os.path.isdir(dest_dir):
            continue
        for name in sorted(os.listdir(dest_dir)):
            path = os.path.join(dest_dir, name)
            if ours(path):
                managed[path] = link_target(path)

    if not dry:
        for src, dest in plan:
            if os.path.islink(dest):
                managed[dest] = os.path.realpath(src)

    for dest in list(managed):
        if not os.path.islink(dest) or link_target(dest) != os.path.realpath(managed[dest]):
            managed.pop(dest, None)

    if not dry:
        save_manifest(managed)


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="install.py", description=__doc__.strip().split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true",
                        help="show what would change, change nothing")
    parser.add_argument("--force", action="store_true",
                        help="also replace symlinks that point somewhere else")
    parser.add_argument("--skill", action="append", nargs="?", metavar="PATH",
                        const=PROMPT_SENTINEL,
                        help="also install skills from PATH (repeatable); "
                             "omit PATH to be prompted")
    return parser.parse_args(argv)


def main(argv=None):
    opts = parse_args(argv)
    run = Run(opts.dry_run, opts.force)
    if run.dry:
        print("dry run: nothing will change")

    skill_dirs = []
    for value in opts.skill or []:
        if value == PROMPT_SENTINEL:
            value = prompt_for_skill()
        found = find_skill_dirs(value)
        if not found:
            sys.exit("ERROR: no SKILL.md found under %s" % value)
        for path in found:
            if path not in skill_dirs:
                skill_dirs.append(path)

    dest_dirs, wanted, plan = build_plan(run, skill_dirs)
    for src, dest in plan:
        run.link(src, dest)

    managed = load_manifest()
    for dest_dir in dest_dirs:
        run.prune(dest_dir, wanted[dest_dir], managed)
    reconcile_manifest(managed, dest_dirs, plan, run.dry)

    if run.conflicts or run.errors:
        print("\n%d conflict(s), %d error(s); see the lines above." % (run.conflicts, run.errors))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
