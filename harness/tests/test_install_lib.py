#!/usr/bin/env python3
"""Checks for install_lib: register a repo with pi and Claude Code, no symlinks.

    python3 harness/tests/test_install_lib.py
    pytest harness/tests/test_install_lib.py

Every case runs against a throwaway home directory; the real one is never read.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

HARNESS = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, HARNESS)
import install_lib  # noqa: E402


class InstallLib(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        home = os.path.realpath(self.tmp.name)
        self.home = home

        # A fake home with pi and Claude installed, plus a repo that ships both.
        os.makedirs(os.path.join(home, ".pi", "agent"))
        os.makedirs(os.path.join(home, ".claude"))
        os.makedirs(os.path.join(home, ".Trash"))
        self.repo = os.path.join(home, "repos", "demo")
        os.makedirs(os.path.join(self.repo, ".claude-plugin"))
        self.dump(os.path.join(self.repo, "package.json"), {"pi": {"skills": ["skills"]}})
        self.dump(os.path.join(self.repo, ".claude-plugin", "marketplace.json"),
                  {"name": "demo-market", "plugins": [{"name": "demo", "source": "./"}]})
        self.pi = os.path.join(home, ".pi", "agent", "settings.json")
        self.claude = os.path.join(home, ".claude", "settings.json")
        self.dump(self.pi, {"theme": "dark", "packages": ["npm:other"]})
        self.dump(self.claude, {"model": "opus"})

        self.saved = {k: getattr(install_lib, k) for k in (
            "HOME", "TRASH", "PI_HOME", "PI_SETTINGS", "CLAUDE_HOME",
            "CLAUDE_SETTINGS", "CODEX_HOME")}
        install_lib.HOME = home
        install_lib.TRASH = os.path.join(home, ".Trash")
        install_lib.PI_HOME = os.path.join(home, ".pi")
        install_lib.PI_SETTINGS = self.pi
        install_lib.CLAUDE_HOME = os.path.join(home, ".claude")
        install_lib.CLAUDE_SETTINGS = self.claude
        install_lib.CODEX_HOME = os.path.join(home, ".codex")
        os.environ["HOME"] = home  # LEGACY_DIRS expand ~

    def tearDown(self):
        for key, value in self.saved.items():
            setattr(install_lib, key, value)
        os.environ["HOME"] = self.saved["HOME"]
        self.tmp.cleanup()

    @staticmethod
    def dump(path, data):
        with open(path, "w") as handle:
            json.dump(data, handle)

    @staticmethod
    def read(path):
        with open(path) as handle:
            return json.load(handle)

    def run_main(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = install_lib.main(self.repo, list(args))
        return code, out.getvalue()

    def test_dry_run_writes_nothing(self):
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertEqual(self.read(self.pi)["packages"], ["npm:other"])
        self.assertIn("update", out)

    def test_apply_registers_and_keeps_other_keys(self):
        self.run_main("--apply")
        pi = self.read(self.pi)
        self.assertEqual(pi["packages"], ["npm:other", "~/repos/demo"])
        self.assertEqual(pi["theme"], "dark")
        claude = self.read(self.claude)
        self.assertEqual(claude["model"], "opus")
        self.assertIs(claude["enabledPlugins"]["demo@demo-market"], True)
        self.assertEqual(claude["extraKnownMarketplaces"]["demo-market"]["source"],
                         {"source": "directory", "path": self.repo})

    def test_check_is_drift(self):
        self.assertEqual(self.run_main("--check")[0], 1)
        self.run_main("--apply")
        self.assertEqual(self.run_main("--check")[0], 0)

    def test_uninstall_reverses(self):
        self.run_main("--apply")
        self.run_main("--uninstall", "--apply")
        self.assertEqual(self.read(self.pi)["packages"], ["npm:other"])
        claude = self.read(self.claude)
        self.assertNotIn("demo-market", claude["extraKnownMarketplaces"])
        self.assertNotIn("demo@demo-market", claude["enabledPlugins"])

    def test_symlinked_settings_is_a_conflict(self):
        real = os.path.join(self.home, "real.json")
        os.rename(self.pi, real)
        os.symlink(real, self.pi)
        code, out = self.run_main("--apply")
        self.assertEqual(code, 1)
        self.assertIn("conflict", out)
        self.assertEqual(self.read(real)["packages"], ["npm:other"])

    def test_legacy_links_go_to_trash(self):
        skills = os.path.join(self.home, ".agents", "skills")
        os.makedirs(skills)
        os.makedirs(os.path.join(self.repo, "skills", "one"))
        os.symlink(os.path.join(self.repo, "skills", "one"), os.path.join(skills, "one"))
        os.makedirs(os.path.join(skills, "mine"))  # a real dir is never touched
        self.run_main("--apply")
        self.assertEqual(os.listdir(skills), ["mine"])
        self.assertTrue(os.path.islink(os.path.join(self.home, ".Trash", "one")))

    def test_missing_harness_is_skipped(self):
        install_lib.CLAUDE_HOME = os.path.join(self.home, "absent")
        code, out = self.run_main("--apply")
        self.assertEqual(code, 0)
        self.assertIn("claude not installed", out)
        self.assertEqual(self.read(self.claude), {"model": "opus"})


if __name__ == "__main__":
    unittest.main()
