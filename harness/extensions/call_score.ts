/**
 * call score: Jev judges whether each tool call of a turn was necessary.
 *
 * voice_score answers "was the prose worth it". This answers the other half of
 * the bill: the calls the run spent. One Jev call per run scores every call of
 * the turn's tool loop - a necessity score and a result gate, multiplied - and
 * the entry draws one line under the turn: `calls  1.5/3 2.8/3 0.4/3 +9`.
 *
 * Deterministic side first, no model needed to see it in the transcripts:
 *   - repeated    - same tool with near-identical arguments, counted from the
 *                   earlier calls of the run (Jaccard 0.8 over the arg words)
 *   - subsumed    - a read whose path/range an earlier read already covered; a
 *                   read with neither offset nor limit is taken to cover the
 *                   tool's first READ_WINDOW lines of that path
 *   - oversize    - a result above OVERSIZE chars
 * The sources: subsumed retrieval, near-duplicate script generation and test
 * re-execution are the three cost-inefficient behaviours in
 * https://arxiv.org/abs/2609.30725; per-call efficiency is not per-run saving
 * (https://arxiv.org/html/2607.12161v4), and trajectory reduction is where the
 * saving lands (https://arxiv.org/html/2509.23586).
 *
 * Jev sees the request, the call line and a bounded slice of its result,
 * SLICE_HEAD chars from the front and SLICE_TAIL from the back, never the whole
 * result. Necessity is 0-3, higher is better, and the gate probability multiplies
 * it so an empty or off-target result cannot be paid for with a small call.
 * At most CALL_MAX calls per run are scored, newest kept; the rest count as
 * dropped and the expanded view says so.
 *
 * The bands are parked: the 2026-10-04 calibration found no gap to sit them in
 * (see CALL_PASS), so the line draws its numbers dim and claims no colour until
 * the ledger holds enough real rows to set the cuts.
 *
 * Display only: nothing is corrected, the entry never reaches the model, and
 * the whole feature costs one classifier call per run while it is on. Its own
 * switch, separate from /voice-score: `/call-score on|off|status`, persisted to
 * CONFIG_PATH. Off spends nothing. Rows share the voice_score ledger
 * (~/.local/share/voice_score/scores.jsonl) with kind "call".
 */
import { homedir } from "node:os";
import { join } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import {
	appendLines,
	argLine,
	ARGS_MAX,
	COLORS,
	LEDGER_PATH,
	LABEL,
	readEnabled,
	REQUEST_MAX,
	REPEAT_OVERLAP,
	SCALE,
	SHOWN,
	similarity,
	stamp,
	textOf,
	thousands,
	tier,
	writeEnabled,
} from "./voice_score.ts";

export const CONFIG_PATH = join(homedir(), ".pi/agent/call_score.json");
/** The read tool's own window when it is given neither an offset nor a limit. */
export const READ_WINDOW = 2000;
/** Calls scored per run, newest kept; the dropped ones are only counted. */
export const CALL_MAX = 12;
/** The bounded slice of a result the judge sees: head plus tail. */
export const SLICE_HEAD = 600;
export const SLICE_TAIL = 200;
/** A result above this many chars reads as oversized in the evidence. */
export const OVERSIZE = 12000;
/**
 * Parked on 2026-10-04: the calibration found no gap for bands to sit in. A
 * hand set of 10 (5 repeated/oversized, 5 targeted) scored wasteful 0.02-0.87
 * against necessary 0.01-1.22, and 230 calls from 25 sessions ran 0.00-2.71
 * with a smooth histogram - only 16 flagged calls, medians 0.80 against 1.12.
 * The score tracks result size (Spearman -0.34) but barely tracks repeats
 * (-0.17). Until a later calibration finds a gap, the line draws its numbers
 * dim: no red, yellow or green is claimed. Set both above 0 to switch bands on.
 */
export const CALL_PASS = 0;
export const CALL_GOOD = 0;

export const NECESSITY_CRITERIA = [
	"0: unnecessary - subsumed by another call, repeated, or unrelated to the task",
	"1: marginal - could have been folded into another call or answered from context already present",
	"2: necessary but wider than needed - a broad query or a result bigger than the task needed",
	"3: necessary and well scoped - the narrowest call that moved the task",
];

export const CALL_GATE = {
	true: "it answered what the call asked and moved the task",
	false: "it was empty, an error, or off target",
} as const;

export type Call = { id: string; name: string; args: string; raw?: Record<string, unknown>; chars?: number; slice?: string; error?: boolean };
export type CallEvidence = { chars: number; repeats: number; subsumed: boolean; oversize: boolean };
export type CallScore = {
	index: number;
	name: string;
	args: string;
	score: number;
	gate: number;
	confidence: number;
	evidence: CallEvidence;
};
export type CallScoreData = { calls: CallScore[]; dropped: number; error?: string; at: number };
export type CallRow = {
	at: string;
	session: string;
	kind: "call";
	tool: string;
	necessity: number;
	gate: number;
	score: number;
	repeats: number;
	subsumed: boolean;
	oversize: boolean;
	chars: number;
};
export type Question =
	| { type: "score"; instructions: string; criteria: string[] }
	| { type: "bool"; instructions: string; criteria: { true: string; false: string } };

/** read voice_score.ts (1,840 chars result) - the same shape as the trace line. */
export function callLine(call: Call): string {
	if (call.chars === undefined) return `${call.name} ${call.args}`.trim();
	const failed = call.error ? ", error" : "";
	return `${call.name} ${call.args} (${thousands(call.chars)} chars result${failed})`.trim();
}

/** Head and tail of a result; the middle is what the judge never sees. */
export function sliceOf(content: unknown): string {
	const text = textOf(content);
	if (text.length <= SLICE_HEAD + SLICE_TAIL) return text;
	return `${text.slice(0, SLICE_HEAD)}\n...\n${text.slice(-SLICE_TAIL)}`;
}

/** The line range a read call asked for; undefined when it names no path. */
export function range(call: Call): { path: string; start: number; end: number } | undefined {
	const raw = call.raw;
	if (typeof raw?.path !== "string") return undefined;
	const offset = typeof raw.offset === "number" ? raw.offset : 1;
	const limit = typeof raw.limit === "number" ? raw.limit : READ_WINDOW;
	return { path: raw.path, start: offset, end: offset + limit - 1 };
}

/** An earlier read that already covered this one's path and range. */
export function subsumed(calls: Call[], index: number): boolean {
	const call = calls[index];
	if (call.name !== "read") return false;
	const mine = range(call);
	if (!mine) return false;
	return calls
		.slice(0, index)
		.some((earlier) => {
			if (earlier.name !== "read") return false;
			const theirs = range(earlier);
			if (!theirs) return false;
			return theirs.path === mine.path && theirs.start <= mine.start && theirs.end >= mine.end;
		});
}

/** Earlier calls of the run with the same tool and near-identical arguments. */
export function repeated(calls: Call[], index: number): number {
	const call = calls[index];
	return calls
		.slice(0, index)
		.filter((earlier) => earlier.name === call.name && similarity(earlier.args, call.args) >= REPEAT_OVERLAP).length;
}

export function evidence(calls: Call[], index: number): CallEvidence {
	const call = calls[index];
	const chars = call.chars ?? 0;
	return { chars, repeats: repeated(calls, index), subsumed: subsumed(calls, index), oversize: chars > OVERSIZE };
}

/** One necessity, one gate question per call. */
export function buildQuestions(calls: Call[]): Record<string, Question> {
	const questions: Record<string, Question> = {};
	calls.forEach((_call, index) => {
		questions[`n${index}`] = {
			type: "score",
			instructions:
				`Was call \`c${index}\` necessary for this task? ` +
				"Judge only the call, not whether its result was correct.",
			criteria: NECESSITY_CRITERIA,
		};
		questions[`h${index}`] = {
			type: "bool",
			instructions: `Did the result of \`c${index}\` give what the turn needed?`,
			criteria: CALL_GATE,
		};
	});
	return questions;
}

export function stateOf(calls: Call[], request = ""): Record<string, string> {
	const state: Record<string, string> = { request };
	calls.forEach((call, index) => {
		state[`c${index}`] = callLine(call);
		state[`s${index}`] = call.slice ?? "";
	});
	return state;
}

/** The gate multiplies the score, so an empty result cannot be a cheap call. */
export function necessity(score: number, gate: number): number {
	return Math.round(score * gate * 100) / 100;
}

/** Parked bands (both 0) return a dim "uncalibrated"; tests pass explicit cuts. */
export function callBand(
	score: number,
	pass = CALL_PASS,
	good = CALL_GOOD,
): { label: string; color: "success" | "warning" | "error" | "dim" } {
	if (good <= 0) return { label: "uncalibrated", color: "dim" };
	const names = { low: "needless", mid: "justified", high: "necessary" } as const;
	const where = tier(score, pass, good);
	return { label: names[where], color: COLORS[where] };
}

function detail(score: CallScore): string {
	const value = necessity(score.score, score.gate);
	const flags = [
		score.evidence.repeats > 0 ? `repeats ${score.evidence.repeats}` : "",
		score.evidence.subsumed ? "subsumed" : "",
		score.evidence.oversize ? "oversize" : "",
	]
		.filter(Boolean)
		.join(" ");
	return (
		`  ${score.name} ${score.args} ${callBand(value).label} ${value.toFixed(1)}/${SCALE} ` +
		`gate ${score.gate.toFixed(2)} conf ${score.confidence.toFixed(2)} ` +
		`${flags ? `${flags} ` : ""}${score.evidence.chars} chars`
	);
}

/**
 * The lines the entry draws. `fg` is the theme's colour function, passed in so
 * the text can be checked without a terminal.
 */
export function renderLines(
	data: CallScoreData,
	expanded: boolean,
	fg: (color: "dim" | "success" | "warning" | "error", text: string) => string,
): string[] {
	if (data.error) return [fg("warning", `call score unavailable: ${data.error}`)];
	const calls = data.calls ?? [];
	const shown = calls
		.slice(0, SHOWN)
		.map((call) => fg(callBand(necessity(call.score, call.gate)).color, `${necessity(call.score, call.gate).toFixed(1)}/${SCALE}`));
	if (calls.length > SHOWN) shown.push(fg("dim", `+${calls.length - SHOWN}`));
	const lines = [fg("dim", `${"calls".padEnd(LABEL)} ${shown.join(" ") || "nothing scored"}`)];
	if (expanded) {
		for (const call of calls) lines.push(fg("dim", detail(call)));
		if (data.dropped > 0) lines.push(fg("dim", `  +${data.dropped} calls not scored`));
	}
	return lines;
}

/** One row per scored call, on the shared ledger. */
export function ledgerRows(data: CallScoreData, session: string, date = new Date()): CallRow[] {
	return (data.calls ?? []).map((call) => ({
		at: stamp(date),
		session,
		kind: "call",
		tool: call.name,
		necessity: call.score,
		gate: Math.round(call.gate * 100) / 100,
		score: Math.round(necessity(call.score, call.gate) * 10) / 10,
		repeats: call.evidence.repeats,
		subsumed: call.evidence.subsumed,
		oversize: call.evidence.oversize,
		chars: call.evidence.chars,
	}));
}

/** Read and write on every message_end, reset per run like voice_score. */
function factory(pi: ExtensionAPI) {
	let enabled = readEnabled(CONFIG_PATH);
	let request = "";
	let calls: Call[] = [];
	let dropped = 0;

	function reset(): void {
		request = "";
		calls = [];
		dropped = 0;
	}

	function add(id: unknown, name: unknown, args: unknown): void {
		if (typeof name !== "string") return;
		calls.push({
			id: typeof id === "string" ? id : "",
			name,
			args: argLine(args).slice(0, ARGS_MAX),
			raw: args && typeof args === "object" ? (args as Record<string, unknown>) : undefined,
		});
		if (calls.length > CALL_MAX) {
			calls.shift();
			dropped += 1;
		}
	}

	function finish(id: unknown, content: unknown, failed: unknown): void {
		if (typeof id !== "string" || !id) return;
		const call = calls.find((each) => each.id === id && each.chars === undefined);
		if (!call) return;
		call.chars = textOf(content).length;
		call.slice = sliceOf(content);
		if (failed === true) call.error = true;
	}

	pi.on("session_start", () => {
		enabled = readEnabled(CONFIG_PATH);
		reset();
	});
	pi.on("agent_start", reset);

	pi.on("message_end", (event) => {
		if (!enabled) return;
		const message = event.message as { role?: string; content?: unknown; toolCallId?: string; isError?: boolean };
		if (message.role === "user") {
			const text = textOf(message.content);
			if (text) request = text.slice(0, REQUEST_MAX);
			return;
		}
		if (message.role === "toolResult") {
			finish(message.toolCallId, message.content, message.isError);
			return;
		}
		if (message.role !== "assistant" || !Array.isArray(message.content)) return;
		for (const block of message.content) {
			if (!block || typeof block !== "object") continue;
			const candidate = block as { type?: string; id?: string; name?: string; arguments?: unknown };
			if (candidate.type === "toolCall") add(candidate.id, candidate.name, candidate.arguments);
		}
	});

	pi.registerEntryRenderer<CallScoreData>("call-score", (entry, { expanded }, theme) => {
		const lines = renderLines(entry.data ?? { calls: [], dropped: 0, at: 0 }, expanded, (color, text) =>
			theme.fg(color, text),
		);
		return {
			render: () => lines,
			invalidate: () => {},
		};
	});

	pi.registerCommand("call-score", {
		description: "Turn Jev scoring of each tool call on or off, or show its state",
		handler: async (args, ctx) => {
			const word = args.trim().toLowerCase();
			if (word === "on" || word === "off") {
				enabled = word === "on";
				writeEnabled(enabled, CONFIG_PATH);
				if (!enabled) reset();
			}
			const bands = CALL_GOOD > 0 ? `pass ${CALL_PASS} necessary ${CALL_GOOD}` : "bands parked, numbers only";
			const detail = enabled ? `${bands}, up to ${CALL_MAX} calls a run` : "no Jev call is spent";
			ctx.ui.notify(`call score: ${enabled ? "on" : "off"} - ${detail}`, "info");
		},
	});

	pi.on("agent_before_settle", async (_event, ctx) => {
		if (!enabled) return;
		const asked = { request, calls: calls.slice(), dropped };
		reset();
		if (asked.calls.length === 0) return;

		if (process.env.PI_CALL_TRACE === "1") {
			const lines = asked.calls.map((call, index) => `${index} ${callLine(call)}`);
			process.stderr.write(`call trace: request ${JSON.stringify(asked.request)}\n${lines.join("\n")}\n`);
		}

		const jev = ctx.modelRegistry.findOfType("classifier", "typesafe", "jev-latest");
		if (!jev) return;

		const result = await ctx.modelRegistry.classify(jev, {
			state: stateOf(asked.calls, asked.request),
			questions: buildQuestions(asked.calls),
		});
		const data: CallScoreData = { calls: [], dropped: asked.dropped, at: Date.now() };
		if (result.stopReason !== "stop") {
			data.error = result.errorMessage ?? result.stopReason;
		} else {
			asked.calls.forEach((call, index) => {
				const score = result.answers[`n${index}`];
				const gate = result.answers[`h${index}`];
				if (score?.type !== "score" || gate?.type !== "bool") return;
				data.calls.push({
					index,
					name: call.name,
					args: call.args,
					score: score.score,
					gate: gate.probability,
					confidence: score.confidence,
					evidence: evidence(asked.calls, index),
				});
			});
		}
		pi.appendEntry<CallScoreData>("call-score", data);
		appendLines(ledgerRows(data, process.env.PI_SESSION_ID ?? ""), LEDGER_PATH);
	});
}

export default factory;