"""Codex CLI adapter.

Logs: ``~/.codex/sessions/<YYYY>/<MM>/<DD>/rollout-*.jsonl``
      ``~/.codex/archived_sessions/rollout-*.jsonl``

Relevant event types:

- ``session_meta``   -> cwd, session id, model_provider, context_window
- ``turn_context``   -> model, effort, cwd
- ``event_msg`` ``item_completed`` with ``item.type == "UserMessage"``
- ``event_msg`` ``token_count`` with ``info.last_token_usage`` (per turn, not
  cumulative) -> usage
- ``event_msg`` ``task_complete`` with an ``error`` -> a failed turn

Codex folds cached tokens *into* ``input_tokens``, unlike pi and Claude Code,
so uncached input is ``input_tokens - cached_input_tokens - cache_write``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .util import expand, make, parse_ts, text_of

NAME = "codex"
LABEL = "Codex"

_INTERESTING = ('"token_count"', '"UserMessage"', '"turn_context"',
                '"session_meta"', '"task_complete"')

_TOOL_ITEMS = {
    "CommandExecution", "FileChange", "McpToolCall", "WebSearch",
    "PatchApply", "ComputerUse", "LocalShellCall", "CustomToolCall",
}


def roots():
    override = os.environ.get("AGENT_REPORT_CODEX_DIR")
    if override:
        return [expand(override)]
    home = Path.home() / ".codex"
    return [p for p in (home / "sessions", home / "archived_sessions") if p.exists()]


def discover():
    return roots()


def available():
    return bool(discover())


def records():
    for base in discover():
        for path in sorted(base.rglob("*.jsonl")):
            for rec in _session(path):
                yield rec


def _session(path):
    session_id = path.stem
    project = ""
    provider = ""
    model = ""
    effort = None
    context_window = None
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
            timestamp = parse_ts(event.get("timestamp"))
            payload = event.get("payload") or {}

            if etype == "session_meta":
                session_id = payload.get("session_id") or session_id
                project = payload.get("cwd") or project
                provider = payload.get("model_provider") or provider
                context_window = payload.get("context_window") or context_window
            elif etype == "turn_context":
                model = payload.get("model") or model
                effort = payload.get("effort") or effort
                project = payload.get("cwd") or project
            elif etype == "event_msg":
                kind = payload.get("type")
                if kind == "item_completed":
                    item = payload.get("item") or {}
                    itype = item.get("type")
                    if itype == "UserMessage":
                        yield make(
                            kind="user", harness=NAME, session_id=session_id,
                            project=project, timestamp=timestamp,
                            provider=provider, model=model,
                            text=text_of(item.get("content")),
                        )
                    elif itype in _TOOL_ITEMS and last is not None:
                        last["tool_calls"] = last.get("tool_calls", 0) + 1
                elif kind == "token_count":
                    info = payload.get("info") or {}
                    usage = info.get("last_token_usage") or info.get("total_token_usage")
                    if not usage:
                        continue
                    cache_read = int(usage.get("cached_input_tokens") or 0)
                    cache_write = int(usage.get("cache_write_input_tokens") or 0)
                    raw_input = int(usage.get("input_tokens") or 0)
                    uncached = max(0, raw_input - cache_read - cache_write)
                    output = int(usage.get("output_tokens") or 0)
                    record = make(
                        kind="assistant", harness=NAME, session_id=session_id,
                        project=project, timestamp=timestamp,
                        provider=provider or "openai", model=model or "unknown",
                        input=uncached, cache_read=cache_read,
                        cache_write=cache_write, output=output,
                        reasoning=int(usage.get("reasoning_output_tokens") or 0),
                        total=raw_input + output,
                        stop_reason="stop",
                        thinking_level=effort,
                        context_window=context_window or info.get("model_context_window"),
                    )
                    last = record
                    yield record
                elif kind == "task_complete":
                    if payload.get("error") and last is not None:
                        last["stop_reason"] = "error"
                        last["tool_errors"] = last.get("tool_errors", 0) + 1
