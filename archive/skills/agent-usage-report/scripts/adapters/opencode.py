"""opencode adapter.

Store: ``~/.local/share/opencode/opencode.db`` (SQLite)

- ``session``  -> ``directory`` for the project, plus aggregate cost/tokens
- ``message``  -> ``data`` JSON: role, ``tokens`` (input, output, reasoning,
  cache.read, cache.write), ``cost``, ``modelID``, ``providerID``
- ``part``     -> ``data`` JSON, used only to recover the text of user
  messages for correction detection

opencode records real cost, so cost comes from the log where non-zero.
Newer opencode versions use SQLite; older ones wrote JSON under a ``storage``
directory, which is handled by the generic adapter when configured.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from .util import expand, make, parse_ts, text_of

NAME = "opencode"
LABEL = "opencode"


def db_path():
    override = os.environ.get("AGENT_REPORT_OPENCODE_DB")
    if override:
        return expand(override)
    return Path.home() / ".local" / "share" / "opencode" / "opencode.db"


def discover():
    path = db_path()
    return [path] if path.exists() else []


def available():
    return bool(discover())


def records():
    path = db_path()
    if not path.exists():
        return
    uri = "file:{}?mode=ro".format(path.as_posix())
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=10)
    except sqlite3.Error:
        return
    try:
        conn.row_factory = sqlite3.Row
        yield from _read(conn)
    except sqlite3.Error:
        return
    finally:
        conn.close()


def _read(conn):
    projects = {}
    try:
        for row in conn.execute("SELECT id, directory FROM session"):
            projects[row["id"]] = row["directory"] or ""
    except sqlite3.Error:
        pass

    texts = {}
    try:
        query = (
            "SELECT p.message_id AS mid, p.data AS data "
            "FROM part p JOIN message m ON m.id = p.message_id "
            "WHERE m.data LIKE '%\"role\":\"user\"%' "
            "AND p.data LIKE '%\"type\":\"text\"%'"
        )
        for row in conn.execute(query):
            data = json.loads(row["data"])
            if data.get("type") == "text":
                texts[row["mid"]] = texts.get(row["mid"], "") + str(data.get("text") or "")
    except (sqlite3.Error, ValueError):
        pass

    query = "SELECT id, session_id, data, time_created FROM message ORDER BY time_created, id"
    for row in conn.execute(query):
        try:
            data = json.loads(row["data"])
        except ValueError:
            continue
        role = data.get("role")
        session_id = row["session_id"] or ""
        project = projects.get(session_id, "")
        timestamp = parse_ts(data.get("time", {}).get("completed") or row["time_created"])

        if role == "user":
            model = data.get("model") or {}
            yield make(
                kind="user", harness=NAME, session_id=session_id,
                project=project, timestamp=timestamp,
                provider=(model.get("providerID") if isinstance(model, dict) else "") or "",
                model=(model.get("modelID") if isinstance(model, dict) else "") or "",
                text=texts.get(row["id"], ""),
            )
        elif role == "assistant":
            tokens = data.get("tokens") or {}
            cache = tokens.get("cache") or {}
            provider = data.get("providerID") or ""
            model = data.get("modelID") or "unknown"
            cost = data.get("cost")
            cost = float(cost) if isinstance(cost, (int, float)) and cost else None
            if not tokens:
                continue
            record = make(
                kind="assistant", harness=NAME, session_id=session_id,
                project=project, timestamp=timestamp,
                provider=provider, model=model,
                input=int(tokens.get("input") or 0),
                cache_read=int(cache.get("read") or 0),
                cache_write=int(cache.get("write") or 0),
                output=int(tokens.get("output") or 0),
                reasoning=int(tokens.get("reasoning") or 0),
                total=int(tokens.get("total") or 0),
                cost=cost, cost_source="recorded" if cost else None,
                stop_reason=data.get("finish") or "stop",
                thinking_level=data.get("mode") or data.get("agent"),
            )
            yield record
