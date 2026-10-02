#!/usr/bin/env python3
"""Validate agent skill directories against this repo's house rules.

Checks: SKILL.md present, frontmatter present, kebab-case `name:` matching
the directory, description within limits with a "Use when" clause, and every
relative link in the body resolving.

Usage:
  validate_skill.py SKILL_DIR [SKILL_DIR ...]
  validate_skill.py --selftest
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\]\((?!https?://|mailto:|#)([^)\s]+)\)")
MAX_NAME = 64
MAX_DESCRIPTION = 1024


def split_frontmatter(text: str) -> tuple[str | None, str]:
    """Return (frontmatter, body). Frontmatter is None when absent."""
    if not text.startswith("---\n"):
        return None, text
    match = re.match(r"^---\n(.*?)\n---[ \t]*(?:\n|$)", text, re.DOTALL)
    if not match:
        return None, text
    return match.group(1), text[match.end():]


def field(frontmatter: str, key: str) -> str | None:
    # ponytail: line-based parse; handles plain and folded scalars, not flow maps
    match = re.search(
        rf"^{key}:[ \t]*(.*?)(?=^[A-Za-z][A-Za-z0-9_-]*:|\Z)",
        frontmatter + "\n",
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        return None
    lines = [line.strip() for line in match.group(1).splitlines()]
    if lines and re.fullmatch(r"[>|][+-]?", lines[0]):
        lines = lines[1:]
    value = " ".join(line for line in lines if line)
    return value.strip("\"'") if value else None


def validate(skill_dir: Path) -> list[str]:
    """Return a list of errors; empty means valid."""
    errors: list[str] = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_dir.is_dir():
        return [f"not a directory: {skill_dir}"]
    if not skill_md.is_file():
        return [f"SKILL.md not found in {skill_dir}"]

    frontmatter, body = split_frontmatter(skill_md.read_text())
    if frontmatter is None:
        return [f"{skill_md}: missing or malformed frontmatter"]

    name = field(frontmatter, "name")
    dir_name = skill_dir.resolve().name
    if not name:
        errors.append("name: missing")
    else:
        if not NAME_RE.match(name):
            errors.append(f"name: {name!r} is not kebab-case")
        if len(name) > MAX_NAME:
            errors.append(f"name: {len(name)} chars, max {MAX_NAME}")
        if name != dir_name:
            errors.append(f"name: {name!r} != directory {dir_name!r}")

    description = field(frontmatter, "description")
    if not description:
        errors.append("description: missing")
    else:
        if len(description) > MAX_DESCRIPTION:
            errors.append(f"description: {len(description)} chars, max {MAX_DESCRIPTION}")
        if "use when" not in description.lower():
            errors.append('description: add a "Use when <trigger>" clause')

    for target in LINK_RE.findall(body):
        relative = target.split("#", 1)[0]
        if not relative or "<" in relative:
            continue
        # A `~` link is how this repo points at another repo's file (common.md's
        # Markdown rule), so resolve it against home, not against the skill dir.
        if relative.startswith("~"):
            exists = Path(relative).expanduser().exists()
        else:
            exists = (skill_dir / relative).resolve().exists()
        if not exists:
            errors.append(f"link: {target} does not resolve")

    return errors


def selftest() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "install.py").write_text("")
        good = root / "demo-skill"
        good.mkdir()
        (good / "SKILL.md").write_text(
            "---\n"
            "name: demo-skill\n"
            "description: Demos things - one output. Use when the user says demo.\n"
            "---\n\n"
            "# Demo\n\nSee [install.py](../install.py).\n"
        )
        assert validate(good) == [], validate(good)

        homed = root / "homed-skill"
        homed.mkdir()
        (homed / "SKILL.md").write_text(
            "---\n"
            "name: homed-skill\n"
            "description: Links home - one output. Use when the user says homed.\n"
            "---\n\n"
            "See [home](~/) and [gone](~/definitely-not-here-xyz.md).\n"
        )
        errors = validate(homed)
        assert len(errors) == 1 and "definitely-not-here-xyz" in errors[0], errors

        bad = root / "bad-skill"
        bad.mkdir()
        (bad / "SKILL.md").write_text(
            "---\nname: bad_skill\ndescription: No trigger clause.\n---\n\n[x](./missing.md)\n"
        )
        errors = validate(bad)
        assert len(errors) == 4, errors

        plain = root / "plain-skill"
        plain.mkdir()
        (plain / "SKILL.md").write_text("# No frontmatter\n")
        assert validate(plain) == [f"{plain / 'SKILL.md'}: missing or malformed frontmatter"]

        folded = root / "folded-skill"
        folded.mkdir()
        (folded / "SKILL.md").write_text(
            "---\n"
            "name: folded-skill\n"
            "metadata:\n"
            "  scope: global\n"
            "description: >-\n"
            "  Folded things - one output.\n"
            "  Use when the user says folded.\n"
            "---\n\n# Folded\n"
        )
        assert validate(folded) == [], validate(folded)
    print("selftest ok")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dirs", nargs="*", type=Path, help="skill directories to validate")
    parser.add_argument("--selftest", action="store_true", help="run the built-in check")
    args = parser.parse_args()

    if args.selftest:
        selftest()
        return 0
    if not args.dirs:
        parser.error("give at least one skill directory")

    failed = False
    for skill_dir in args.dirs:
        errors = validate(skill_dir)
        if errors:
            failed = True
            for error in errors:
                print(f"FAIL\t{skill_dir}\t{error}")
        else:
            print(f"ok\t{skill_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
