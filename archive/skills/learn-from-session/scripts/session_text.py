#!/usr/bin/env python3
"""Dump a Pi session transcript as plain text.

Reads the current session by default ($PI_SESSION_FILE, else the newest
*.jsonl for the working directory under ~/.pi/agent/sessions/). Prints user
messages, assistant text and tool calls. Skips thinking, tool results and
system prompts.

Usage:
  session_text.py [--path FILE] [--selftest]
"""
from __future__ import annotations

import argparse
import contextlib
import glob
import io
import json
import os
import sys

SESSIONS = os.path.expanduser("~/.pi/agent/sessions")


def session_file() -> str:
    env = os.environ.get("PI_SESSION_FILE")
    if env and os.path.exists(env):
        return env
    slug = "--" + os.getcwd().strip("/").replace("/", "-") + "--"
    files = glob.glob(os.path.join(SESSIONS, slug, "*.jsonl"))
    if not files:
        sys.exit(f"no transcript for {os.getcwd()} under {SESSIONS}/{slug}")
    return max(files, key=os.path.getmtime)


def one_line(text: str, limit: int = 300) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit] + " ..."


def dump(path: str) -> None:
    for line in open(path, encoding="utf-8"):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = entry.get("message")
        if not isinstance(msg, dict) or msg.get("role") in ("system", "toolResult"):
            continue
        role = msg.get("role")
        content = msg.get("content")
        if isinstance(content, str):
            if content.strip():
                print(f"[{role}] {content.strip()}")
            continue
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            kind = block.get("type")
            if kind == "text" and block.get("text", "").strip():
                print(f"[{role}] {block['text'].strip()}")
            elif kind == "toolCall":
                args = block.get("arguments") or {}
                detail = args.get("command") or args.get("path") or args.get("query") or ""
                print(f"[tool {block.get('name')}] {one_line(detail)}")


def selftest() -> None:
    import tempfile

    entries = [
        {"message": {"role": "system", "content": "secret"}},
        {"message": {"role": "user", "content": [{"type": "text", "text": "hello"}]}},
        {"message": {"role": "assistant", "content": [
            {"type": "thinking", "thinking": "hidden"},
            {"type": "text", "text": "world"},
            {"type": "toolCall", "name": "bash", "arguments": {"command": "ls"}},
        ]}},
        {"message": {"role": "toolResult", "content": [{"type": "text", "text": "noise"}]}},
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + "\n")
        path = fh.name
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        dump(path)
    os.unlink(path)
    text = out.getvalue()
    assert "[user] hello" in text, text
    assert "[assistant] world" in text, text
    assert "[tool bash] ls" in text, text
    assert "hidden" not in text and "secret" not in text and "noise" not in text, text
    print("selftest ok")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", help="transcript jsonl; default current session")
    parser.add_argument("--selftest", action="store_true")
    opts = parser.parse_args()
    if opts.selftest:
        selftest()
    else:
        dump(opts.path or session_file())
