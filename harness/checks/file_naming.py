#!/usr/bin/env python3
# harness-check: {"id": "file_naming", "applies": ["*"], "quadrant": "feedback/computational"}
"""Files and directories use snake_case - lowercase words joined by underscores.

common.md's Naming rule, decided. A basename passes when every character is a
lowercase letter, digit, underscore or dot, so no uppercase, no spaces, no
hyphens. Tool-recognized canonical names are exempt: README.md, LICENSE,
AGENTS.md, CLAUDE.md, SKILL.md, .gitignore, and the .claude-plugin directory
(Claude Code discovers the plugin manifest only under that exact name).

Scope: everything except the skills/ subtree of the repo that owns the file.
Skill directories are kebab-case because the Agent Skills format requires the
directory name to match the skill name (README.md: "Skill directories use
hyphens"), and skill_frontmatter.py already decides that pair.

Directories are validated as the ancestors of each file, up to the repo root.
A directory with no files in it is invisible here; git does not track empty
directories either.

    file_naming.py FILE...      (or paths on stdin)
"""
from __future__ import annotations

import os
import re
import sys

CANONICAL = {"README.md", "LICENSE", "AGENTS.md", "CLAUDE.md", "SKILL.md", ".gitignore"}

# tool-recognized directories whose name the tool owns, not this repo
CANONICAL_DIRS = {".claude-plugin"}

SKIP_DIRS = {"node_modules", "__pycache__", ".git"}

# lowercase letters, digits, underscores and dots; no uppercase, space or hyphen
SNAKE = re.compile(r"^[a-z0-9_.]+$")


def suggestion(name: str) -> str:
	"""The snake_case spelling: lowercase, runs of spaces and hyphens to underscores."""
	return re.sub(r"[\s-]+", "_", name.strip()).lower()


def repo_root(path: str) -> str | None:
	"""The nearest ancestor that is a repo root: it holds .git, or a harness/ dir."""
	current = os.path.dirname(os.path.realpath(path))
	while True:
		if os.path.isdir(os.path.join(current, ".git")) or os.path.isdir(
			os.path.join(current, "harness")
		):
			return current
		parent = os.path.dirname(current)
		if parent == current:
			return None
		current = parent


def check(path: str) -> list[str]:
	findings = []
	root = repo_root(path)
	if root is None:
		return findings
	rel = os.path.relpath(os.path.realpath(path), root)
	parts = rel.split(os.sep)
	# the whole skills/ subtree follows the Agent Skills naming, not this rule
	if parts[0] == "skills":
		return findings
	dirs, name = parts[:-1], parts[-1]
	for directory in dirs:
		if directory in SKIP_DIRS or directory in CANONICAL_DIRS or SNAKE.match(directory):
			continue
		findings.append(
			f"{path}: directory '{directory}' is not snake_case - "
			f"rename it: git mv {os.path.join(root, *dirs)} {suggestion(directory)}"
		)
		break
	if name in CANONICAL or SNAKE.match(name):
		return findings
	findings.append(
		f"{path}: file '{name}' is not snake_case - "
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
