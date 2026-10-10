#!/usr/bin/env -S node --experimental-strip-types --no-warnings
/**
 * hook: agent1's harness for Claude Code, through the hook contract.
 *
 * pi runs harness/extensions/*.ts in process. Claude Code runs this file once
 * per hook event, wired in hooks/hooks.json, and it calls the same exported
 * functions - so a rule lives in one place and both harnesses enforce it.
 *
 *   guard      PreToolUse         command_guard on Bash, edit_guard on Edit;
 *                                 exit 2 blocks, stderr is the reason
 *   lint       Stop               harness lint over the files this session
 *                                 edited, read from the transcript; at most
 *                                 MAX_CONTINUATIONS nudges per session
 *   nudge      PostToolUse(Failure)  failure_nudge: a line to the user after
 *                                 NUDGE_AT failures in a row
 *   rules      SessionStart       rules_context plus the telegraph rule, as
 *                                 additionalContext
 *   telegraph  on|off|status      the shared voice-rule switch (/telegraph)
 *
 * Per-session state (lint nudges, failure streak) is in
 * ~/.local/state/agent1/sessions/<session_id>.json.
 *
 * Usage: node --experimental-strip-types harness/hook.ts <command> < event.json
 *        harness/hook.ts -h | --help
 */
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { commandBlock } from "./extensions/command_guard.ts";
import { editHit } from "./extensions/edit_guard.ts";
import { NUDGE_AT, nudgeText } from "./extensions/failure_nudge.ts";
import { type Finding, key, lint, findingsMessage, MAX_CONTINUATIONS } from "./extensions/harness_lint.ts";
import { currentRules } from "./extensions/rules_context.ts";
import { readEnabled, readRule, ruleSection, RULE_PATH, writeEnabled } from "./extensions/telegraph.ts";

const STATE_DIR = join(homedir(), ".local/state/agent1/sessions");
const EDIT_TOOLS = new Set(["Edit", "Write", "NotebookEdit"]);
const BLOCK = 2;

type Event = {
	session_id?: string;
	transcript_path?: string;
	cwd?: string;
	hook_event_name?: string;
	tool_name?: string;
	tool_input?: Record<string, unknown>;
};

type State = { reported: string[]; continuations: number; streak: number };

function readStdin(): Event {
	try {
		return JSON.parse(readFileSync(0, "utf8")) as Event;
	} catch {
		return {};
	}
}

function statePath(event: Event): string {
	return join(STATE_DIR, `${(event.session_id ?? "unknown").replace(/[^\w-]/g, "_")}.json`);
}

function loadState(event: Event): State {
	try {
		return { reported: [], continuations: 0, streak: 0, ...JSON.parse(readFileSync(statePath(event), "utf8")) };
	} catch {
		return { reported: [], continuations: 0, streak: 0 };
	}
}

function saveState(event: Event, state: State): void {
	mkdirSync(STATE_DIR, { recursive: true });
	writeFileSync(statePath(event), `${JSON.stringify(state)}\n`);
}

/** Refuse a Bash command or an Edit the same way pi does. */
function guard(event: Event): number {
	const input = event.tool_input ?? {};
	if (event.tool_name === "Bash" && typeof input.command === "string") {
		const reason = commandBlock(input.command);
		if (!reason) return 0;
		process.stderr.write(`${reason}\n`);
		return BLOCK;
	}
	// replace_all asks for every occurrence, so "exactly once" does not apply.
	if (event.tool_name !== "Edit" || input.replace_all === true) return 0;
	if (typeof input.file_path !== "string") return 0;
	let text: string;
	try {
		text = readFileSync(input.file_path, "utf8");
	} catch {
		return 0;
	}
	const reason = editHit(input.file_path, text, [{ oldText: input.old_string }]);
	if (!reason) return 0;
	process.stderr.write(`${reason}\n`);
	return BLOCK;
}

/** Every file an Edit, Write or NotebookEdit call named in the transcript. */
export function editedFiles(transcript: string): string[] {
	const files = new Set<string>();
	for (const line of transcript.split("\n")) {
		if (!line.includes('"tool_use"')) continue;
		let entry: { message?: { content?: unknown } };
		try {
			entry = JSON.parse(line);
		} catch {
			continue;
		}
		const content = entry.message?.content;
		if (!Array.isArray(content)) continue;
		for (const block of content) {
			if (block?.type !== "tool_use" || !EDIT_TOOLS.has(block.name)) continue;
			const path = block.input?.file_path ?? block.input?.notebook_path;
			if (typeof path === "string") files.add(path);
		}
	}
	return [...files];
}

/** Hand new findings in the session's edited files back to the agent. */
async function stop(event: Event): Promise<number> {
	if (!event.transcript_path) return 0;
	const state = loadState(event);
	if (state.continuations >= MAX_CONTINUATIONS) return 0;

	let transcript: string;
	try {
		transcript = readFileSync(event.transcript_path, "utf8");
	} catch {
		return 0;
	}
	const files = editedFiles(transcript);
	if (files.length === 0) return 0;

	const seen = new Set(state.reported);
	const report = await lint(files, event.cwd ?? process.cwd());
	const fresh = report.findings.filter((f: Finding) => !seen.has(key(f)));
	const failures = report.failures.filter((f) => !seen.has(key(f)));
	if (fresh.length === 0 && failures.length === 0) return 0;

	state.reported.push(...fresh.map(key), ...failures.map(key));
	state.continuations += 1;
	saveState(event, state);
	process.stdout.write(`${JSON.stringify({ decision: "block", reason: findingsMessage(fresh, failures) })}\n`);
	return 0;
}

/** Count failures in a row; tell the user once when the streak hits NUDGE_AT. */
function nudge(event: Event): number {
	const state = loadState(event);
	const failed = event.hook_event_name === "PostToolUseFailure";
	const before = state.streak;
	state.streak = failed ? state.streak + 1 : 0;
	if (state.streak !== before) saveState(event, state);
	if (failed && state.streak === NUDGE_AT) {
		process.stdout.write(`${JSON.stringify({ systemMessage: nudgeText(event.tool_name ?? "a tool") })}\n`);
	}
	return 0;
}

/** The session-start rules, and the voice rule while its switch is on. */
function rules(): number {
	const parts = [currentRules()];
	if (readEnabled()) parts.push(ruleSection(readRule()));
	const context = parts.filter(Boolean).join("\n\n");
	process.stdout.write(
		`${JSON.stringify({ hookSpecificOutput: { hookEventName: "SessionStart", additionalContext: context } })}\n`,
	);
	return 0;
}

function telegraph(word: string): number {
	if (word === "on" || word === "off") writeEnabled(word === "on");
	else if (word && word !== "status") {
		process.stderr.write("usage: hook.ts telegraph on|off|status\n");
		return 1;
	}
	const rule = readRule() ? "found" : "MISSING";
	process.stdout.write(
		`telegraph rule: ${readEnabled() ? "on" : "off"} - rule ${rule} at ${RULE_PATH}; ` +
			"pi applies it on the next request, Claude Code on the next session\n",
	);
	return 0;
}

const USAGE = "usage: hook.ts guard|lint|nudge|rules < event.json\n       hook.ts telegraph on|off|status\n";

async function main(argv: string[]): Promise<number> {
	const [command, arg = ""] = argv;
	if (command === "-h" || command === "--help") {
		process.stdout.write(USAGE);
		return 0;
	}
	if (command === "telegraph") return telegraph(arg.trim().toLowerCase());
	if (command === "rules") return rules();
	if (command === "guard") return guard(readStdin());
	if (command === "nudge") return nudge(readStdin());
	if (command === "lint") return stop(readStdin());
	process.stderr.write(USAGE);
	return 1;
}

if (import.meta.url === `file://${process.argv[1]}`) {
	process.exitCode = await main(process.argv.slice(2));
}
