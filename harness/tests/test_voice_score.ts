/**
 * check for voice_score.ts. Run:
 *   timeout 180 node --experimental-strip-types harness/tests/test_voice_score.ts
 */
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import voiceScore, {
	addCall,
	addResult,
	appendLedger,
	argLine,
	band,
	blocksOf,
	blocksOfRun,
	buildQuestions,
	CALL_CHAR_BUDGET,
	callsOf,
	chunksOf,
	CRITERIA,
	density,
	EFFICIENCY_CRITERIA,
	effBand,
	EFF_GOOD,
	EFF_PASS,
	efficiency,
	evidence,
	FILLERS,
	fillers,
	FLOOR,
	GOOD,
	ledgerRows,
	ofKind,
	PASS,
	renderLines,
	repeats,
	REQUEST_MAX,
	runsOf,
	SHOWN,
	stamp,
	stateOf,
	tally,
	textOf,
	thousands,
	TRACE_MAX,
	traceLine,
	traceText,
	type EfficiencyScore,
	type VoiceScore,
	type VoiceScoreData,
} from "../extensions/voice_score.ts";

// a theme-free colour function: the raw text is what matters here
const plain = (_color: string, text: string): string => text;

// the display bands, at their boundaries
assert.equal(band(PASS - 0.01).label, "verbose");
assert.equal(band(PASS - 0.01).color, "error");
assert.equal(band(PASS).label, "passable");
assert.equal(band(PASS).color, "warning");
assert.equal(band(GOOD - 0.01).color, "warning");
assert.equal(band(GOOD).label, "telegraph");
assert.equal(band(GOOD).color, "success");
assert.ok(PASS < GOOD, "PASS must sit below GOOD");
assert.ok(EFF_PASS < EFF_GOOD, "EFF_PASS must sit below EFF_GOOD");
assert.equal(effBand(EFF_PASS - 0.01).label, "wasteful");
assert.equal(effBand(EFF_PASS - 0.01).color, "error");
assert.equal(effBand(EFF_PASS).label, "workable");
assert.equal(effBand(EFF_PASS).color, "warning");
assert.equal(effBand(EFF_GOOD - 0.01).color, "warning");
assert.equal(effBand(EFF_GOOD).label, "load-bearing");
assert.equal(effBand(EFF_GOOD).color, "success");

// --- the deterministic evidence: a positive, a negative and the empty string ---

// fillers: found with counts, absent when none, nothing on an empty string
const fillerText = "Note that this is really just very simple, and note that it is worth noting plainly.";
const found = fillers(fillerText);
assert.deepEqual(found, { "it is worth noting": 1, "note that": 2, just: 1, really: 1, very: 1 });
assert.deepEqual(fillers("Read the file. Ship it."), {});
assert.deepEqual(fillers(""), {});
assert.equal(tally(found), 6);
assert.ok(FILLERS.includes("basically"), "the banned list travels with the rule");

// repeats: near-duplicates count, distinct spans do not, empty is zero
assert.equal(
	repeats("The tests always pass here.\nThe file is read.\nThe tests always pass."),
	1,
	"two spans at the 0.8 overlap are one repeat",
);
assert.equal(repeats("First fact here.\nSecond thing different.\nThird unrelated line."), 0);
assert.equal(repeats(""), 0);

// density: chars and tokens track length, repetition deflates smaller than prose
const flat = "one two three four ".repeat(20);
const varied = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima ".repeat(2);
assert.equal(density("").chars, 0);
assert.equal(density("").tokens, 0);
assert.equal(density("").ratio, 0);
assert.equal(density(flat).chars, flat.length);
assert.equal(density(flat).tokens, Math.round(flat.length / 4));
assert.ok(density(flat).ratio < density(varied).ratio, "repetition is the less dense text");

// evidence: the same block, measured
assert.deepEqual(evidence("Really just a plain line."), { chars: 25, tokens: 6, fillers: 2, repeats: 0 });

// 1,840 - grouped for reading
assert.equal(thousands(0), "0");
assert.equal(thousands(1840), "1,840");
assert.equal(thousands(1234567), "1,234,567");

// --- capture ---

assert.equal(textOf("plain"), "plain");
assert.equal(textOf([{ type: "text", text: "a" }, { type: "image" }, { type: "text", text: "b" }]), "ab");
assert.equal(textOf(undefined), "");
assert.equal(argLine({ path: "voice_score.ts" }), "voice_score.ts");
assert.equal(argLine({ command: "rg -n x", timeout: 30 }), "rg -n x timeout=30");
assert.equal(argLine("plain"), "plain");
assert.equal(argLine(undefined), "");
const calls = callsOf([{ type: "text", text: "x" }, { type: "toolCall", id: "1", name: "read", arguments: { path: "a" } }]);
assert.equal(calls.length, 1);
assert.equal(calls[0].name, "read");

const trace = [];
for (let i = 0; i < TRACE_MAX + 2; i += 1) addCall(trace, { id: `c${i}`, name: "read", arguments: { path: `f${i}.ts` } });
assert.equal(trace.length, TRACE_MAX, "the trace is capped");
assert.equal(trace[0].args, "f2.ts", "oldest dropped first");
addResult(trace, { toolCallId: "c2", content: "x".repeat(1840) });
assert.equal(trace[0].chars, 1840);
assert.equal(traceLine(trace[0]), "read f2.ts (1,840 chars result)");
assert.equal(traceLine({ id: "c", name: "bash", args: "ls" }), "bash ls");
assert.match(traceText(trace), /^read f2\.ts \(1,840 chars result\)/);
assert.equal(traceText([]), "");
assert.doesNotThrow(() => addResult(trace, { toolCallId: "gone", content: "x" }));

// blocksOf: thinking kept, short blocks dropped, text concatenated into one reply
const long = "x".repeat(FLOOR);
const short = "x".repeat(FLOOR - 1);

const content = [
	{ type: "thinking", thinking: long },
	{ type: "thinking", thinking: short },
	{ type: "text", text: "first half " },
	{ type: "toolCall", id: "1" },
	{ type: "text", text: "y".repeat(FLOOR) },
];
const blocks = blocksOf(content);
assert.equal(blocks.think.length, 1, "short thinking is not worth judging");
assert.equal(blocks.think[0].text, long);
assert.equal(blocks.reply?.text.length, "first half ".length + FLOOR, "text blocks join into one reply");
assert.equal(blocks.reply?.kind, "reply");
assert.deepEqual(blocksOf(undefined), { think: [] });
assert.deepEqual(blocksOf([{ type: "thinking", thinking: short }]).think, []);
assert.equal(blocksOf([{ type: "text", text: short }]).reply, undefined);

// three questions per block, each naming its own state path and kind
const all = blocks.think.concat(blocks.reply ? [blocks.reply] : []);
const questions = buildQuestions(all);
assert.deepEqual(Object.keys(questions), ["b0", "e0", "g0", "b1", "e1", "g1"]);
assert.equal(questions.e0.type, "score");
assert.deepEqual(questions.e0.criteria, EFFICIENCY_CRITERIA);
assert.match(questions.e1.instructions, /How token-efficient is `b1` for this task\? Judge only the text, not whether the reasoning is correct\./);
assert.deepEqual(questions.b0.criteria, CRITERIA);
assert.equal(questions.g0.type, "bool");
assert.deepEqual(questions.g0.criteria, {
	true: "each step advances the reasoning, nothing re-derived",
	false: "it repeats or re-derives a point it already settled",
});
assert.deepEqual(questions.g1.criteria, { true: "it covers what the task needed", false: "something needed is missing" });

// the state: request and trace first, then one field per block
const state = stateOf(all, "the request", trace);
assert.deepEqual(Object.keys(state), ["request", "trace", "b0", "b1"]);
assert.equal(state.request, "the request");
assert.match(state.trace, /^read f2\.ts/);
assert.equal(state.b0, long);
assert.equal(stateOf([{ kind: "think", text: short }]).request, "");

// the gate multiplies the score
assert.equal(efficiency(3, 1), 3);
assert.equal(efficiency(2.6, 0.95), 2.47);
assert.equal(efficiency(0, 1), 0);

// a scratch directory for the ledger below
const dir = mkdtempSync(join(tmpdir(), "voice-score-"));

// chunksOf: a run that fits one call stays one call, a long run is split, and
// no chunk carries more than the budget
const one = chunksOf([{ kind: "think", text: long }], "ask", []);
assert.equal(one.length, 1, "a short run is one call");
assert.equal(one[0].length, 1);
const longRun = Array.from({ length: 40 }, (_value, index) => ({ kind: "think" as const, text: `${index} `.repeat(2000) }));
const split = chunksOf(longRun, "ask", []);
assert.ok(split.length > 1, `40 large blocks split (got ${split.length})`);
assert.equal(
	split.reduce((sum, chunk) => sum + chunk.length, 0),
	longRun.length,
	"every block lands in exactly one chunk, none dropped",
);
for (const chunk of split) {
	const size =
		Object.entries(stateOf(chunk, "ask", [])).reduce((sum, [key, value]) => sum + key.length + value.length, 0) +
		Object.entries(buildQuestions(chunk)).reduce((sum, [key, value]) => sum + key.length + JSON.stringify(value).length, 0);
	assert.ok(size <= CALL_CHAR_BUDGET, `chunk of ${chunk.length} blocks is ${size} chars, over the budget`);
}
assert.equal(chunksOf([], "ask", []).length, 0, "nothing to score, no call");

// runsOf: a session branch folded back into runs, the way the live capture
// read the same messages before the command could ask for them
const branch = [
	{ type: "session_info", name: "not a message" },
	{ type: "message", message: { role: "user", content: "first ask" } },
	{
		type: "message",
		message: {
			role: "assistant",
			content: [
				{ type: "thinking", thinking: long },
				{ type: "toolCall", id: "t1", name: "read", arguments: { path: "a.ts" } },
				{ type: "text", text: long },
			],
		},
	},
	{ type: "message", message: { role: "toolResult", toolCallId: "t1", content: "x".repeat(1840) } },
	{ type: "message", message: { role: "user", content: "second ask" } },
	{ type: "message", message: { role: "assistant", content: [{ type: "text", text: "y".repeat(FLOOR) }] } },
	{ type: "message", message: { role: "user", content: "too short to judge" } },
	{ type: "message", message: { role: "assistant", content: [{ type: "text", text: short }] } },
];
const runs = runsOf(branch);
assert.equal(runs.length, 2, "a run with nothing long enough to judge is dropped");
assert.equal(runs[0].request, "first ask");
assert.equal(runs[0].think.length, 1, "short thinking is left out of the run too");
assert.equal(runs[0].reply?.text, long);
assert.deepEqual(blocksOfRun(runs[0]).map((block) => block.kind), ["think", "reply"]);
assert.equal(runs[0].trace.length, 1, "the call is kept, the result attached to it");
assert.equal(traceLine(runs[0].trace[0]), "read a.ts (1,840 chars result)");
assert.equal(runs[1].request, "second ask");
assert.equal(runs[1].think.length, 0);
assert.equal(runs[1].trace.length, 0);
assert.deepEqual(runsOf([]), []);
assert.deepEqual(runsOf([{ type: "message", message: { role: "assistant", content: [] } }]), [], "no request, no run");
const capped = runsOf([
	{ type: "message", message: { role: "user", content: "z".repeat(REQUEST_MAX + 50) } },
	{ type: "message", message: { role: "assistant", content: [{ type: "text", text: long }] } },
]);
assert.equal(capped[0].request.length, REQUEST_MAX, "the request is capped");

// --- the drawn lines ---

const scores: VoiceScore[] = [
	{ kind: "think", index: 0, score: 0.9, confidence: 0.8 },
	{ kind: "reply", index: 1, score: 2.6, confidence: 0.6 },
	{ kind: "think", index: 2, score: 2.1, confidence: 0.5 },
];
const proof = { chars: 1840, tokens: 460, fillers: 3, repeats: 1 };
const spend: EfficiencyScore[] = [
	{ kind: "think", index: 0, score: 1.2, gate: 0.7, confidence: 0.5, evidence: proof },
	{ kind: "reply", index: 1, score: 2.7, gate: 0.95, confidence: 0.6, evidence: proof },
];
const data: VoiceScoreData = { scores, efficiency: spend, at: 0 };

assert.deepEqual(
	ofKind(scores, "think").map((s) => s.score),
	[0.9, 2.1],
);
assert.deepEqual(ofKind(scores, "reply").length, 1);

const line = renderLines(data, false, plain);
assert.deepEqual(line, ["voice  think 0.9/3 2.1/3  reply 2.6/3", "tokens think 0.8/3  reply 2.6/3"]);
assert.deepEqual(renderLines({ scores: [], at: 0 }, false, plain), ["voice  nothing scored"]);
assert.match(renderLines({ scores: [], error: "aborted", at: 0 }, false, plain)[0], /unavailable: aborted/);

// a voice score with no efficiency score still draws the empty tokens line
const voiceOnly: VoiceScoreData = { scores, at: 0 };
assert.deepEqual(renderLines(voiceOnly, false, plain), ["voice  think 0.9/3 2.1/3  reply 2.6/3", "tokens nothing scored"]);
assert.deepEqual(renderLines({ scores: [], efficiency: [], at: 0 }, false, plain), ["voice  nothing scored"]);

// expanded adds the voice line and the measured evidence per block
const expanded = renderLines(data, true, plain);
assert.equal(expanded.length, 2 + scores.length + spend.length);
assert.match(expanded[2], /think verbose conf 0\.80 \(0\.90\/3\)/);
assert.match(expanded[3], /think workable 0\.8\/3 gate 0\.70 conf 0\.50 fillers 3 repeats 1 1840 chars 460 tokens/);
assert.match(expanded[4], /reply telegraph conf 0\.60 \(2\.60\/3\)/);
assert.match(expanded[5], /reply load-bearing 2\.6\/3 gate 0\.95 conf 0\.60 fillers 3 repeats 1 1840 chars 460 tokens/);

// a long run summarises the tail instead of printing every score
const many: VoiceScore[] = Array.from({ length: SHOWN + 2 }, (_, i) => ({
	kind: "think" as const,
	index: i,
	score: 1 + i / 10,
	confidence: 0.5,
}));
assert.match(renderLines({ scores: many, at: 0 }, false, plain)[0], /\+2$/);

// --- the ledger ---

const when = new Date("2026-10-04T11:40:00Z");
assert.match(stamp(when), /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$/);
assert.equal(Date.parse(stamp(when)), when.getTime(), "the stamp keeps its instant");

const rows = ledgerRows(data, "01a103cc", when);
assert.equal(rows.length, 2, "one row per scored block");
assert.deepEqual(rows[1], {
	at: stamp(when),
	session: "01a103cc",
	kind: "reply",
	voice: 2.6,
	efficiency: 2.6,
	gate: 0.95,
	chars: 1840,
	fillers: 3,
	repeats: 1,
	tokens: 460,
});
assert.equal(ledgerRows(voiceOnly, "").length, 0, "no efficiency, no row");

const ledger = join(dir, "ledger", "scores.jsonl");
appendLedger(rows, ledger);
const stored = readFileSync(ledger, "utf8").trim().split("\n").map((each) => JSON.parse(each));
assert.equal(stored.length, 2);
assert.equal(stored[1].session, "01a103cc");
assert.equal(stored[1].kind, "reply");
assert.ok(!("evidence" in stored[1]), "the row is flat");
assert.doesNotThrow(() => appendLedger(rows, join(dir, "missing", "nested.jsonl")), "a bad path stays silent");

assert.ok(REQUEST_MAX >= FLOOR, "a request worth keeping is longer than a block");

// --- the command: no argument scores the last run, -0 walks the branch ---

const notes: string[] = [];
const entries: VoiceScoreData[] = [];
const registered: Record<string, { handler: (args: string, ctx: unknown) => Promise<void> }> = {};
const fakePi = {
	registerEntryRenderer: () => {},
	registerCommand: (name: string, spec: { handler: (args: string, ctx: unknown) => Promise<void> }) => {
		registered[name] = spec;
	},
	appendEntry: (_type: string, data: VoiceScoreData) => entries.push(data),
};
voiceScore(fakePi as unknown as ExtensionAPI);

// no classifier is registered here, so every score is the drawn error entry and
// no network call happens: this checks the wiring, not Jev
const commandCtx = (sessionBranch: unknown[]) => ({
	ui: { notify: (message: string) => notes.push(message) },
	sessionManager: { getBranch: () => sessionBranch },
	modelRegistry: { findOfType: () => undefined },
});
const command = registered["voice-score"];
assert.ok(command, "the command is registered");

await command.handler("", commandCtx(branch));
assert.equal(entries.length, 1, "no argument scores the last run only");
assert.equal(entries[0].error, "no Jev classifier in this session");
assert.equal(notes.at(-1), "voice score: 1 of 1 runs scored by Jev");

await command.handler(" -0 ", commandCtx(branch));
assert.equal(entries.length, 3, "-0 walks every run of the branch, surrounding space ignored");
assert.equal(notes.at(-1), "voice score: 2 of 2 runs scored by Jev");

notes.length = 0;
await command.handler("on", commandCtx(branch));
assert.equal(entries.length, 3, "a word that is not the switch spends nothing");
assert.match(notes[0], /no argument scores the last turn, -0 the session, got on/);

notes.length = 0;
await command.handler("", commandCtx([]));
assert.equal(entries.length, 3, "an empty session has nothing to score");
assert.match(notes[0], /nothing in this session ran long enough to judge/);

// the note line: a run that took several calls says so under its two lines
const noted = renderLines({ scores, efficiency: spend, note: "6 calls, one per 10 blocks", at: 0 }, false, plain);
assert.equal(noted.length, 3, "two score lines and the note");
assert.equal(noted[2], "6 calls, one per 10 blocks");
assert.equal(renderLines({ scores, efficiency: spend, at: 0 }, false, plain).length, 2, "no note, no line");

console.log(
	`voice_score ok: bands, ${CRITERIA.length}+${EFFICIENCY_CRITERIA.length} criteria, evidence, trace, questions, runs, command, chunks, lines, ledger`,
);