/**
 * voice score: Jev reads a turn's thinking, its reply and what it spent - on
 * demand, never on its own.
 *
 * The telegraph rule covers thinking as well as replies, but a rule with no
 * signal is a wish. This is the signal: `/voice-score` scores the last turn,
 * `/voice-score -0` scores every turn of the session, one Jev call per run -
 * voice and token-efficiency, two questions per block - and each scored run is
 * appended as a session entry, drawn as two lines, and written to a ledger.
 *
 * The entry draws two lines under the run: `voice  think 2.8/3  reply 2.2/3`
 * and `tokens think 1.4/3  reply 2.6/3`; both scales run 0 to 3, so every
 * number carries its max. Each block's token efficiency is Jev's 0-3
 * score for the block times `p(gate)`, the probability that the block delivers
 * what the turn needed (a reply) or avoids circularity (thinking), so an
 * omission cannot be paid for with brevity.
 *
 * Display only. It never nudges, blocks or rewrites, and the entry is not sent
 * to the model, so the whole feature costs one Jev call per run asked about and
 * no context: a turn nobody asks about is free, and nothing is scored on its
 * own. History comes from `ctx.sessionManager.getBranch()`, thinking blocks
 * included, which is why the command can score a run that finished before it
 * was typed. A run too long for one call is split at CALL_CHAR_BUDGET, so a 59
 * block run costs several calls rather than a 400; the entry says how many.
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
 * Usage: /voice-score for the last turn, /voice-score -0 for the session.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { deflateSync } from "node:zlib";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

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
	/** What a run too long for one call has to say about itself. */
	note?: string;
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
	// punctuation is a boundary, not a letter: a path tokenises into its parts
	return new Set(span.toLowerCase().split(/[^\p{L}\p{N}]+/u).filter(Boolean));
}

/** Jaccard overlap of two texts' word sets, 0-1; call duplication reads this. */
export function similarity(a: string, b: string): number {
	return overlap(words(a), words(b));
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

/** One run as the transcript holds it: the ask, its calls and its blocks. */
export type Run = { request: string; trace: Trace[]; think: Block[]; reply?: Block };

/** The blocks a run is judged on, in the order the questions name them. */
export function blocksOfRun(run: Run): Block[] {
	return [...run.think, ...(run.reply ? [run.reply] : [])];
}

/**
 * A session branch folded back into runs, by the same rules the message_end
 * handler used to apply live: a user message opens a run, an assistant message
 * adds its thinking, its calls and its last substantive text, and a tool result
 * sizes the call that asked for it.
 *
 * Only runs with something long enough to judge are kept, and a non-message
 * entry - a model change, a compaction summary - is skipped.
 */
export function runsOf(entries: readonly unknown[]): Run[] {
	const runs: Run[] = [];
	let run: Run | undefined;
	for (const entry of entries) {
		if (!entry || typeof entry !== "object") continue;
		const candidate = entry as {
			type?: string;
			message?: { role?: string; content?: unknown; toolCallId?: string };
		};
		if (candidate.type !== "message" || !candidate.message) continue;
		const message = candidate.message;
		if (message.role === "user") {
			run = { request: "", trace: [], think: [] };
			runs.push(run);
			const text = textOf(message.content);
			if (text) run.request = text.slice(0, REQUEST_MAX);
			continue;
		}
		if (!run) continue;
		if (message.role === "toolResult") {
			addResult(run.trace, message);
			continue;
		}
		if (message.role !== "assistant") continue;
		const found = blocksOf(message.content);
		run.think.push(...found.think);
		// only the run's last substantive text is the reply; earlier text is narration
		if (found.reply) run.reply = found.reply;
		for (const call of callsOf(message.content)) addCall(run.trace, call);
	}
	return runs.filter((candidate) => blocksOfRun(candidate).length > 0);
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

/**
 * Jev's window is 64,000 tokens and one call carries the state plus three
 * questions per block. Measured 2026-10-06 on a 59-block run: state 138,080
 * chars and questions 70,713 chars - ~52,000 tokens at four chars a token, and
 * over the window at the tokenizer's real density, which the API answered with
 * `max_tokens_exceeded`. One call is therefore budgeted well inside it, and a
 * run longer than the budget is split across calls instead of being trimmed.
 */
export const CALL_CHAR_BUDGET = 64000;

/**
 * The blocks of a run, grouped so each group's state and questions fit one
 * Jev call. Greedy and in order, so a group is a contiguous slice of the run.
 * The questions are measured per block rather than guessed: they carry the
 * criteria, and they are large enough to change where the cut lands.
 */
export function chunksOf(blocks: Block[], request = "", trace: Trace[] = []): Block[][] {
	const base = stateChars(stateOf([], request, trace));
	const chunks: Block[][] = [];
	let current: Block[] = [];
	let size = base;
	for (const block of blocks) {
		const cost = block.text.length + questionChars(block);
		if (current.length > 0 && size + cost > CALL_CHAR_BUDGET) {
			chunks.push(current);
			current = [];
			size = base;
		}
		current.push(block);
		size += cost;
	}
	if (current.length > 0) chunks.push(current);
	return chunks;
}

function stateChars(state: Record<string, string>): number {
	let total = 0;
	for (const [key, value] of Object.entries(state)) total += key.length + value.length;
	return total;
}

/** The three questions one block adds to the call, criteria and instructions included. */
function questionChars(block: Block): number {
	let total = 0;
	for (const [key, value] of Object.entries(buildQuestions([block]))) {
		total += key.length + JSON.stringify(value).length;
	}
	return total;
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

/** The good/mid/low cut every score line shares. */
export function tier(score: number, pass: number, good: number): "low" | "mid" | "high" {
	if (score >= good) return "high";
	if (score >= pass) return "mid";
	return "low";
}

export const COLORS = { low: "error", mid: "warning", high: "success" } as const;

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
	if (data.note) lines.push(fg("dim", data.note));
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
export function appendLines(rows: object[], path: string): void {
	if (rows.length === 0) return;
	try {
		mkdirSync(dirname(path), { recursive: true });
		for (const row of rows) writeFileSync(path, `${JSON.stringify(row)}\n`, { flag: "a" });
	} catch {
		// nothing to report: the ledger is a convenience, not a contract
	}
}

/** Append the rows to the shared voice_score ledger, creating its directory. */
export function appendLedger(rows: LedgerRow[], path = LEDGER_PATH): void {
	appendLines(rows, path);
}

export default function (pi: ExtensionAPI) {
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
		description: "Score the last turn's voice and tokens with Jev, or every turn of this session with -0",
		handler: async (args, ctx) => {
			const word = args.trim();
			if (word !== "" && word !== "-0") {
				ctx.ui.notify(`voice score: no argument scores the last turn, -0 the session, got ${word}`, "warning");
				return;
			}
			const runs = runsOf(ctx.sessionManager.getBranch());
			const wanted = word === "-0" ? runs : runs.slice(-1);
			if (wanted.length === 0) {
				ctx.ui.notify("voice score: nothing in this session ran long enough to judge", "info");
				return;
			}
			let done = 0;
			for (const run of wanted) {
				if (await scoreRun(pi, ctx, run)) done += 1;
			}
			ctx.ui.notify(`voice score: ${done} of ${wanted.length} runs scored by Jev`, "info");
		},
	});
}

/**
 * One Jev call for one run: score it, append the entry, write its ledger rows.
 * Undefined when the run held nothing long enough to judge, so the caller's
 * count stays honest. A missing classifier is an entry like any other, drawn as
 * `voice score unavailable`, rather than a silent nothing.
 */
async function scoreRun(
	pi: ExtensionAPI,
	ctx: ExtensionContext,
	run: Run,
): Promise<VoiceScoreData | undefined> {
	const blocks = blocksOfRun(run);
	if (blocks.length === 0) return undefined;

	if (process.env.PI_VOICE_TRACE === "1") {
		process.stderr.write(`voice trace: request ${JSON.stringify(run.request)}\n${traceText(run.trace)}\n`);
	}

	const data: VoiceScoreData = { scores: [], efficiency: [], at: Date.now() };
	const jev = ctx.modelRegistry.findOfType("classifier", "typesafe", "jev-latest");
	if (!jev) {
		data.error = "no Jev classifier in this session";
	} else {
		const chunks = chunksOf(blocks, run.request, run.trace);
		const failed: string[] = [];
		let index = 0;
		for (const chunk of chunks) {
			// A thinking block is judged against the calls of its run, including ones
			// made after it: only the later calls show whether the thinking was needed.
			const result = await ctx.modelRegistry.classify(jev, {
				state: stateOf(chunk, run.request, run.trace),
				questions: buildQuestions(chunk),
			});
			if (result.stopReason !== "stop") {
				failed.push(result.errorMessage ?? result.stopReason);
			} else {
				chunk.forEach((block, local) => {
					const voice = result.answers[`b${local}`];
					if (voice?.type === "score") {
						data.scores.push({
							kind: block.kind,
							index: index + local,
							score: voice.score,
							confidence: voice.confidence,
						});
					}
					const spend = result.answers[`e${local}`];
					const gate = result.answers[`g${local}`];
					if (spend?.type === "score" && gate?.type === "bool") {
						data.efficiency?.push({
							kind: block.kind,
							index: index + local,
							score: spend.score,
							gate: gate.probability,
							confidence: spend.confidence,
							evidence: evidence(block.text),
						});
					}
				});
			}
			index += chunk.length;
		}
		// Every call failing is the run failing; some of them failing is a partial
		// score, and the note says so rather than letting the line look whole.
		if (failed.length === chunks.length) {
			data.error = failed[0];
		} else if (failed.length > 0) {
			data.note = `${failed.length} of ${chunks.length} calls failed: ${failed[0]}`;
		} else if (chunks.length > 1) {
			data.note = `${chunks.length} calls, one per ${Math.ceil(blocks.length / chunks.length)} blocks`;
		}
	}
	pi.appendEntry<VoiceScoreData>("voice-score", data);
	appendLedger(ledgerRows(data, process.env.PI_SESSION_ID ?? ""));
	return data;
}