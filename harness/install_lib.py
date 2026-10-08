"""Register a repo with every agent harness, without symlinks.

A repo that ships skills, prompts, commands or hooks is loaded in place, from
its checkout, through each harness's own load path:

  pi      ~/.pi/agent/settings.json `packages` lists the repo; its package.json
          `pi` key declares the skills, prompts and extensions.
  claude  ~/.claude/settings.json registers the repo's .claude-plugin
          marketplace as a directory source and enables its plugins. Claude
          reads a directory plugin live from the checkout; no update step.
  codex   not wired yet; skipped with a note while ~/.codex exists.

A harness whose home directory is missing is skipped. `git pull` in the repo
updates every harness on its next start.

Only the keys this repo owns are touched; every other key in a settings file,
including what the harness writes at runtime, is left alone. A settings file
that is still a symlink is never written through - it belongs to the dotfiles
installer.

Older installers linked skills and commands into the harness directories.
Those links, when they point into the repo, are moved to the Trash.

Usage from a repo's install.py:

    sys.path.insert(0, os.path.expanduser("~/repos/agent1/harness"))
    import install_lib
    sys.exit(install_lib.main(REPO, sys.argv[1:]))
"""
from __future__ import annotations

import argparse
import json
import os
import time

HOME = os.path.expanduser("~")
TRASH = os.path.join(HOME, ".Trash")

PI_HOME = os.path.join(HOME, ".pi")
PI_SETTINGS = os.path.join(HOME, ".pi", "agent", "settings.json")
CLAUDE_HOME = os.path.join(HOME, ".claude")
CLAUDE_SETTINGS = os.path.join(HOME, ".claude", "settings.json")
CODEX_HOME = os.path.join(HOME, ".codex")

# Directories older installers filled with links back into a repo.
LEGACY_DIRS = [
    "~/.agents/skills",
    "~/.claude/skills",
    "~/.claude/commands",
    "~/.codex/skills",
    "~/.pi/agent/prompts",
]


def tilde(path: str) -> str:
    """~/repos/agent1 for /Users/me/repos/agent1; Pi settings use this form."""
    return "~" + path[len(HOME):] if path.startswith(HOME + os.sep) else path


def load(path: str) -> dict:
    try:
        with open(path) as handle:
            return json.load(handle)
    except FileNotFoundError:
        return {}


def save(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


class Run:
    """Collects actions, prints them, and writes only when applying."""

    def __init__(self, apply: bool):
        self.apply, self.changes, self.conflicts = apply, 0, 0

    def say(self, action: str, path: str, note: str = "") -> None:
        print("%-9s %s%s" % (action, tilde(path), "  " + note if note else ""))

    def write(self, path: str, data: dict, note: str) -> None:
        # A symlinked settings file is the dotfiles installer's to replace.
        if os.path.islink(path):
            self.conflicts += 1
            return self.say("conflict", path,
                            "symlink; run ~/dot/script/install.py --apply first")
        self.changes += 1
        self.say("update", path, note)
        if self.apply:
            save(path, data)

    def trash(self, path: str, note: str) -> None:
        self.changes += 1
        self.say("trash", path, note)
        if not self.apply:
            return
        dest = os.path.join(TRASH, os.path.basename(path))
        if os.path.lexists(dest):
            dest += time.strftime(" %H.%M.%S")
        os.rename(path, dest)


def pi_spec(entry) -> str:
    """A `packages` entry is a source string or an object with `source`."""
    return entry.get("source", "") if isinstance(entry, dict) else entry


def pi(run: Run, repo: str, remove: bool) -> None:
    if not os.path.isdir(PI_HOME):
        return run.say("skip", PI_SETTINGS, "pi not installed")
    if "pi" not in load(os.path.join(repo, "package.json")):
        return run.say("skip", PI_SETTINGS, "repo has no package.json `pi` key")

    settings = load(PI_SETTINGS)
    packages = settings.get("packages", [])
    source = tilde(repo)
    present = [p for p in packages if os.path.expanduser(pi_spec(p)) == repo]

    if remove and present:
        settings["packages"] = [p for p in packages if p not in present]
        return run.write(PI_SETTINGS, settings, "packages -= %s" % source)
    if remove or present:
        return run.say("ok", PI_SETTINGS, "packages: %s" % source)
    settings["packages"] = packages + [source]
    run.write(PI_SETTINGS, settings, "packages += %s" % source)


def claude(run: Run, repo: str, remove: bool) -> None:
    if not os.path.isdir(CLAUDE_HOME):
        return run.say("skip", CLAUDE_SETTINGS, "claude not installed")
    market = load(os.path.join(repo, ".claude-plugin", "marketplace.json"))
    if not market.get("name"):
        return run.say("skip", CLAUDE_SETTINGS, "repo has no .claude-plugin/marketplace.json")

    name = market["name"]
    plugins = ["%s@%s" % (p["name"], name) for p in market.get("plugins", [])]
    source = {"source": {"source": "directory", "path": repo}}
    settings = load(CLAUDE_SETTINGS)
    known = settings.setdefault("extraKnownMarketplaces", {})
    enabled = settings.setdefault("enabledPlugins", {})

    if remove:
        if name not in known and not any(p in enabled for p in plugins):
            return run.say("ok", CLAUDE_SETTINGS, "marketplace %s absent" % name)
        known.pop(name, None)
        for plugin in plugins:
            enabled.pop(plugin, None)
        return run.write(CLAUDE_SETTINGS, settings, "removed marketplace %s" % name)

    if known.get(name) == source and all(enabled.get(p) is True for p in plugins):
        return run.say("ok", CLAUDE_SETTINGS, "plugins: %s" % ", ".join(plugins))
    known[name] = source
    for plugin in plugins:
        enabled[plugin] = True
    run.write(CLAUDE_SETTINGS, settings, "enabled %s" % ", ".join(plugins))


def codex(run: Run, repo: str, remove: bool) -> None:
    if not os.path.isdir(CODEX_HOME):
        return run.say("skip", CODEX_HOME, "codex not installed")
    run.say("skip", CODEX_HOME, "codex wiring not written yet")


def legacy(run: Run, repo: str) -> None:
    """Trash links an older installer made into this repo."""
    for folder in LEGACY_DIRS:
        folder = os.path.expanduser(folder)
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            if not os.path.islink(path):
                continue
            target = os.path.realpath(path)
            if target == repo or target.startswith(repo + os.sep):
                run.trash(path, "legacy link -> %s" % tilde(target))


def main(repo: str, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Register %s with pi, Claude Code and Codex (dry-run by default)."
                    % tilde(repo))
    parser.add_argument("-a", "--apply", action="store_true", help="make the changes")
    parser.add_argument("-u", "--uninstall", action="store_true",
                        help="unregister the repo instead")
    parser.add_argument("-c", "--check", action="store_true",
                        help="exit 1 when anything would change (drift)")
    opts = parser.parse_args(argv)

    repo = os.path.realpath(repo)
    run = Run(opts.apply and not opts.check)
    if not run.apply:
        print("dry run: nothing will change; pass --apply to write")

    for step in (pi, claude, codex):
        step(run, repo, opts.uninstall)
    legacy(run, repo)

    if run.conflicts:
        print("\n%d conflict(s); see the lines above." % run.conflicts)
        return 1
    if opts.check and run.changes:
        return 1
    if run.apply and run.changes:
        print("\nrestart pi and Claude Code to load the changes")
    return 0
