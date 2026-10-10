/**
 * check for hook.ts, the Claude Code side of the harness. Run:
 *   node --experimental-strip-types harness/tests/test_hook.ts
 *
 * Drives the CLI the way Claude does - event JSON on stdin - and checks the
 * contract: exit 2 with the reason on stderr blocks, exit 0 lets it run.
 */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { editedFiles } from "../hook.ts";

const HOOK = join(dirname(fileURLToPath(import.meta.url)), "..", "hook.ts");

function run(args: string[], event: unknown, home?: string) {
	return spawnSync("node", ["--experimental-strip-types", "--no-warnings", HOOK, ...args], {
		input: JSON.stringify(event),
		encoding: "utf8",
		env: home ? { ...process.env, HOME: home } : process.env,
	});
}

// help: -h is the header's first line plus the usage; `help` is the whole header
assert.match(run(["-h"], {}).stdout, /^hook: agent1's harness for Claude Code.*\nusage: hook\.ts/);
const help = run(["help"], {});
assert.equal(help.status, 0);
assert.match(help.stdout, /^Exit: 0 allow/m);

// guard: the pi command_guard rules, refused with the replacement command
const grep = run(["guard"], { tool_name: "Bash", tool_input: { command: "grep -rn foo ~/repos" } });
assert.equal(grep.status, 2);
assert.match(grep.stderr, /rg -n/);
assert.equal(run(["guard"], { tool_name: "Bash", tool_input: { command: "rg -n foo ~/repos" } }).status, 0);

// guard: the pi edit_guard rule, mapped from Claude's Edit input
const dir = mkdtempSync(join(tmpdir(), "hook-test-"));
const file = join(dir, "a.txt");
writeFileSync(file, "one\ntwo\ntwo\n");
const edit = (old: string, all = false) =>
	run(["guard"], { tool_name: "Edit", tool_input: { file_path: file, old_string: old, new_string: "x", replace_all: all } });
assert.equal(edit("one").status, 0);
assert.equal(edit("two").status, 2, "two occurrences are refused");
assert.equal(edit("two", true).status, 0, "replace_all wants every occurrence");
assert.equal(edit("missing").status, 2);

// transcript: only Edit, Write and NotebookEdit paths, once each
const transcript = [
	{ type: "assistant", message: { content: [{ type: "tool_use", name: "Write", input: { file_path: "/a" } }] } },
	{ type: "assistant", message: { content: [{ type: "tool_use", name: "Edit", input: { file_path: "/a" } }] } },
	{ type: "assistant", message: { content: [{ type: "tool_use", name: "Read", input: { file_path: "/b" } }] } },
	{ type: "assistant", message: { content: [{ type: "tool_use", name: "NotebookEdit", input: { notebook_path: "/c" } }] } },
].map((line) => JSON.stringify(line)).join("\n");
assert.deepEqual(editedFiles(`${transcript}\nnot json`), ["/a", "/c"]);

// nudge: one systemMessage on the second failure in a row, none after
const event = { session_id: "t", hook_event_name: "PostToolUseFailure", tool_name: "Bash" };
const outs = [1, 2, 3].map(() => run(["nudge"], event, dir).stdout);
assert.deepEqual(outs.map((out) => out.includes("systemMessage")), [false, true, false]);
run(["nudge"], { ...event, hook_event_name: "PostToolUse" }, dir);
assert.equal(run(["nudge"], event, dir).stdout, "", "a success resets the streak");

// lint: a failed check blocks Stop once, as lint.py's own line; the rerun is quiet.
// HOME is the temp dir, so hook.ts runs this stub in place of ~/repos/agent1/harness/lint.py.
const stub = join(dir, "repos", "agent1", "harness");
mkdirSync(stub, { recursive: true });
const failure = { check: "broken", root: "/r", error: "exit 1: boom" };
writeFileSync(join(stub, "lint.py"), `print(${JSON.stringify(JSON.stringify({ findings: [], failures: [failure] }))})\n`);
const log = join(dir, "transcript.jsonl");
writeFileSync(log, `${JSON.stringify({ message: { content: [{ type: "tool_use", name: "Write", input: { file_path: file } }] } })}\n`);
const stop = { session_id: "lint", transcript_path: log, cwd: dir };
const blocked = run(["lint"], stop, dir).stdout;
assert.match(blocked, /lint: check broken failed in \/r: exit 1: boom/, "a failed check must reach the agent");
assert.equal(JSON.parse(blocked).decision, "block");
assert.equal(run(["lint"], stop, dir).stdout, "", "a failure already reported must not block again");

// lint: lint.py itself crashing is a failure too, never a clean run
writeFileSync(join(stub, "lint.py"), `import sys\nsys.exit("Traceback (most recent call last):\\nKeyError: 'x'")\n`);
const crash = { ...stop, session_id: "crash" };
const crashed = run(["lint"], crash, dir).stdout;
assert.ok(crashed.includes(`lint: check lint.py failed in ${dir}: exit 1: KeyError: 'x'`), crashed);
assert.equal(run(["lint"], crash, dir).stdout, "", "a crash already reported must not block again");

// rules: the SessionStart context carries common.md
const rules = JSON.parse(run(["rules"], {}).stdout);
assert.match(rules.hookSpecificOutput.additionalContext, /common\.md/);

rmSync(dir, { recursive: true, force: true });
console.log("ok - hook");
