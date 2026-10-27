"""Claude Code adapter.

Logs: ``~/.claude/projects/<encoded-cwd>/<session-uuid>.jsonl``

Relevant line types:

- ``assistant`` with ``message.usage`` (``input_tokens``,
  ``cache_creation_input_tokens``, ``cache_read_input_tokens``,
  ``output_tokens``) and ``message.model``. Anthropic semantics: input_tokens
  excludes cache tokens, so total is the plain sum.
- ``user`` with ``origin.kind == "human"`` is a real human request. Tool
  results are also ``user`` lines, but their content holds ``tool_result``
  blocks, some flagged ``is_error``.

Claude Code logs no dollars, so cost is computed by pricing.py from
models.dev rates.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .util import expand, make, parse_ts, text_of

NAME = "claude_code"
LABEL = "Claude Code"

_INTERESTING = ('"usage"', '"type":"user"', '"is_error"')


def root():
    override = os.environ.get("AGENT_REPORT_CLAUDE_DIR")
    if override:
        return expand(override)
    return Path.home() / ".claude" / "projects"


def discover():
    base = root()
    return [base] if base.exists() else []


def available():
    return bool(discover())


def records():
    for base in discover():
        for path in sorted(base.rglob("*.jsonl")):
            for rec in _session(path, base):
                yield rec


def _project_of(path, base):
    try:
        return "-" + str(path.relative_to(base).parent).lstrip("./")
    except ValueError:
        return ""


def _session(path, base):
    project = _project_of(path, base)

    last = None
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not any(token in line for token in _INTERESTING):
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue

            etype = event.get("type")
            message = event.get("message") or {}
            session_id = event.get("sessionId") or path.stem
            cwd = event.get("cwd") or project
            timestamp = parse_ts(event.get("timestamp"))

            if etype == "user":
                origin = event.get("origin") or {}
                content = message.get("content")
                human = origin.get("kind") == "human" or isinstance(content, str)
                if human:
                    yield make(
                        kind="user", harness=NAME, session_id=session_id,
                        project=cwd, timestamp=timestamp, text=text_of(content),
                    )
                elif isinstance(content, list) and last is not None:
                    for block in content:
                        if isinstance(block, dict) and block.get("is_error"):
                            last["tool_errors"] = last.get("tool_errors", 0) + 1
            elif etype == "assistant":
                usage = message.get("usage")
                if not usage:
                    continue
                cache_write = int(
                    usage.get("cache_creation_input_tokens")
                    or usage.get("cache_creation_tokens") or 0
                )
                tool_calls = 0
                tools = {}
                for block in message.get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_calls += 1
                        name = str(block.get("name") or "tool")
                        tools[name] = tools.get(name, 0) + 1
                record = make(
                    kind="assistant", harness=NAME, session_id=session_id,
                    project=cwd, timestamp=timestamp,
                    provider="anthropic",
                    model=message.get("model") or "unknown",
                    input=int(usage.get("input_tokens") or 0),
                    cache_read=int(usage.get("cache_read_input_tokens") or 0),
                    cache_write=cache_write,
                    output=int(usage.get("output_tokens") or 0),
                    reasoning=int(
                        (usage.get("output_tokens_details") or {}).get("thinking_tokens")
                        or usage.get("thinking_tokens") or 0
                    ),
                    stop_reason=message.get("stop_reason"),
                    tool_calls=tool_calls,
                    thinking_level=event.get("effort"),
                    tools=tools,
                )
                last = record
                yield record
