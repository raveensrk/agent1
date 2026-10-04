/**
 * check for voice_score.ts. Run:
 *   timeout 180 node --experimental-strip-types harness/tests/test_voice_score.ts
 */
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
	addCall,
	addResult,
	appendLedger,
	argLine,
	band,
	blocksOf,
	buildQuestions,
	callsOf,
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
	readEnabled,
	renderLines,
	repeats,
	REQUEST_MAX,
	SHOWN,
	stamp,
	stateOf,
	tally,
	textOf,
	thousands,
	TRACE_MAX,
	traceLine,
	traceText,
	writeEnabled,
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

// the config file: absent means on, off is explicit, malformed means on
const dir = mkdtempSync(join(tmpdir(), "voice-score-"));
assert.equal(readEnabled(join(dir, "absent.json")), true);
writeEnabled(false, join(dir, "off.json"));
assert.equal(readEnabled(join(dir, "off.json")), false);
writeEnabled(true, join(dir, "on.json"));
assert.equal(readEnabled(join(dir, "on.json")), true);
writeFileSync(join(dir, "broken.json"), "{not json");
assert.equal(readEnabled(join(dir, "broken.json")), true);

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
assert.doesNotThrow(() => appendLedger(rows, join(dir, "on.json", "nested.jsonl")), "a bad path stays silent");

assert.ok(REQUEST_MAX >= FLOOR, "a request worth keeping is longer than a block");

console.log(`voice_score ok: bands, ${CRITERIA.length}+${EFFICIENCY_CRITERIA.length} criteria, evidence, trace, questions, lines, ledger`);