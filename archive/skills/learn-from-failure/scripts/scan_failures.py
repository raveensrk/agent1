#!/usr/bin/env python3
"""Scan a Pi session transcript for hard tool failures.

Flags every tool result pi recorded with isError, pairs it with the call's
arguments, and prints one block per failure: index, time, tool, arguments,
error text. This is the input for the learn-from-failure report; the skill
decides nothing here and the script judges nothing here.

Transcript order: --path, $PI_SESSION_FILE, newest .jsonl for cwd, newest overall.
"""

import argparse
import json
import os
import sys
from pathlib import Path

SESSIONS_DIR = Path.home() / ".pi" / "agent" / "sessions"
ERROR_CHARS = 300
ARG_CHARS = 160


def find_transcript(explicit):
	if explicit:
		return Path(explicit)
	env = os.environ.get("PI_SESSION_FILE")
	if env:
		return Path(env)

	# pi names session dirs after the cwd: /a/b -> -a-b-
	tag = f"-{os.getcwd().replace('/', '-')}-"
	ours = sorted((SESSIONS_DIR / tag).glob("*.jsonl"))
	if ours:
		return ours[-1]

	everything = sorted(SESSIONS_DIR.glob("*/*.jsonl"))
	return everything[-1] if everything else None


def compact_args(tool, args):
	"""The one line a person recognizes: command, path, query, question."""
	if tool == "bash":
		return args.get("command", "")
	for key in ("path", "file_path", "query", "pattern", "url", "question"):
		if args.get(key):
			return str(args[key])
	return json.dumps(args, ensure_ascii=False)


def flat_text(content):
	parts = [block.get("text", "") for block in content if isinstance(block, dict)]
	return " | ".join(part.replace("\n", " ").strip() for part in parts if part)


def main():
	parser = argparse.ArgumentParser(
		description="Print every hard tool failure in a Pi session transcript.",
	)
	parser.add_argument("--path", help="transcript file, default $PI_SESSION_FILE")
	parser.add_argument("--json", action="store_true", help="JSON output")
	parser.add_argument("--error-chars", type=int, default=ERROR_CHARS, help="error text cap")
	opts = parser.parse_args()

	transcript = find_transcript(opts.path)
	if not transcript or not transcript.exists():
		print(f"no transcript found (looked at {SESSIONS_DIR})", file=sys.stderr)
		return 1

	calls = {}
	failures = []
	result_count = 0

	for line in transcript.read_text(errors="replace").splitlines():
		try:
			entry = json.loads(line)
		except json.JSONDecodeError:
			continue
		if entry.get("type") != "message":
			continue
		message = entry.get("message", {})
		role = message.get("role")

		if role == "assistant":
			# Tool calls live on assistant messages, keyed by id for pairing.
			for block in message.get("content", []):
				if isinstance(block, dict) and block.get("type") == "toolCall":
					calls[block["id"]] = block

		elif role == "toolResult":
			result_count += 1
			if not message.get("isError"):
				continue
			call = calls.get(message.get("toolCallId"), {})
			args = call.get("arguments", {}) or {}
			failures.append({
				"index": len(failures) + 1,
				"time": entry.get("timestamp", "")[11:19],
				"tool": message.get("toolName", "?"),
				"args": compact_args(call.get("name", "?"), args),
				"error": flat_text(message.get("content", [])),
			})

	for failure in failures:
		failure["args"] = failure["args"].replace("\n", " ")[:ARG_CHARS]
		failure["error"] = failure["error"][:opts.error_chars]

	if opts.json:
		print(json.dumps({"transcript": str(transcript), "results": result_count, "failures": failures}, indent=2))
		return 0

	print(f"{transcript}: {len(failures)} failures across {result_count} tool results")
	for failure in failures:
		print(f"{failure['index']}. [{failure['time']}] {failure['tool']}")
		print(f"   args:  {failure['args']}")
		print(f"   error: {failure['error']}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
