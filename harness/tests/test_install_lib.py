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

# A stand-in for the claude CLI: logs each call and updates the registry files
# the real one keeps, so a second run reads the state the first one left.
FAKE_CLAUDE = r"""#!/usr/bin/env python3
import json, os, sys
plugins = os.path.join(os.environ["HOME"], ".claude", "plugins")
known_path = os.path.join(plugins, "known_marketplaces.json")
installed_path = os.path.join(plugins, "installed_plugins.json")
settings_path = os.path.join(os.environ["HOME"], ".claude", "settings.json")
def load(path, empty):
    try:
        return json.load(open(path))
    except FileNotFoundError:
        return empty
os.makedirs(plugins, exist_ok=True)
known, installed = load(known_path, {}), load(installed_path, {"plugins": {}})
settings = load(settings_path, {})
args = sys.argv[1:]
open(os.path.join(plugins, "calls.log"), "a").write(" ".join(args) + "\n")
if args[:3] == ["plugin", "marketplace", "add"]:
    name = json.load(open(os.path.join(args[3], ".claude-plugin", "marketplace.json")))["name"]
    known[name] = {"source": {"source": "directory", "path": args[3]}}
if args[:3] == ["plugin", "marketplace", "remove"]:
    known.pop(args[3], None)
if args[:2] == ["plugin", "install"]:
    installed["plugins"][args[2]] = [{"scope": "user"}]
    settings.setdefault("enabledPlugins", {})[args[2]] = True
if args[:2] == ["plugin", "uninstall"]:
    installed["plugins"].pop(args[2], None)
    settings.get("enabledPlugins", {}).pop(args[2], None)
json.dump(known, open(known_path, "w"))
json.dump(installed, open(installed_path, "w"))
json.dump(settings, open(settings_path, "w"))
"""
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

        self.cli = os.path.join(home, "claude")
        with open(self.cli, "w") as handle:
            handle.write(FAKE_CLAUDE)
        os.chmod(self.cli, 0o755)
        self.log = os.path.join(home, ".claude", "plugins", "calls.log")

        self.saved = {k: getattr(install_lib, k) for k in (
            "HOME", "TRASH", "PI_HOME", "PI_SETTINGS", "CLAUDE_HOME",
            "CLAUDE_SETTINGS", "CLAUDE_KNOWN", "CLAUDE_INSTALLED", "CODEX_HOME")}
        self.saved_env = {k: os.environ.get(k) for k in ("HOME", "CLAUDE_BIN")}
        install_lib.HOME = home
        install_lib.TRASH = os.path.join(home, ".Trash")
        install_lib.PI_HOME = os.path.join(home, ".pi")
        install_lib.PI_SETTINGS = self.pi
        install_lib.CLAUDE_HOME = os.path.join(home, ".claude")
        install_lib.CLAUDE_SETTINGS = self.claude
        install_lib.CLAUDE_KNOWN = os.path.join(home, ".claude", "plugins", "known_marketplaces.json")
        install_lib.CLAUDE_INSTALLED = os.path.join(home, ".claude", "plugins", "installed_plugins.json")
        install_lib.CODEX_HOME = os.path.join(home, ".codex")
        os.environ["HOME"] = home  # LEGACY_DIRS expand ~
        os.environ["CLAUDE_BIN"] = self.cli

    def tearDown(self):
        for key, value in self.saved.items():
            setattr(install_lib, key, value)
        for key, value in self.saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tmp.cleanup()

    @staticmethod
    def dump(path, data):
        with open(path, "w") as handle:
            json.dump(data, handle)

    @staticmethod
    def read(path):
        with open(path) as handle:
            return json.load(handle)

    def calls(self):
        try:
            with open(self.log) as handle:
                return handle.read().splitlines()
        except FileNotFoundError:
            return []

    def run_main(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = install_lib.main(self.repo, list(args))
        return code, out.getvalue()

    def test_dry_run_writes_nothing(self):
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertEqual(self.read(self.pi)["packages"], ["npm:other"])
        self.assertIn("update", out)
        self.assertIn("run       claude plugin install demo@demo-market", out)
        self.assertEqual(self.calls(), [])

    def test_apply_registers_and_keeps_other_keys(self):
        self.run_main("--apply")
        pi = self.read(self.pi)
        self.assertEqual(pi["packages"], ["npm:other", "~/repos/demo"])
        self.assertEqual(pi["theme"], "dark")
        self.assertEqual(self.calls(), [
            "plugin marketplace add %s" % self.repo,
            "plugin install demo@demo-market --scope user",
        ])

    def test_check_is_drift(self):
        self.assertEqual(self.run_main("--check")[0], 1)
        self.run_main("--apply")
        self.assertEqual(self.run_main("--check")[0], 0)

    def test_uninstall_reverses(self):
        self.run_main("--apply")
        self.run_main("--uninstall", "--apply")
        self.assertEqual(self.read(self.pi)["packages"], ["npm:other"])
        self.assertEqual(self.calls()[2:], [
            "plugin uninstall demo@demo-market --scope user",
            "plugin marketplace remove demo-market",
        ])

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
        self.assertEqual(self.calls(), [])

    def test_missing_cli_is_a_conflict_with_the_install_command(self):
        os.environ["CLAUDE_BIN"] = ""
        os.environ["PATH"], path = "/nonexistent", os.environ["PATH"]
        try:
            code, out = self.run_main("--apply")
        finally:
            os.environ["PATH"] = path
        self.assertEqual(code, 1)
        self.assertIn(install_lib.CLAUDE_INSTALL, out)

    def test_save_keeps_mode(self):
        os.chmod(self.pi, 0o600)
        self.run_main("--apply")
        self.assertEqual(os.stat(self.pi).st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
