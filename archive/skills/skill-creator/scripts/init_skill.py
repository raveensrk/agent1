#!/usr/bin/env python3
"""Scaffold a new agent skill directory in this repo.

Creates <skills>/<name>/SKILL.md with a TODO skeleton and any requested
resource directories. Refuses to overwrite an existing skill.

Usage:
  init_skill.py <skill-name> [--resources scripts,references,assets] [--path DIR]
  init_skill.py --selftest
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_NAME = 64
RESOURCES = ("scripts", "references", "assets")
TEMPLATE = """---
name: {name}
description: TODO: <what it does> - <what it produces>. Use when <trigger phrase>.
---

# {title}

TODO: <what this skill does, 1-2 sentences>.

## 1. <first step>

TODO: command first, then the one-line why.

## 2. Verify

TODO: what to run to prove it worked.

## 3. Report

TODO: what to show the user.
"""


def default_skills_dir() -> Path:
    """This repo's skills/ directory: <repo>/skills/skill-creator/scripts/init_skill.py."""
    return Path(__file__).resolve().parents[2]


def scaffold(name: str, path: Path, resources: list[str]) -> Path:
    if not NAME_RE.match(name) or len(name) > MAX_NAME:
        raise SystemExit(f"ERROR: {name!r} is not kebab-case (<= {MAX_NAME} chars)")
    dest = path / name
    if dest.exists():
        raise SystemExit(f"ERROR: {dest} already exists; edit it or pick another name")
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_text(
        TEMPLATE.format(name=name, title=name.replace("-", " ").capitalize())
    )
    for resource in resources:
        (dest / resource).mkdir()
    return dest


def selftest() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        dest = scaffold("demo-skill", root, ["scripts"])
        text = (dest / "SKILL.md").read_text()
        assert "name: demo-skill" in text
        assert (dest / "scripts").is_dir()
        try:
            scaffold("demo-skill", root, [])
        except SystemExit:
            pass
        else:
            raise AssertionError("existing skill was overwritten")
        for bad in ("Bad_Name", "UPPER", "-lead", "trail-", "a" * 65):
            try:
                scaffold(bad, root, [])
            except SystemExit:
                pass
            else:
                raise AssertionError(f"accepted bad name {bad!r}")
    print("selftest ok")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name", nargs="?", help="new skill name, kebab-case")
    parser.add_argument("--path", type=Path, default=default_skills_dir(),
                        help=f"parent directory (default: {default_skills_dir()})")
    parser.add_argument("--resources", default="",
                        help=f"comma-separated, any of: {', '.join(RESOURCES)}")
    parser.add_argument("--selftest", action="store_true", help="run the built-in check")
    args = parser.parse_args()

    if args.selftest:
        selftest()
        return 0
    if not args.name:
        parser.error("give a skill name")

    resources = [r.strip() for r in args.resources.split(",") if r.strip()]
    unknown = [r for r in resources if r not in RESOURCES]
    if unknown:
        parser.error(f"unknown resources: {', '.join(unknown)}; pick from {', '.join(RESOURCES)}")

    dest = scaffold(args.name, args.path.expanduser(), resources)
    print(f"created\t{dest}")
    print("next:")
    print("  1. write SKILL.md, replace the TODOs")
    print(f"  2. validate: ~/repos/agent1/skills/skill-creator/scripts/validate_skill.py {dest}")
    print(f"  3. install:  cd {default_skills_dir().parent} && ./install.py --check")
    print("  4. index:    add a one-line entry to skills/index.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
