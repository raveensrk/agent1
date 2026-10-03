/**
 * check for edit_guard.ts. Run:
 *   node --experimental-strip-types harness/tests/test_edit_guard.ts
 */
import assert from "node:assert/strict";
import { editHit, nearestWindow, occurrences } from "../extensions/edit_guard.ts";

const FILE = [
	'(defun todo-create (rest flags)',
	'  (let* ((title (car rest))',
	'         (priority (todo--flag flags "--priority"))',
	'         (note (todo--flag flags "--note")))',
	'    (when deadline (org-deadline nil deadline))',
	'    (when note (todo--append-body note))))',
].join("\n");

// the exact region passes, as every edit in the session that happened to be right did
assert.equal(editHit("/tmp/a.el", FILE, [{ oldText: "    (when note (todo--append-body note))))" }]), null);
assert.equal(
	editHit("/tmp/a.el", FILE, [
		{ oldText: "  (let* ((title (car rest))" },
		{ oldText: "    (when note (todo--append-body note))))" },
	]),
	null,
);

// the first real failure: a guessed region that is not in the file
const missing = editHit("/tmp/a.el", FILE, [{ oldText: "  (let ((board (todo--existing file)))" }]);
assert.ok(missing, "a missing oldText must block");
assert.match(missing, /is not in \/tmp\/a\.el/);
assert.match(missing, /^.*read \/tmp\/a\.el/m, "the block must print the read to do");

// the second real failure: an oldText that matches twice, which aborted the batch
const twice = editHit("/tmp/a.el", FILE, [{ oldText: "(defun todo-create" }]);
assert.equal(twice, null, "a single occurrence cannot be duplicated in this fixture");
const duped = FILE + "\n" + FILE;
const ambiguous = editHit("/tmp/a.el", duped, [{ oldText: "    (when note (todo--append-body note))))" }]);
assert.ok(ambiguous, "a twice-matching oldText must block");
assert.match(ambiguous, /appears 2 times/);

// an edit that overlaps an earlier one in the same call
const overlap = editHit("/tmp/a.el", FILE, [
	{ oldText: "         (priority (todo--flag flags \"--priority\"))" },
	{ oldText: "  (let* ((title (car rest))\n         (priority (todo--flag flags \"--priority\"))" },
]);
assert.ok(overlap, "overlapping edits must block before the tool applies the batch");
assert.match(overlap, /overlaps an earlier oldText/);

// helpers
assert.deepEqual(occurrences("a\nb\na\n", "a"), [1, 3]);
assert.match(nearestWindow(FILE, "    (when note"), /^\s+4: /m);

console.log("edit_guard: all checks passed");
