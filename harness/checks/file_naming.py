#!/usr/bin/env python3
# harness-check: {"id": "file_naming", "applies": ["*"], "quadrant": "feedback/computational"}
"""Files and directories use snake_case - lowercase words joined by underscores.

common.md's Naming rule, decided. A basename passes when every character is a
lowercase letter, digit, underscore or dot, so no uppercase, no spaces, no
hyphens.

Exempt, in CANONICAL: a name a tool reads by its exact spelling (Makefile,
Cargo.toml, Info.plist), the agent files (AGENTS.md, CLAUDE.md, SKILL.md), and
repo docs of the README and LICENSE kind (CHANGELOG.md, COPYING). A name joins
when a rename would break a tool or the convention, not because a repo holds
one. The .claude-plugin directory is exempt the same way: Claude Code discovers
the plugin manifest only under that exact name.

Junk gets a delete, not a rename: a Windows Zone.Identifier copy
(`x.sv:Zone - Copy.Identifier`, whose snake_case spelling still holds the
colon) and Finder's .DS_Store. The steer is `git rm` when git tracks the file
and `trash` when it does not; for .DS_Store, which Finder writes again, also a
line in the repo's .gitignore.

Scope: everything except the skills/ subtree of the repo that owns the file.
Skill directories are kebab-case because the Agent Skills format requires the
directory name to match the skill name (README.md: "Skill directories use
hyphens"), and skill_frontmatter.py already decides that pair. Anywhere else, a
directory holding a SKILL.md may carry a kebab-case name for the same reason;
the files inside it are still checked. Pi package prompt templates under
prompts/ may use hyphens: Pi turns the filename into the slash-command name.

Directories are validated as the ancestors of each file, up to the repo root.
A directory with no files in it is invisible here; git does not track empty
directories either.

This machine's exceptions live in the private repo, like nested_git_repo.py's:
~/repos/agent2/harness/data/file_naming_allow.txt holds one fnmatch glob per
line, relative to ~/repos with the repo name first (`notes/*`), because a
folder name such as requirements/ is fine in one repo and a finding in another.

    file_naming.py FILE...      (or paths on stdin)
"""
from __future__ import annotations

import fnmatch
import functools
import os
import re
import shlex
import subprocess
import sys

REPOS = os.path.expanduser("~/repos")
ALLOW = os.path.join(REPOS, "agent2", "harness", "data", "file_naming_allow.txt")
PATTERNS: dict[str, list[str]] = {}

CANONICAL = {
	"README.md", "LICENSE", "AGENTS.md", "CLAUDE.md", "SKILL.md", ".gitignore",
	# a build or package tool reads these by exact spelling, and GNU make
	# recommends Makefile over makefile: 64 findings in ~/repos on 2026-10-10
	"Makefile", "CMakeLists.txt", "package-lock.json", "Cargo.toml", "Cargo.lock",
	"Info.plist", "BUILD.bazel", ".markdownlint-cli2.jsonc",
	# repo docs of the README and LICENSE kind: 11 findings on 2026-10-10
	"README.txt", "CHANGELOG.md", "COPYING", "LICENSE.txt",
}

# tool-recognized directories whose name the tool owns, not this repo
CANONICAL_DIRS = {".claude-plugin"}

SKIP_DIRS = {"node_modules", "__pycache__", ".git"}

# lowercase letters, digits, underscores and dots; no uppercase, space or hyphen
SNAKE = re.compile(r"^[a-z0-9_.]+$")

# an Agent Skills name: lowercase words joined by single hyphens, page-precheck
KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Windows keeps a download's origin in the x.sv:Zone.Identifier stream; a copy
# off NTFS turns it into a file, and Explorer's copy of that file adds " - Copy"
# or " - Copy (2)". 276 in ~/repos on 2026-10-10, all tracked.
ZONE = re.compile(r":Zone(?: - Copy(?: \(\d+\))?)?\.Identifier$")

# Finder's per-folder view state; Finder writes it again after a delete
FINDER = ".DS_Store"


def suggestion(name: str) -> str:
	"""The snake_case spelling: lowercase, runs of spaces and hyphens to underscores."""
	return re.sub(r"[\s-]+", "_", name.strip()).lower()


def allowed(path: str) -> bool:
	"""PATH sits under a glob in ALLOW, matched relative to REPOS; `#` lines are comments."""
	rel = os.path.relpath(os.path.realpath(path), os.path.realpath(REPOS))
	if rel.startswith(".."):
		return False
	# read once per allowlist path; tests point ALLOW at a fixture after import
	if ALLOW not in PATTERNS:
		try:
			with open(ALLOW, encoding="utf-8") as fh:
				lines = fh.read().splitlines()
		except OSError:
			lines = []
		PATTERNS[ALLOW] = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
	return any(fnmatch.fnmatch(rel, pattern) for pattern in PATTERNS[ALLOW])


def repo_root(path: str) -> str | None:
	"""The nearest ancestor that is a repo root: it holds .git, or a harness/ dir.

	A linked worktree's .git is a file, so a file counts too; otherwise the walk
	climbs into the main repo and judges the worktree folder's tool-chosen name.
	"""
	current = os.path.dirname(os.path.realpath(path))
	while True:
		if os.path.exists(os.path.join(current, ".git")) or os.path.isdir(
			os.path.join(current, "harness")
		):
			return current
		parent = os.path.dirname(current)
		if parent == current:
			return None
		current = parent


@functools.cache
def tracked(root: str) -> frozenset[str]:
	"""Paths git tracks under ROOT, relative to it; empty when ROOT is no git repo.

	One git call per repo, and only once a junk file turns up there.
	"""
	try:
		proc = subprocess.run(
			["git", "-C", root, "ls-files", "-z"], capture_output=True, text=True, timeout=60
		)
	except (OSError, subprocess.SubprocessError):
		return frozenset()
	return frozenset(proc.stdout.split("\0")) if proc.returncode == 0 else frozenset()


def junk(path: str, root: str, rel: str, name: str) -> str:
	"""The delete steer for junk: git rm when tracked, trash when not.

	Both forms work from any cwd: git -C names the repo, and the paths are
	absolute and quoted, since a Zone name holds a colon and spaces.
	"""
	target = os.path.join(root, rel)
	delete = f"trash {shlex.quote(target)}"
	if rel in tracked(root):
		delete = f"git -C {shlex.quote(root)} rm -- {shlex.quote(target)}"
	if name == FINDER:
		# the leading newline keeps a .gitignore with no final newline intact
		ignore = shlex.quote(os.path.join(root, ".gitignore"))
		return (
			f"{path}:1: file '{name}' is macOS Finder metadata, not content - "
			f"delete and ignore it: {delete} && printf '\\n{FINDER}\\n' >> {ignore}"
		)
	return (
		f"{path}:1: file '{name}' is a Windows Zone.Identifier leftover, not content - "
		f"delete it, do not rename it: {delete}"
	)


def check(path: str) -> list[str]:
	findings = []
	# a deleted file has no name left to fix, and git mv on it would fail
	if not os.path.lexists(path):
		return findings
	root = repo_root(path)
	if root is None:
		return findings
	rel = os.path.relpath(os.path.realpath(path), root)
	parts = rel.split(os.sep)
	# the whole skills/ subtree follows the Agent Skills naming, not this rule
	if parts[0] == "skills" or allowed(path):
		return findings
	dirs, name = parts[:-1], parts[-1]
	for index, directory in enumerate(dirs):
		if directory in SKIP_DIRS or directory in CANONICAL_DIRS or SNAKE.match(directory):
			continue
		# a skill's directory carries the skill's kebab-case name, wherever it lives
		if KEBAB.match(directory) and os.path.isfile(os.path.join(root, *dirs[: index + 1], "SKILL.md")):
			continue
		# rename the offending directory in place, not the file's own directory
		parent = os.path.join(root, *dirs[:index])
		findings.append(
			f"{path}:1: directory '{directory}' is not snake_case - "
			f"rename it: git mv {os.path.join(parent, directory)} {os.path.join(parent, suggestion(directory))}"
		)
		break
	# Pi package prompt filenames become slash commands, such as /estimate-cost.
	if dirs == ["prompts"] and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*\.md", name):
		return findings
	if name in CANONICAL or SNAKE.match(name):
		return findings
	# junk is deleted, not renamed: a rename keeps it, and Zone's keeps the colon
	if name == FINDER or ZONE.search(name):
		findings.append(junk(path, root, rel, name))
		return findings
	findings.append(
		f"{path}:1: file '{name}' is not snake_case - "
		f"rename it: git mv {path} {os.path.join(root, *dirs, suggestion(name))}"
	)
	return findings


def main() -> int:
	paths = sys.argv[1:] or [line.strip() for line in sys.stdin if line.strip()]
	for path in paths:
		for finding in check(path):
			print(finding)
	return 0


if __name__ == "__main__":
	sys.exit(main())
