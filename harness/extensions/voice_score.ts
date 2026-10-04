/**
 * voice score: Jev reads one turn's thinking, its reply and what it spent.
 *
 * The telegraph rule covers thinking as well as replies, but a rule with no
 * signal is a wish. This is the signal: after a run settles, one Jev call
 * scores every thinking block of the run plus the reply - voice and
 * token-efficiency, two questions each - and the result is appended as a
 * session entry, drawn as two lines under the turn, and written to a ledger.
 *
 * The entry draws two lines under the run: `voice  think 2.8/3  reply 2.2/3`
 * and `tokens think 1.4/3  reply 2.6/3`; both scales run 0 to 3, so every
 * number carries its max. Each block's token efficiency is Jev's 0-3
 * score for the block times `p(gate)`, the probability that the block delivers
 * what the turn needed (a reply) or avoids circularity (thinking), so an
 * omission cannot be paid for with brevity.
 *
 * Display only. It never nudges, blocks or rewrites, and the entry is not sent
 * to the model, so the whole feature costs one Jev call per run and no context.
 *
 * Voice thresholds, measured on 152 samples from 25 past sessions plus 10
 * labeled ones (calibration in [voice_probe](~/tmp/voice_probe)):
 *   - pre-rule thinking scored 0.66-1.52, telegraph replies 2.02-2.79
 *   - PASS 1.8 sits in that gap, GOOD 2.5 marks a clean telegraph
 * Efficiency thresholds, measured 2026-10-04 on 10 hand-labeled blocks (5
 * pre-rule thinking, 5 telegraph replies) plus 87 blocks from the 25 newest
 * sessions, the same probe script with the shipped questions:
 *   - labeled wasteful scored 0.17-0.52, labelled tight 0.81-2.62, so PASS
 *     0.75 sits in that one measured gap; the blocks were stable to 0.07
 *     across runs
 *   - the population ran 0.03-2.41, median 0.66, and only 4 of 87 reached 2.0:
 *     no second gap exists, so GOOD 1.5 is a judgement at the top quartile
 *     (21 of 87), not a measured edge
 *   - the score tracks the deterministic evidence it is drawn next to:
 *     Spearman -0.691 against filler count, +0.525 against deflate density,
 *     -0.232 against repeat count
 * Re-run the calibration before moving any number.
 *
 * The ledger is /Users/raveen_kumar_personal/.local/share/voice_score/scores.jsonl
 * (LEDGER_PATH): one row per scored block, machine-local, never committed.
 *
 * Toggle: /voice-score on|off|status, persisted to CONFIG_PATH. Off spends nothing.
 */
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { deflateSync } from "node:zlib";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export const CONFIG_PATH = join(homedir(), ".pi/agent/voice_score.json");
export const LEDGER_PATH = join(homedir(), ".local/share/voice_score/scores.jsonl");
/** Shorter blocks carry no voice to judge, only a score to guess. */
export const FLOOR = 200;
export const PASS = 1.8;
export const GOOD = 2.5;
/** Measured 2026-10-04: wasteful 0.17-0.52, tight 0.81-2.62 - the gap holds PASS. */
export const EFF_PASS = 0.75;
/** Top quartile of the 87-block population (21 of 87); a judgement, not a gap. */
export const EFF_GOOD = 1.5;
/** Scores the inline line shows before it summarises the rest. */
export const SHOWN = 4;
/** The label column: `voice` and `tokens` line up their first number. */
export const LABEL = 6;
/** The request kept for the judge, and the args summary per tool call. */
export const REQUEST_MAX = 2000;
export const ARGS_MAX = 120;
/** Oldest dropped beyond this many tool calls. */
export const TRACE_MAX = 12;
/** Two spans are duplicates at this Jaccard overlap of their word sets. */
export const REPEAT_OVERLAP = 0.8;
/** Rough English average: four characters a token. */
export const TOKENS_PER_CHAR = 0.25;
/** Jev scores both lines on a 0-3 scale, so every number draws as 2.6/3. */
export const SCALE = 3;

export const CRITERIA = [
	"0: prose paragraphs, no line breaks, articles and filler throughout",
	"1: prose paragraphs with some short sentences, filler still common",
	"2: short lines mixed with longer sentences, some filler or subordinate clauses",
	"3: telegraph: one idea per line, filler and subordinate clauses gone, fragments fine",
];

export const EFFICIENCY_CRITERIA = [
	"0: at least half the tokens are non-essential, restatement, filler or material the task did not ask for",
	"1: noticeable waste, repeated points, throat-clearing or detail beyond what the task needed",
	"2: mostly load-bearing, a few clauses or hedges could go",
	"3: every sentence carries information needed for this task, nothing could be cut without losing content",
];

/** The gate is one bool per block; a missing piece is the only thing it measures. */
export const GATE = {
	think: {
		true: "each step advances the reasoning, nothing re-derived",
		false: "it repeats or re-derives a point it already settled",
	},
	reply: {
		true: "it covers what the task needed",
		false: "something needed is missing",
	},
} as const;

/** Phrases the telegraph rule bans, matched on word boundaries, case-insensitive. */
export const FILLERS = [
	"actually",
	"basically",
	"essentially",
	"in order to",
	"it is important to note",
	"it is worth noting",
	"just",
	"note that",
	"quite",
	"really",
	"simply",
	"the fact that",
	"very",
];

export type Block = { kind: "think" | "reply"; text: string };
export type Trace = { id: string; name: string; args: string; chars?: number };
export type Question =
	| { type: "score"; instructions: string; criteria: string[] }
	| { type: "bool"; instructions: string; criteria: { true: string; false: string } };
/** What the deterministic half measured, next to Jev's number. */
export type Evidence = { chars: number; tokens: number; fillers: number; repeats: number };
export type VoiceScore = { kind: "think" | "reply"; index: number; score: number; confidence: number };
export type EfficiencyScore = {
	kind: "think" | "reply";
	index: number;
	score: number;
	gate: number;
	confidence: number;
	evidence: Evidence;
};
export type VoiceScoreData = {
	scores: VoiceScore[];
	efficiency?: EfficiencyScore[];
	error?: string;
	at: number;
};
export type LedgerRow = {
	at: string;
	session: string;
	kind: "think" | "reply";
	voice: number | null;
	efficiency: number;
	gate: number;
	chars: number;
	fillers: number;
	repeats: number;
	tokens: number;
};

// --- deterministic evidence: pure functions, no model call, no I/O ---

/** The banned phrases this text uses, each with its count. */
export function fillers(text: string): Record<string, number> {
	const found: Record<string, number> = {};
	for (const phrase of FILLERS) {
		const hits = text.match(new RegExp(`\\b${phrase}\\b`, "gi"));
		if (hits?.length) found[phrase] = hits.length;
	}
	return found;
}

export function tally(found: Record<string, number>): number {
	return Object.values(found).reduce((sum, hits) => sum + hits, 0);
}

/** Sentence-ish spans: blank lines, line breaks and sentence ends all split. */
export function spans(text: string): string[] {
	return text
		.split(/\n\s*\n|(?<=[.!?])\s+|\n/)
		.map((span) => span.trim())
		.filter(Boolean);
}

function words(span: string): Set<string> {
	const clean = span.toLowerCase().replace(/[^\p{L}\p{N}\s]/gu, "");
	return new Set(clean.split(/\s+/).filter(Boolean));
}

function overlap(a: Set<string>, b: Set<string>): number {
	if (a.size === 0 && b.size === 0) return 1;
	let shared = 0;
	for (const word of a) if (b.has(word)) shared += 1;
	return shared / (a.size + b.size - shared);
}

/** Spans beyond the first in each group of near-duplicate spans. */
export function repeats(text: string): number {
	const sets = spans(text).map(words);
	const parent = sets.map((_set, index) => index);
	const root = (index: number): number => (parent[index] === index ? index : (parent[index] = root(parent[index])));
	for (let i = 0; i < sets.length; i += 1) {
		for (let j = i + 1; j < sets.length; j += 1) {
			if (overlap(sets[i], sets[j]) >= REPEAT_OVERLAP) parent[root(j)] = root(i);
		}
	}
	return sets.length - new Set(sets.map((_set, index) => root(index))).size;
}

/** chars, estimated tokens and zlib deflate ratio; a high ratio means dense. */
export function density(text: string): { chars: number; tokens: number; ratio: number } {
	const chars = text.length;
	const tokens = Math.round(chars * TOKENS_PER_CHAR);
	const ratio = chars === 0 ? 0 : deflateSync(Buffer.from(text)).length / chars;
	return { chars, tokens, ratio };
}

export function evidence(text: string): Evidence {
	const { chars, tokens } = density(text);
	return { chars, tokens, fillers: tally(fillers(text)), repeats: repeats(text) };
}

/** 1,840 - grouped by three, so a size reads at a glance. */
export function thousands(count: number): string {
	return String(count).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// --- capture: the request, the tool-call trace and the blocks ---

/** The text of a message content, whether it is a string or text blocks. */
export function textOf(content: unknown): string {
	if (typeof content === "string") return content;
	if (!Array.isArray(content)) return "";
	let text = "";
	for (const block of content) {
		if (!block || typeof block !== "object") continue;
		const candidate = block as { type?: string; text?: unknown };
		if (candidate.type === "text" && typeof candidate.text === "string") text += candidate.text;
	}
	return text;
}

/** One call's arguments as a short plain line: `voice_score.ts`, not JSON. */
export function argLine(args: unknown): string {
	if (typeof args === "string") return args;
	if (!args || typeof args !== "object") return "";
	return Object.entries(args as Record<string, unknown>)
		.map(([key, value]) => (typeof value === "string" ? value : `${key}=${JSON.stringify(value)}`))
		.join(" ");
}

export function callsOf(content: unknown): { id?: string; name?: string; arguments?: unknown }[] {
	if (!Array.isArray(content)) return [];
	const calls: { id?: string; name?: string; arguments?: unknown }[] = [];
	for (const block of content) {
		if (!block || typeof block !== "object") continue;
		const candidate = block as { type?: string; id?: string; name?: string; arguments?: unknown };
		if (candidate.type === "toolCall") calls.push(candidate);
	}
	return calls;
}

/** Record one call; oldest dropped beyond TRACE_MAX. */
export function addCall(trace: Trace[], call: { id?: string; name?: string; arguments?: unknown }): void {
	if (typeof call.name !== "string") return;
	trace.push({
		id: typeof call.id === "string" ? call.id : "",
		name: call.name,
		args: argLine(call.arguments).slice(0, ARGS_MAX),
	});
	if (trace.length > TRACE_MAX) trace.shift();
}

/** Attach a result's size to the call that asked for it. */
export function addResult(trace: Trace[], result: { toolCallId?: string; content?: unknown }): void {
	if (typeof result.toolCallId !== "string" || !result.toolCallId) return;
	const call = trace.find((entry) => entry.id === result.toolCallId && entry.chars === undefined);
	if (call) call.chars = textOf(result.content).length;
}

/** read voice_score.ts (1,840 chars result) - one line per call. */
export function traceLine(call: Trace): string {
	const size = call.chars === undefined ? "" : ` (${thousands(call.chars)} chars result)`;
	return `${call.name} ${call.args}${size}`.trim();
}

export function traceText(trace: Trace[]): string {
	return trace.map(traceLine).join("\n");
}

/** Thinking blocks plus the run's last substantive text, in that order. */
export function blocksOf(content: unknown): { think: Block[]; reply?: Block } {
	if (!Array.isArray(content)) return { think: [] };
	const think: Block[] = [];
	let text = "";
	for (const block of content) {
		if (!block || typeof block !== "object") continue;
		const candidate = block as { type?: string; thinking?: unknown; text?: unknown };
		if (candidate.type === "thinking" && typeof candidate.thinking === "string") {
			if (candidate.thinking.length >= FLOOR) think.push({ kind: "think", text: candidate.thinking });
		} else if (candidate.type === "text" && typeof candidate.text === "string") {
			text += candidate.text;
		}
	}
	return { think, reply: text.length >= FLOOR ? { kind: "reply", text } : undefined };
}

// --- the Jev call ---

/** One voice, one efficiency and one gate question per block. */
export function buildQuestions(blocks: Block[]): Record<string, Question> {
	const questions: Record<string, Question> = {};
	blocks.forEach((block, index) => {
		questions[`b${index}`] = {
			type: "score",
			instructions:
				`How closely does \`b${index}\` match telegraph voice? ` +
				"Judge only the writing, not whether the reasoning is correct.",
			criteria: CRITERIA,
		};
		questions[`e${index}`] = {
			type: "score",
			instructions:
				`How token-efficient is \`b${index}\` for this task? ` +
				"Judge only the text, not whether the reasoning is correct.",
			criteria: EFFICIENCY_CRITERIA,
		};
		questions[`g${index}`] = {
			type: "bool",
			instructions:
				block.kind === "think"
					? `Does the thinking in \`b${index}\` avoid circularity?`
					: `Does the reply in \`b${index}\` deliver everything this turn learned that the user needs, judged against the request and the trace?`,
			criteria: GATE[block.kind],
		};
	});
	return questions;
}

export function stateOf(blocks: Block[], request = "", trace: Trace[] = []): Record<string, string> {
	const state: Record<string, string> = { request, trace: traceText(trace) };
	blocks.forEach((block, index) => {
		state[`b${index}`] = block.text;
	});
	return state;
}

/** The gate multiplies the score, so an omission cannot be paid for with brevity. */
export function efficiency(score: number, gate: number): number {
	return Math.round(score * gate * 100) / 100;
}

// --- display and ledger ---

export function readEnabled(path = CONFIG_PATH): boolean {
	try {
		const config = JSON.parse(readFileSync(path, "utf8")) as { enabled?: unknown };
		return config.enabled !== false;
	} catch {
		return true;
	}
}

export function writeEnabled(enabled: boolean, path = CONFIG_PATH): void {
	writeFileSync(path, `${JSON.stringify({ enabled }, null, 2)}\n`);
}

function tier(score: number, pass: number, good: number): "low" | "mid" | "high" {
	if (score >= good) return "high";
	if (score >= pass) return "mid";
	return "low";
}

const COLORS = { low: "error", mid: "warning", high: "success" } as const;

export function band(score: number): { label: string; color: "success" | "warning" | "error" } {
	const names = { low: "verbose", mid: "passable", high: "telegraph" } as const;
	const where = tier(score, PASS, GOOD);
	return { label: names[where], color: COLORS[where] };
}

export function effBand(score: number): { label: string; color: "success" | "warning" | "error" } {
	const names = { low: "wasteful", mid: "workable", high: "load-bearing" } as const;
	const where = tier(score, EFF_PASS, EFF_GOOD);
	return { label: names[where], color: COLORS[where] };
}

/** The scores of one kind, in order, capped for display. */
export function ofKind<T extends { kind: "think" | "reply" }>(scores: T[], kind: T["kind"]): T[] {
	return scores.filter((score) => score.kind === kind);
}

function summary<T extends { kind: "think" | "reply" }>(
	label: string,
	rows: T[],
	value: (row: T) => number,
	color: (row: T) => { color: "success" | "warning" | "error" },
	fg: (color: "dim" | "success" | "warning" | "error", text: string) => string,
): string {
	const parts: string[] = [];
	for (const kind of ["think", "reply"] as const) {
		const group = ofKind(rows, kind);
		if (group.length === 0) continue;
		const shown = group.slice(0, SHOWN).map((row) => fg(color(row).color, `${value(row).toFixed(1)}/${SCALE}`));
		if (group.length > SHOWN) shown.push(fg("dim", `+${group.length - SHOWN}`));
		parts.push(`${fg("dim", kind)} ${shown.join(" ")}`);
	}
	return `${fg("dim", label.padEnd(LABEL))} ${parts.join("  ") || "nothing scored"}`;
}

function detail(score: EfficiencyScore): string {
	const { evidence: proof } = score;
	const value = efficiency(score.score, score.gate);
	return (
		`${score.kind} ${effBand(value).label} ${value.toFixed(1)}/${SCALE} ` +
		`gate ${score.gate.toFixed(2)} conf ${score.confidence.toFixed(2)} ` +
		`fillers ${proof.fillers} repeats ${proof.repeats} ${proof.chars} chars ${proof.tokens} tokens`
	);
}

/**
 * The lines the entry draws. `fg` is the theme's colour function, passed in so
 * the text can be checked without a terminal.
 */
export function renderLines(
	data: VoiceScoreData,
	expanded: boolean,
	fg: (color: "dim" | "success" | "warning" | "error", text: string) => string,
): string[] {
	if (data.error) return [fg("warning", `voice score unavailable: ${data.error}`)];
	const voices = data.scores ?? [];
	const tokens = data.efficiency ?? [];
	const lines = [summary("voice", voices, (score) => score.score, band, fg)];
	if (voices.length > 0 || tokens.length > 0) {
		lines.push(
			summary(
				"tokens",
				tokens,
				(score) => efficiency(score.score, score.gate),
				(score) => effBand(efficiency(score.score, score.gate)),
				fg,
			),
		);
	}
	if (expanded) {
		for (const voice of voices) {
			lines.push(
				fg("dim", `  ${voice.kind} ${band(voice.score).label} conf ${voice.confidence.toFixed(2)} (${voice.score.toFixed(2)}/${SCALE})`),
			);
			for (const token of tokens) {
				if (token.index === voice.index) lines.push(fg("dim", `  ${detail(token)}`));
			}
		}
		for (const token of tokens) {
			if (!voices.some((voice) => voice.index === token.index)) lines.push(fg("dim", `  ${detail(token)}`));
		}
	}
	return lines;
}

function pad(value: number): string {
	return String(Math.abs(value)).padStart(2, "0");
}

/** Local ISO 8601 with its offset: 2026-10-04T04:40:00-07:00. */
export function stamp(date = new Date()): string {
	const offset = -date.getTimezoneOffset();
	const sign = offset >= 0 ? "+" : "-";
	return (
		`${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
		`T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}` +
		`${sign}${pad(Math.floor(Math.abs(offset) / 60))}:${pad(Math.abs(offset) % 60)}`
	);
}

/** One row per block that got an efficiency score, for calibration later. */
export function ledgerRows(data: VoiceScoreData, session: string, date = new Date()): LedgerRow[] {
	const rows: LedgerRow[] = [];
	for (const token of data.efficiency ?? []) {
		const voice = (data.scores ?? []).find((score) => score.index === token.index);
		rows.push({
			at: stamp(date),
			session,
			kind: token.kind,
			voice: voice ? voice.score : null,
			efficiency: Math.round(efficiency(token.score, token.gate) * 10) / 10,
			gate: Math.round(token.gate * 100) / 100,
			chars: token.evidence.chars,
			fillers: token.evidence.fillers,
			repeats: token.evidence.repeats,
			tokens: token.evidence.tokens,
		});
	}
	return rows;
}

/** Silent on failure: a bad ledger path must never break a turn. */
export function appendLedger(rows: LedgerRow[], path = LEDGER_PATH): void {
	if (rows.length === 0) return;
	try {
		mkdirSync(dirname(path), { recursive: true });
		for (const row of rows) writeFileSync(path, `${JSON.stringify(row)}\n`, { flag: "a" });
	} catch {
		// nothing to report: the ledger is a convenience, not a contract
	}
}

export default function (pi: ExtensionAPI) {
	let enabled = readEnabled();
	let think: Block[] = [];
	let reply: Block | undefined;
	let request = "";
	let trace: Trace[] = [];

	function reset(): void {
		think = [];
		reply = undefined;
		request = "";
		trace = [];
	}

	pi.on("session_start", () => {
		enabled = readEnabled();
		reset();
	});
	pi.on("agent_start", reset);

	pi.on("message_end", (event) => {
		if (!enabled) return;
		const message = event.message as { role?: string; content?: unknown; toolCallId?: string };
		if (message.role === "user") {
			const text = textOf(message.content);
			if (text) request = text.slice(0, REQUEST_MAX);
			return;
		}
		if (message.role === "toolResult") {
			addResult(trace, message);
			return;
		}
		if (message.role !== "assistant") return;
		const found = blocksOf(message.content);
		think.push(...found.think);
		// only the run's last substantive text is the reply; earlier text is narration
		if (found.reply) reply = found.reply;
		for (const call of callsOf(message.content)) addCall(trace, call);
	});

	pi.registerEntryRenderer<VoiceScoreData>("voice-score", (entry, { expanded }, theme) => {
		const lines = renderLines(entry.data ?? { scores: [], at: 0 }, expanded, (color, text) =>
			theme.fg(color, text),
		);
		return {
			render: () => lines,
			invalidate: () => {},
		};
	});

	pi.registerCommand("voice-score", {
		description: "Turn Jev scoring of thinking, the reply and the run's spend on or off, or show its state",
		handler: async (args, ctx) => {
			const word = args.trim().toLowerCase();
			if (word === "on" || word === "off") {
				enabled = word === "on";
				writeEnabled(enabled);
				if (!enabled) reset();
			}
			const detail = enabled
				? `voice pass ${PASS} telegraph ${GOOD}, tokens pass ${EFF_PASS} load-bearing ${EFF_GOOD}`
				: "no Jev call is spent";
			ctx.ui.notify(`voice score: ${enabled ? "on" : "off"} - ${detail}`, "info");
		},
	});

	pi.on("agent_before_settle", async (_event, ctx) => {
		if (!enabled) return;
		const blocks = [...think, ...(reply ? [reply] : [])];
		const asked = { request, trace: trace.slice() };
		reset();
		if (blocks.length === 0) return;

		if (process.env.PI_VOICE_TRACE === "1") {
			process.stderr.write(`voice trace: request ${JSON.stringify(asked.request)}\n${traceText(asked.trace)}\n`);
		}

		const jev = ctx.modelRegistry.findOfType("classifier", "typesafe", "jev-latest");
		if (!jev) return;

		// A thinking block is judged against the calls of its run, including ones
		// made after it: only the later calls show whether the thinking was needed.
		const result = await ctx.modelRegistry.classify(jev, {
			state: stateOf(blocks, asked.request, asked.trace),
			questions: buildQuestions(blocks),
		});
		const data: VoiceScoreData = { scores: [], efficiency: [], at: Date.now() };
		if (result.stopReason !== "stop") {
			data.error = result.errorMessage ?? result.stopReason;
		} else {
			blocks.forEach((block, index) => {
				const voice = result.answers[`b${index}`];
				if (voice?.type === "score") {
					data.scores.push({ kind: block.kind, index, score: voice.score, confidence: voice.confidence });
				}
				const spend = result.answers[`e${index}`];
				const gate = result.answers[`g${index}`];
				if (spend?.type === "score" && gate?.type === "bool") {
					data.efficiency?.push({
						kind: block.kind,
						index,
						score: spend.score,
						gate: gate.probability,
						confidence: spend.confidence,
						evidence: evidence(block.text),
					});
				}
			});
		}
		pi.appendEntry<VoiceScoreData>("voice-score", data);
		appendLedger(ledgerRows(data, process.env.PI_SESSION_ID ?? ""));
	});
}