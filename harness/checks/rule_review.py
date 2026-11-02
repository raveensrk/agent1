#!/usr/bin/env python3
# harness-check: {"id": "rule_review", "applies": ["rules/*.md"], "quadrant": "feedback/computational"}
"""Every rule file under rules/ records its last review, at most 30 days ago.

A rule file opens with YAML frontmatter carrying last_reviewed: YYYY-MM-DD. The
date means the user reviewed the file, so a finding is not silenced by moving
the date alone: review the rule first. An edit is not a review.

The dispatcher runs this on a full lint.py run and on files a session touched,
so a stale file nobody touches surfaces only on a full run.

    rule_review.py FILE...      (or paths on stdin)
"""
from __future__ import annotations

import datetime
import re
import sys

MAX_AGE_DAYS = 30
BLOCK = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|$)", re.S)
FIELD = re.compile(r"^last_reviewed:\s*(.*?)\s*$", re.M)
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def finding(path: str, today: datetime.date) -> str | None:
    """The problem with one file's review date, or None when it is current."""
    add = f"add --- / last_reviewed: {today} / --- at line 1, after the user reviews it"
    with open(path, encoding="utf-8") as reader:
        block = BLOCK.match(reader.read())
    if not block:
        return f"no YAML frontmatter - fix: {add}"
    field = FIELD.search(block.group(1))
    if not field:
        return f"frontmatter has no last_reviewed - fix: {add}"
    fix = f"fix: have the user review it, then set last_reviewed: {today}"
    value = field.group(1).strip("\"'")
    try:
        if not DATE.fullmatch(value):
            raise ValueError
        reviewed = datetime.date.fromisoformat(value)
    except ValueError:
        return f"last_reviewed {value!r} is not a YYYY-MM-DD date - {fix}"
    age = (today - reviewed).days
    if age < 0:
        return f"last_reviewed {value} is in the future - {fix}"
    if age > MAX_AGE_DAYS:
        return f"last reviewed {age} days ago, limit is {MAX_AGE_DAYS} - {fix}"
    return None


def main() -> int:
    files = sys.argv[1:]
    if not files and not sys.stdin.isatty():
        files = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]

    today = datetime.date.today()
    for path in files:
        try:
            problem = finding(path, today)
        except (OSError, UnicodeDecodeError) as err:
            print(f"{path}:1: cannot read: {err}", file=sys.stderr)
            return 2
        if problem:
            print(f"{path}:1: {problem}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
