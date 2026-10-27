"""Shared helpers for agent-usage-report adapters.

Every adapter yields two kinds of record:

- ``kind="user"``      one human request, with ``text`` for correction detection.
- ``kind="assistant"`` one model turn, with token counts and (optional) cost.

Token fields are normalised so that they always add up:

    total = input + cache_read + cache_write + output

``input`` is *uncached* input. Harnesses that fold cached tokens into their
input counter subtract them in their own adapter.
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path

FIELDS = (
    "kind",
    "harness",
    "session_id",
    "project",
    "timestamp",
    "provider",
    "model",
    "input",
    "cache_read",
    "cache_write",
    "output",
    "reasoning",
    "total",
    "cost",
    "cost_source",
    "stop_reason",
    "tool_calls",
    "tool_errors",
    "thinking_level",
    "context_window",
    "text",
    "tools",
)


def make(**kw):
    """Build a normalised record, filling in zeroes and deriving total."""
    rec = dict.fromkeys(FIELDS)
    rec.update(
        {
            "kind": "assistant",
            "input": 0,
            "cache_read": 0,
            "cache_write": 0,
            "output": 0,
            "reasoning": 0,
            "total": 0,
            "tool_calls": 0,
            "tool_errors": 0,
            "text": "",
        }
    )
    rec.update(kw)
    if not rec.get("total"):
        rec["total"] = (
            int(rec.get("input") or 0)
            + int(rec.get("cache_read") or 0)
            + int(rec.get("cache_write") or 0)
            + int(rec.get("output") or 0)
        )
    return rec


def parse_ts(value):
    """ISO-8601 (with or without Z) or epoch seconds/ms to epoch seconds."""
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        # Heuristic: milliseconds vs seconds.
        return float(value) / 1000.0 if float(value) > 1e11 else float(value)
    text = str(value).strip()
    if text.isdigit():
        return float(text) / 1000.0 if len(text) > 11 else float(text)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.datetime.fromisoformat(text)
    except ValueError:
        return 0.0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.timestamp()


def text_of(content):
    """Flatten a message content value (str or Anthropic-style block list)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text" and item.get("text"):
                    parts.append(str(item["text"]))
                elif "content" in item and isinstance(item["content"], str):
                    parts.append(item["content"])
        return "\n".join(parts)
    if isinstance(content, dict):
        return text_of(content.get("content"))
    return ""


def home():
    return Path(os.path.expanduser("~"))


def expand(path):
    """Expand ~ and environment variables in a config path."""
    return Path(os.path.expandvars(os.path.expanduser(str(path))))
