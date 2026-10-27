"""pi-coding-agent adapter.

Logs: ``~/.pi/agent/sessions/<project>/<timestamp>_<uuid>.jsonl``

Each JSONL line is an event. The ones that matter:

- ``session``               -> cwd, session id
- ``model_change``          -> provider, modelId
- ``thinking_level_change`` -> thinkingLevel
- ``message`` with role user/assistant/toolResult
      assistant carries ``usage`` (input, output, cacheRead, cacheWrite,
      reasoning, totalTokens) and a ``cost`` breakdown in dollars.

pi records real billed cost, so cost is taken from the log, never computed.
The prefilter skips lines that cannot carry usage to keep large sessions fast.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .util import expand, make, parse_ts, text_of

NAME = "pi"
LABEL = "pi"

_INTERESTING = ('"usage"', '"role":"user"', '"toolResult"', '"type":"session"',
                '"type":"model_change"', '"thinking_level_change"')


def root():
    override = os.environ.get("AGENT_REPORT_PI_DIR")
    if override:
        return expand(override)
    return Path.home() / ".pi" / "agent" / "sessions"


def discover():
    base = root()
    return [base] if base.exists() else []


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
    thinking = None
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
            if etype == "session":
                session_id = event.get("id") or session_id
                project = event.get("cwd") or project
            elif etype == "model_change":
                provider = event.get("provider") or provider
                model = event.get("modelId") or model
            elif etype == "thinking_level_change":
                thinking = event.get("thinkingLevel")
            elif etype == "message":
                message = event.get("message") or {}
                role = message.get("role")
                timestamp = parse_ts(event.get("timestamp"))

                if role == "user":
                    yield make(
                        kind="user", harness=NAME, session_id=session_id,
                        project=project, timestamp=timestamp,
                        provider=provider, model=model,
                        text=text_of(message.get("content")),
                    )
                elif role == "assistant":
                    usage = message.get("usage")
                    if not usage:
                        continue
                    cost = None
                    source = None
                    breakdown = usage.get("cost") or {}
                    if isinstance(breakdown, dict) and breakdown.get("total") is not None:
                        cost = float(breakdown["total"])
                        source = "recorded"
                    tool_calls = 0
                    tools = {}
                    for part in message.get("content") or []:
                        if isinstance(part, dict) and part.get("type") == "toolCall":
                            tool_calls += 1
                            name = str(part.get("name") or "tool")
                            tools[name] = tools.get(name, 0) + 1
                    record = make(
                        kind="assistant", harness=NAME, session_id=session_id,
                        project=project, timestamp=timestamp,
                        provider=message.get("provider") or provider,
                        model=message.get("model") or model,
                        input=int(usage.get("input") or 0),
                        cache_read=int(usage.get("cacheRead") or 0),
                        cache_write=int(usage.get("cacheWrite") or 0),
                        output=int(usage.get("output") or 0),
                        reasoning=int(usage.get("reasoning") or 0),
                        total=int(usage.get("totalTokens") or 0),
                        cost=cost, cost_source=source,
                        stop_reason=message.get("stopReason"),
                        tool_calls=tool_calls,
                        thinking_level=thinking,
                        tools=tools,
                    )
                    last = record
                    yield record
                elif role == "toolResult":
                    if message.get("isError") and last is not None:
                        last["tool_errors"] = last.get("tool_errors", 0) + 1
