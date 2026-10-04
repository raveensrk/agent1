/**
 * command guard: refuse the command shapes that hang before they run.
 *
 * Two shapes, both measured on this machine:
 *
 * - recursive grep. One `grep -rn` over ~/repos spent 111s of a 137s session
 *   (17 GB, 169,203 files) and had to be aborted; `rg -l` answered in 2.6s.
 * - curl or wget with no maximum time. ~/.bash_history holds 9 `curl ... | sh`
 *   installs with no `--max-time`, and a dead host blocks one of those forever.
 *
 * Blocking with the replacement command is the point: the next attempt must be
 * the right one. A guard that only says no sends it down the same dead end.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { execFileSync } from "node:child_process";
import { homedir } from "node:os";
import { join } from "node:path";

const GREP_NAMES = new Set(["grep", "egrep", "fgrep", "rgrep", "ggrep"]);
const FETCHERS = new Set(["curl", "wget"]);
const TIMEOUT_FLAG = /(^|\s)--(max-time|connect-timeout|timeout)(=\S+)?(\s|$)|(^|\s)-m(\s|$|\d)/;

// A test suite run with no shell bound. Measured 2026-10-03: one
// `emacs -Q --batch ... ert-run-tests-batch-and-exit` hung on a daemon waiting
// for a keypress, burned the full 300s tool timeout, and cost another 194s when
// it was aborted - the same suite finishes in 5s when it is healthy.
const RUNNERS = [
	/\bpytest\b/,
	/\bcargo\s+test\b/,
	/\bswift\s+test\b/,
	/\bgo\s+test\b/,
	/\bnpm\s+(run\s+)?test\b/,
	/\byarn\s+test\b/,
	/\bert-run-tests/,
];
const SHELL_BOUND = /(^|\s)timeout\s+\d+/;

/** The test runner in COMMAND with no shell bound, or null. */
function unboundedRunner(command: string): string | null {
	if (SHELL_BOUND.test(command)) return null;
	for (const runner of RUNNERS) {
		const found = command.match(runner);
		if (found) return found[0];
	}
	return null;
}

type Hit = { name: string; fix: string };

function isRecursiveFlag(word: string): boolean {
	if (word === "--recursive") return true;
	if (!/^-[^-]/.test(word)) return false;
	return word.includes("r") || word.includes("R");
}

function wordsOf(command: string): string[][] {
	// ponytail: quoted spans are dropped, not parsed, so a heredoc can hide a hit
	const bare = command.replace(/'[^']*'/g, "''").replace(/"[^"]*"/g, '""');
	return bare.split(/\|\||&&|[;|\n]/).map((segment) => segment.trim().split(/\s+/));
}

/** The command shape that would hang, or null when it is safe. */
export function guardHit(command: string): Hit | null {
	for (const words of wordsOf(command)) {
		const names = words.map((word) => word.split("/").pop() ?? "");
		const grepAt = names.findIndex((name) => GREP_NAMES.has(name));
		if (grepAt !== -1 && words.slice(grepAt + 1).some(isRecursiveFlag)) {
			return {
				name: "recursive grep",
				fix: [
					"Use rg, which skips hidden and gitignored paths:",
					'  rg -n "pattern" ~/repos',
				].join("\n"),
			};
		}
		const fetchAt = names.findIndex((name) => FETCHERS.has(name));
		if (fetchAt !== -1) {
			const flags = words.slice(fetchAt + 1).join(" ");
			if (!TIMEOUT_FLAG.test(flags)) {
				return {
					name: "curl or wget with no maximum time",
					fix: [
						"A dead host blocks forever without one:",
						"  curl -fsSL --max-time 60 URL | sh",
						"  wget --timeout=60 URL",
					].join("\n"),
				};
			}
		}
		const catAt = names.findIndex((name) => name === "cat");
		if (catAt !== -1 && words.slice(catAt + 1).some((word) => /^-[^-]*A/.test(word))) {
			return {
				name: "cat -A, which BSD cat does not have",
				fix: [
					"common.md: BSD cat has no -A, and the flag aborts the call:",
					"  cat -v -e FILE",
					"  sed -n l FILE",
				].join("\n"),
			};
		}
		const tmpAt = words.findIndex(
			(word, index) =>
				/^[0-9&]?>>?\/tmp\//.test(word) ||
				(/^[0-9&]?>>?$/.test(word) && (words[index + 1] ?? "").startsWith("/tmp/")),
		);
		if (tmpAt !== -1) {
			return {
				name: "a temp file written under /tmp",
				fix: [
					"Temp files go under ~/tmp, never /tmp (common.md):",
					"  mkdir -p ~/tmp/review && cmd 2> ~/tmp/review/err.txt",
				].join("\n"),
			};
		}
	}
	const runner = unboundedRunner(command);
	if (runner) {
		return {
			name: `unbounded test run (${runner})`,
			fix: [
				"Bound it, and state the ETA before starting it (jobs.md):",
				"  timeout 180 emacs -Q --batch -l tests/todo_tests.el -f ert-run-tests-batch-and-exit",
				"  scripts/test                      # the todo skill's suite: bounded, prints the failures",
				"  timeout 900 swift test",
			].join("\n"),
		};
	}
	return null;
}

const MEASURED =
	"Measured here: one recursive grep over ~/repos ran 111s of a 137s session and was " +
	"aborted, and ~/.bash_history holds 9 curl installs with no --max-time.";

export default function (pi: ExtensionAPI) {
	pi.on("tool_call", (event) => {
		if (event.toolName !== "bash") return;
		const command = (event.input as { command?: unknown }).command;
		if (typeof command !== "string") return;
		const hit = guardHit(command);
		if (hit) {
			return {
				block: true,
				reason: `Blocked: ${hit.name}. ${MEASURED}\n${hit.fix}\nBound the path for a search, and keep the timeout on every fetch.`,
			};
		}
	});
}
