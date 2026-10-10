/**
 * check for harness_lint.ts, the trigger that hands lint's verdict back to the
 * agent. Run:
 *   node --experimental-strip-types harness/tests/test_harness_lint.ts
 *
 * Runs the real lint.py over a temp repo that carries a broken check of its
 * own. A failed check is not a pass: it must reach the agent once, not vanish
 * the way every file_naming finding did until 2026-10-09.
 */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import trigger, { crash, findingsMessage, lint } from "../extensions/harness_lint.ts";

// findings alone: the message is byte for byte what it was
const finding = { check: "file_naming", path: "Bad Name.md", line: 1, message: "rename it" };
assert.equal(
	findingsMessage([finding]),
	[
		"harness lint found 1 findings in the files this session edited:",
		"- Bad Name.md:1: file_naming: rename it",
		"",
		"Fix them, or say why one is a false positive. If a rule is wrong rather than the code, say so and fix the rule.",
	].join("\n"),
);

// a temp repo whose own check exits 1, so lint.py lists it under failures
const dir = realpathSync(mkdtempSync(join(tmpdir(), "harness_lint_test_")));
spawnSync("git", ["init", "-q", dir]);
mkdirSync(join(dir, "scripts", "checks"), { recursive: true });
const broken = (error: string) =>
	writeFileSync(
		join(dir, "scripts", "checks", "broken.py"),
		`# harness-check: {"id": "broken", "applies": ["*.md"]}\nimport sys\nsys.exit("${error}")\n`,
	);
broken("boom");
const note = join(dir, "note.md");
writeFileSync(note, "# note\n");
const line = `lint: check broken failed in ${dir}: exit 1: boom`;

const report = await lint([note], dir);
assert.deepEqual(report.failures.filter((f) => f.check === "broken"), [{ check: "broken", root: dir, error: "exit 1: boom" }]);

// the failure is lint.py's own stderr line, after the findings, which stay unchanged
const both = findingsMessage([finding], report.failures);
assert.ok(both.startsWith(`${findingsMessage([finding])}\n\n`), both);
assert.ok(both.split("\n").includes(line), both);
assert.ok(!findingsMessage([], report.failures).includes("harness lint found"), "no findings, no findings header");

// pi: the failure continues the agent once; a rerun stays quiet even when the error text moves
const handlers: Record<string, (event: unknown, ctx: unknown) => unknown> = {};
const fakePi = { on: (name: string, handler: (event: unknown, ctx: unknown) => unknown) => (handlers[name] = handler) };
trigger(fakePi as unknown as ExtensionAPI);
const settle = async () => {
	handlers.tool_call({ toolName: "edit", input: { path: note } }, {});
	return (await handlers.agent_before_settle({}, { cwd: dir })) as
		| { entries: { content: string }[]; continue: boolean }
		| undefined;
};

const first = await settle();
assert.equal(first?.continue, true, "a failed check alone continues the agent");
assert.ok(first.entries[0].content.split("\n").includes(line), first.entries[0].content);
broken("boom again");
assert.equal(await settle(), undefined, "one check in one repo is reported once, whatever its error says");

// lint.py itself: a timeout, a crash, a missing python3 and empty output each
// name what happened, so a dead dispatcher never reads as a clean run
const why = (error: unknown, stderr = "") => crash(error, stderr, "/r");
assert.match(why({ killed: true, signal: "SIGTERM" }).error, /^timed out after 30 s - see it: .*lint\.py --timing FILE\.\.\.$/);
assert.match(why({ code: 1 }, "Traceback\nKeyError: 'x'\n").error, /^exit 1: KeyError: 'x' - see it: /);
assert.match(why({ code: "ENOENT", message: "spawn python3 ENOENT" }).error, /^spawn python3 ENOENT - see it: /);
assert.match(why(null).error, /^no JSON on stdout - see it: /);
assert.deepEqual([why(null).check, why(null).root], ["lint.py", "/r"]);

rmSync(dir, { recursive: true, force: true });
console.log("ok - harness_lint");
