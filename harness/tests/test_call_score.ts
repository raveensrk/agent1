/**
 * check for call_score.ts. Run:
 *   timeout 180 node --experimental-strip-types harness/tests/test_call_score.ts
 */
import assert from "node:assert/strict";
import {
	CALL_GATE,
	CALL_GOOD,
	CALL_MAX,
	CALL_PASS,
	callBand,
	callLine,
	buildQuestions,
	evidence,
	necessity,
	NECESSITY_CRITERIA,
	OVERSIZE,
	range,
	READ_WINDOW,
	renderLines,
	repeated,
	sliceOf,
	SLICE_HEAD,
	SLICE_TAIL,
	stateOf,
	subsumed,
	ledgerRows,
	type Call,
	type CallScoreData,
} from "../extensions/call_score.ts";
import { argLine, SHOWN } from "../extensions/voice_score.ts";

const plain = (_color: string, text: string): string => text;

// the bands: parked on this machine, so no colour is claimed
assert.equal(CALL_PASS, 0, "the bands stay parked until a calibration finds a gap");
assert.equal(CALL_GOOD, 0);
assert.equal(callBand(0).color, "dim");
assert.equal(callBand(2.5).color, "dim");
assert.equal(callBand(1).label, "uncalibrated");

// the calibrated path, for the day a gap is measured
assert.equal(callBand(0.74, 0.75, 1.5).label, "needless");
assert.equal(callBand(0.74, 0.75, 1.5).color, "error");
assert.equal(callBand(0.75, 0.75, 1.5).label, "justified");
assert.equal(callBand(0.75, 0.75, 1.5).color, "warning");
assert.equal(callBand(1.49, 0.75, 1.5).color, "warning");
assert.equal(callBand(1.5, 0.75, 1.5).label, "necessary");
assert.equal(callBand(1.5, 0.75, 1.5).color, "success");

// the call line: args, the result size, and an error marker
assert.equal(callLine({ id: "1", name: "read", args: "voice_score.ts" }), "read voice_score.ts");
assert.equal(
	callLine({ id: "1", name: "read", args: "voice_score.ts", chars: 1840 }),
	"read voice_score.ts (1,840 chars result)",
);
assert.equal(
	callLine({ id: "1", name: "bash", args: "ls", chars: 0, error: true }),
	"bash ls (0 chars result, error)",
);

// the slice: short text whole, long text head and tail, empty stays empty
const big = "a".repeat(SLICE_HEAD) + "MIDDLE" + "b".repeat(SLICE_TAIL);
const cut = sliceOf(big);
assert.ok(cut.startsWith("a".repeat(SLICE_HEAD)));
assert.ok(cut.endsWith("b".repeat(SLICE_TAIL)));
assert.ok(cut.includes("\n...\n"));
assert.ok(!cut.includes("MIDDLE"), "the judge never sees the middle");
assert.equal(sliceOf("short"), "short");
assert.equal(sliceOf(undefined), "");
assert.equal(sliceOf([{ type: "text", text: "two blocks" }]), "two blocks");

// the range a read asks for, from its own arguments
assert.deepEqual(
	range({ id: "1", name: "bash", args: "ls", raw: { path: "x" } }),
	{ path: "x", start: 1, end: READ_WINDOW },
	"range reads the arguments; the caller decides which tools it applies to",
);
assert.equal(range({ id: "1", name: "read", args: "x" }), undefined);
assert.deepEqual(range({ id: "1", name: "read", args: "x", raw: { path: "x" } }), {
	path: "x",
	start: 1,
	end: READ_WINDOW,
});
assert.deepEqual(range({ id: "1", name: "read", args: "x", raw: { path: "x", offset: 10, limit: 5 } }), {
	path: "x",
	start: 10,
	end: 14,
});
assert.deepEqual(range({ id: "1", name: "read", args: "x", raw: { path: "x", limit: 5 } }), {
	path: "x",
	start: 1,
	end: 5,
});
assert.deepEqual(range({ id: "1", name: "read", args: "x", raw: { path: "x", offset: 10 } }), {
	path: "x",
	start: 10,
	end: 10 + READ_WINDOW - 1,
});

// subsumed retrieval: a later read inside an earlier one, same path only
const mkRead = (id: string, raw: Record<string, unknown>): Call => ({ id, name: "read", args: argLine(raw), raw });
const reads: Call[] = [
	mkRead("1", { path: "x", offset: 1, limit: 100 }),
	mkRead("2", { path: "x", offset: 10, limit: 5 }),
	mkRead("3", { path: "x", offset: 90, limit: 30 }),
	mkRead("4", { path: "y", offset: 10, limit: 5 }),
	{ id: "5", name: "bash", args: "cat x" },
	mkRead("6", { path: "x" }),
];
assert.equal(subsumed(reads, 1), true, "a slice inside an earlier read is subsumed");
assert.equal(subsumed(reads, 2), false, "a range past the earlier one is not");
assert.equal(subsumed(reads, 3), false, "another path is not subsumed");
assert.equal(subsumed(reads, 4), false, "a bash call is out of scope");
assert.equal(subsumed(reads, 5), false, "a later whole-file read is not subsumed by a slice");
assert.equal(subsumed([mkRead("1", { path: "x" }), reads[1]], 1), true, "a whole-file read covers a later slice");

// repeats: same tool and near-identical args, counted from earlier calls
const same: Call[] = [
	{ id: "1", name: "read", args: "harness/extensions/voice_score.ts" },
	{ id: "2", name: "read", args: "harness/extensions/voice_score.ts" },
	{ id: "3", name: "read", args: "harness/extensions/call_score.ts" },
	{ id: "4", name: "bash", args: "harness/extensions/voice_score.ts" },
];
assert.equal(repeated(same, 0), 0);
assert.equal(repeated(same, 1), 1);
assert.equal(repeated(same, 2), 0, "a different file is a different call");
assert.equal(repeated(same, 3), 0, "another tool is not a repeat");
assert.equal(repeated([same[0], { id: "2", name: "read", args: "extensions/voice_score.ts harness" }], 1), 1, "word overlap 0.8 counts");

// the evidence: sizes, repeats, subsumed, oversized
const measured = evidence(reads, 1);
assert.deepEqual(measured, { chars: 0, repeats: 0, subsumed: true, oversize: false });
const huge = evidence([{ id: "1", name: "bash", args: "cat log", chars: OVERSIZE + 1 }], 0);
assert.equal(huge.oversize, true);
assert.equal(evidence([{ id: "1", name: "bash", args: "cat log", chars: OVERSIZE }], 0).oversize, false);

// two questions per call, each naming its own state path
const questions = buildQuestions(reads.slice(0, 2));
assert.deepEqual(Object.keys(questions), ["n0", "h0", "n1", "h1"]);
assert.equal(questions.n0.type, "score");
assert.deepEqual(questions.n0.criteria, NECESSITY_CRITERIA);
assert.match(questions.n1.instructions, /`c1`/);
assert.equal(questions.h0.type, "bool");
assert.deepEqual(questions.h0.criteria, CALL_GATE);

// the state: request first, then the call line and its result slice
const state = stateOf(reads.slice(0, 2), "the request");
assert.deepEqual(Object.keys(state), ["request", "c0", "s0", "c1", "s1"]);
assert.equal(state.request, "the request");
assert.match(state.c0, /^read x offset=1 limit=100$/);
assert.equal(state.s0, "");
assert.equal(stateOf([], "the request").trace, undefined);

// the gate multiplies the score
assert.equal(necessity(3, 1), 3);
assert.equal(necessity(2.6, 0.95), 2.47);
assert.equal(necessity(3, 0), 0);

// the drawn line: one number per call, in order, then the tail count
const data: CallScoreData = {
	calls: [
		{ index: 0, name: "read", args: "a.ts", score: 3, gate: 1, confidence: 0.7, evidence: { chars: 100, repeats: 0, subsumed: false, oversize: false } },
		{ index: 1, name: "read", args: "a.ts", score: 2, gate: 0.6, confidence: 0.6, evidence: { chars: 100, repeats: 1, subsumed: true, oversize: false } },
		{ index: 2, name: "bash", args: "pytest", score: 0.4, gate: 0.5, confidence: 0.8, evidence: { chars: 20000, repeats: 3, subsumed: false, oversize: true } },
	],
	dropped: 2,
	at: 0,
};
assert.deepEqual(renderLines(data, false, plain), ["calls  3.0/3 1.2/3 0.2/3"]);
assert.deepEqual(renderLines({ calls: [], dropped: 0, at: 0 }, false, plain), ["calls  nothing scored"]);
assert.match(renderLines({ calls: [], dropped: 0, error: "aborted", at: 0 }, false, plain)[0], /unavailable: aborted/);

const expanded = renderLines(data, true, plain);
assert.equal(expanded.length, 1 + data.calls.length + 1);
assert.match(expanded[1], /read a\.ts uncalibrated 3\.0\/3 gate 1\.00 conf 0\.70 100 chars$/);
assert.match(expanded[2], /read a\.ts uncalibrated 1\.2\/3 gate 0\.60 conf 0\.60 repeats 1 subsumed 100 chars$/);
assert.match(expanded[3], /bash pytest uncalibrated 0\.2\/3 gate 0\.50 conf 0\.80 repeats 3 oversize 20000 chars$/);
assert.match(expanded[4], /\+2 calls not scored/);

// a long run summarises the tail, like the other lines
const many: CallScoreData = {
	calls: Array.from({ length: SHOWN + 2 }, (_value, i) => ({
		index: i,
		name: "read",
		args: `f${i}.ts`,
		score: 2,
		gate: 1,
		confidence: 0.5,
		evidence: { chars: 1, repeats: 0, subsumed: false, oversize: false },
	})),
	dropped: 0,
	at: 0,
};
assert.match(renderLines(many, false, plain)[0], /\+2$/);

// the ledger row: kind "call", the tool, both numbers and the evidence
const when = new Date("2026-10-04T11:40:00Z");
const rows = ledgerRows(data, "01a103cc", when);
assert.equal(rows.length, data.calls.length);
assert.deepEqual(rows[1], {
	at: rows[0].at,
	session: "01a103cc",
	kind: "call",
	tool: "read",
	necessity: 2,
	gate: 0.6,
	score: 1.2,
	repeats: 1,
	subsumed: true,
	oversize: false,
	chars: 100,
});
assert.match(rows[0].at, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$/);
assert.deepEqual(ledgerRows({ calls: [], dropped: 0, at: 0 }, "x"), []);

assert.ok(CALL_MAX >= SHOWN, "a run can show a full line of calls");

console.log(`call_score ok: bands, ${NECESSITY_CRITERIA.length} criteria, slice, range, subsumed, repeats, evidence, questions, lines, ledger`);