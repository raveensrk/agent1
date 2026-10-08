#!/usr/bin/env python3
"""Unregister this repo from pi, Claude Code and Codex. Dry-run by default.

Usage:
  ./uninstall.py            show the plan
  ./uninstall.py --apply    write it
  ./uninstall.py -h, --help all flags

The reverse of install.py; see harness/install_lib.py.
"""
import os
import sys

REPO = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(REPO, "harness"))
import install_lib  # noqa: E402

if __name__ == "__main__":
    sys.exit(install_lib.main(REPO, ["--uninstall"] + sys.argv[1:]))
