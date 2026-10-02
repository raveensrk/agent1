#!/usr/bin/env python3
"""Remove the skills and commands that install.py installed.

By default this trusts install.py's manifest, so it removes exactly the links
install.py created and never touches a symlink you made by hand.

Usage:
  ./uninstall.py             remove everything install.py installed
  ./uninstall.py --dry-run   show what would be removed, remove nothing
  ./uninstall.py --scan      also remove hand-made skill links (target holds
                             SKILL.md) from the harness directories
  ./uninstall.py --yes       skip the confirmation prompt

Safety:
  - Never deletes a real file or directory; only symlinks.
  - Skips a manifest entry whose symlink now points somewhere else, and says so.
"""
import argparse
import os
import sys

import install


def looks_like_skill(path):
    return os.path.isdir(path) and os.path.isfile(os.path.join(path, "SKILL.md"))


def looks_like_command(path):
    return os.path.isfile(path) and path.endswith(".md")


def dest_dirs():
    return sorted({install.expand(d) for _, d, _ in install.TARGETS})


def collect(scan):
    """dest -> reason, for everything this run should remove."""
    targets = {}
    skipped = []

    for dest, source in install.load_manifest().items():
        if not os.path.islink(dest):
            continue
        if install.link_target(dest) == os.path.realpath(source):
            targets[dest] = "installed by install.py"
        else:
            skipped.append((dest, os.readlink(dest)))

    if scan:
        for directory in dest_dirs():
            if not os.path.isdir(directory):
                continue
            for name in sorted(os.listdir(directory)):
                path = os.path.join(directory, name)
                if not os.path.islink(path) or path in targets:
                    continue
                target = install.link_target(path)
                if looks_like_skill(target) or looks_like_command(target):
                    targets[path] = "found by --scan"

    return targets, skipped


def confirm(count):
    if not sys.stdin.isatty():
        print("nothing removed: pass --yes to confirm without a terminal")
        return False
    try:
        answer = input("Remove %d link(s)? [y/N] " % count).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in ("y", "yes")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="uninstall.py", description=__doc__.strip().split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true",
                        help="show what would be removed, remove nothing")
    parser.add_argument("--scan", action="store_true",
                        help="also remove hand-made skill links from harness dirs")
    parser.add_argument("--yes", action="store_true",
                        help="skip the confirmation prompt")
    opts = parser.parse_args(argv)

    run = install.Run(opts.dry_run, force=True)
    if run.dry:
        print("dry run: nothing will change")

    targets, skipped = collect(opts.scan)
    for dest, current in skipped:
        run.say("skip", dest, "points to %s, not the manifest source" % current)

    if not targets:
        print("nothing to remove")
        return 0

    for dest, reason in sorted(targets.items()):
        run.say("remove", dest, reason)

    if not opts.dry_run and not opts.yes and not confirm(len(targets)):
        print("aborted; nothing removed")
        return 0
    if opts.dry_run:
        return 0

    managed = install.load_manifest()
    for dest in sorted(targets):
        run.apply(os.unlink, dest)
        managed.pop(dest, None)
    for dest in list(managed):
        if not os.path.islink(dest) or \
                install.link_target(dest) != os.path.realpath(managed[dest]):
            managed.pop(dest, None)
    install.save_manifest(managed)

    print("removed %d link(s)" % len(targets))
    return 1 if run.errors else 0


if __name__ == "__main__":
    sys.exit(main())
