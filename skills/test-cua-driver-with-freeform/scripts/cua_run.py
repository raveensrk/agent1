#!/usr/bin/env python3
"""Thin wrapper over `cua-driver call` for the Freeform test.

Each `cua-driver call` is its own process, so element tokens from one call
are stale in the next. This wrapper keeps one session label on every call,
JSON-encodes arguments safely, and strips base64 screenshots from output.

Usage:
  cua_run.py js FILE.js        run FILE.js through run_script
  cua_run.py call TOOL JSON    call one tool, JSON object as arguments
  cua_run.py shot PID WID OUT  save a window screenshot to OUT (png)
  cua_run.py help              long help
  cua_run.py -h, --help        short help

Options:
  --session NAME   session label (default: freeform-test)

Example:
  cua_run.py shot 2352 20225 /tmp/board.png
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

LONG_HELP = __doc__ + """
Output is the tool's JSON with every *_b64 field replaced by "<b64>" and the
per-call log of run_script dropped. A run_script result carries `ok`,
`value` (the script's return) and `error`.

run_script gets timeout_ms 120000 and max_calls 300. Inside a script only
these tools are allowed: click, double_click, right_click, set_value,
type_text, press_key, hotkey, scroll, drag, move_cursor, launch_app,
list_apps, list_windows, get_window_state, verify_state, zoom. Call
set_window_frame, invoke_menu and bring_to_front with `call` instead.
"""


def strip(obj):
    if isinstance(obj, dict):
        return {
            k: ("<b64>" if k.endswith("b64") else strip(v))
            for k, v in obj.items()
            if k != "calls"
        }
    if isinstance(obj, list):
        return [strip(x) for x in obj]
    return obj


def call(tool: str, args: dict) -> int:
    proc = subprocess.run(
        ["cua-driver", "call", tool, json.dumps(args)],
        capture_output=True,
        text=True,
    )
    out = proc.stdout or proc.stderr
    try:
        print(json.dumps(strip(json.loads(out)), indent=1))
    except json.JSONDecodeError:
        print(out)
    return proc.returncode


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 0
    if argv[:1] == ["help"]:
        print(LONG_HELP)
        return 0

    parser = argparse.ArgumentParser(
        prog="cua_run.py",
        description="Wrapper over cua-driver call for the Freeform test.",
        epilog="Example: cua_run.py shot 2352 20225 /tmp/board.png",
    )
    parser.add_argument("--session", "-s", default="freeform-test")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_js = sub.add_parser("js", help="run a JavaScript file via run_script")
    p_js.add_argument("file")

    p_call = sub.add_parser("call", help="call one tool")
    p_call.add_argument("tool")
    p_call.add_argument("json", nargs="?", default="{}")

    p_shot = sub.add_parser("shot", help="save a window screenshot")
    p_shot.add_argument("pid", type=int)
    p_shot.add_argument("window_id", type=int)
    p_shot.add_argument("out")

    sub.add_parser("help", help="long help")

    a = parser.parse_args(argv)
    if a.cmd == "js":
        with open(a.file, encoding="utf-8") as fh:
            script = fh.read()
        return call(
            "run_script",
            {
                "script": script,
                "session": a.session,
                "timeout_ms": 120000,
                "max_calls": 300,
            },
        )
    if a.cmd == "call":
        args = json.loads(a.json)
        args.setdefault("session", a.session)
        return call(a.tool, args)
    if a.cmd == "shot":
        return call(
            "get_window_state",
            {
                "pid": a.pid,
                "window_id": a.window_id,
                "include_accessibility_tree": False,
                "screenshot_out_file": a.out,
                "session": a.session,
            },
        )
    print(LONG_HELP)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
