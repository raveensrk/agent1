#!/usr/bin/env python3
"""Register this repo with pi, Claude Code and Codex. Dry-run by default.

Nothing is copied or linked: each harness loads the repo in place.

  pi      ~/.pi/agent/settings.json `packages` lists ~/repos/agent1, and
          package.json `pi` declares skills/, prompts/ and harness/extensions/.
  claude  ~/.claude/settings.json enables plugin agents@raveen-agents, a
          directory marketplace read live from .claude-plugin/.

Usage:
  ./install.py              show the plan
  ./install.py --apply      write it
  ./install.py --check      exit 1 when the harnesses drifted from the repo
  ./uninstall.py --apply    unregister
  ./install.py -h, --help   all flags

Links that the older symlink installer made into this repo are moved to the
Trash. The mechanics live in harness/install_lib.py, shared by every repo that
ships skills.
"""
import os
import sys

REPO = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(REPO, "harness"))
import install_lib  # noqa: E402

if __name__ == "__main__":
    sys.exit(install_lib.main(REPO, sys.argv[1:]))
