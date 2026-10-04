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
 *
 * What it reads is the command, minus the parts the shell never runs: quoted
 * spans and heredoc bodies are data. A measured false positive blocked a call
 * whose only offence was a runner keyword inside a quoted echo, and another
 * inside a heredoc body, so both are dropped before the patterns match.
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

/**
 * COMMAND with heredoc bodies removed: a body is data, not something the shell
 * runs. An unterminated heredoc swallows the rest of the command, which can
 * hide a hit - the right side to err on, since a guard that invents a block
 * costs a real call.
 */
function stripHeredocs(command: string): string {
	const kept: string[] = [];
	let terminator: string | null = null;
	for (const line of command.split("\n")) {
		if (terminator) {
			if (line.trim() === terminator) terminator = null;
			continue;
		}
		kept.push(line);
		const opener = line.match(
			/<<-?[ \t]*(?:'([A-Za-z_][A-Za-z0-9_]*)'|"([A-Za-z_][A-Za-z0-9_]*)"|([A-Za-z_][A-Za-z0-9_]*))/,
		);
		if (opener) terminator = opener[1] ?? opener[2] ?? opener[3] ?? null;
	}
	return kept.join("\n");
}

/**
 * The part of COMMAND that would actually run. Quoted spans and heredoc bodies
 * are dropped, which is what the two measured false positives needed: a runner
 * keyword in a quoted echo, and one in a heredoc body, both blocked real work.
 */
export function executableText(command: string): string {
	return stripHeredocs(command)
		.replace(/'[^']*'/g, "''")
		.replace(/"[^"]*"/g, '""');
}

/** The test runner in COMMAND with no shell bound, or null. */
function unboundedRunner(command: string): string | null {
	const text = executableText(command);
	if (SHELL_BOUND.test(text)) return null;
	for (const runner of RUNNERS) {
		const found = text.match(runner);
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
	// ponytail: quoted spans and heredoc bodies are dropped, not parsed, so a heredoc can hide a hit
	return executableText(command)
		.split(/\|\||&&|[;|\n]/)
		.map((segment) => segment.trim().split(/\s+/));
}

/**
 * `ls ... 2>/dev/null && echo|cat|printf`. The suppressed error hides a missing
 * path, and the `&&` then skips the print, so the call exits 1 having printed
 * nothing - which reads as a failure and silently drops the rest of the command.
 * Measured 2026-10-04 across 147 pi transcripts and 4612 bash commands: 4
 * instances, every one this shape, and one aborted a per-file plan mid-command.
 * The tail must be
 * a print, so `ls X 2>/dev/null && ./X` - skip the work when it is missing -
 * stays allowed, and ~/.bash_history holds 0 of either, so this is an agent
 * habit rather than a typed one.
 */
function lsSuppressedThenPrint(command: string): boolean {
	// Split on ; and newline and a single |, but never inside a ||: a || is the
	// fallback that makes the whole shape correct.
	for (const segment of executableText(command).split(/[;\n]|(?<!\|)\|(?!\|)/)) {
		// A `||` anywhere in the segment means the failure is handled, which is
		// the shape `ls X 2>/dev/null && echo exists || { fallback; }`.
		if (segment.includes("||")) continue;
		const parts = segment.split("&&").map((part) => part.trim());
		for (let i = 0; i < parts.length - 1; i++) {
			if (!/(?:^|\s)(?:\S*\/)?ls\s/.test(parts[i])) continue;
			if (!/2>\s*\/dev\/null/.test(parts[i])) continue;
			// The print must END the chain: `ls X && echo hdr && ./X` is a guard
			// on the next step, and skipping it when X is missing is intended.
			if (i + 1 !== parts.length - 1) continue;
			if (/^(?:echo|cat|printf)\b/.test(parts[i + 1])) return true;
		}
	}
	return false;
}

/** A path a copy is expected to be disposable at. */
const SCRATCH = /^(?:~\/tmp\/|\/tmp\/|\$TMPDIR\/|\/var\/folders\/)/;

/**
 * A browser cookie database copied into a scratch path and left there. Measured
 * 2026-10-04: `cp .../cookies.sqlite ~/tmp/ff_cookies.sqlite` put a live console
 * session in ~/tmp for 50 minutes, beside three copied browser profiles. The
 * copy itself is needed - the browser holds the database locked - so the fix is
 * to delete it in the same command, not to refuse the work.
 *
 * Reads the heredoc-stripped command, not the quote-stripped one: a destination
 * is often quoted, and a quoted span is exactly what the other patterns drop.
 */
function cookieCopyWithoutDelete(command: string): string | null {
	const text = stripHeredocs(command);
	const copy = text.match(
		/(?:^|[;&|\n])\s*cp\s[^;&|\n]*\/(?:cookies\.sqlite|Cookies)\s+("[^"]*"|'[^']*'|[^\s;&|]+)/,
	);
	if (!copy) return null;
	const dest = copy[1].replace(/^["']|["']$/g, "");
	if (!SCRATCH.test(dest)) return null;
	const escaped = dest.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
	const removed = new RegExp(`(?:^|[;&|\\n])\\s*(?:rm|unlink)\\s[^;&|\\n]*${escaped}`);
	return removed.test(text) ? null : dest;
}

/** The command shape that would hang, or null when it is safe. */
export function guardHit(command: string): Hit | null {
	if (lsSuppressedThenPrint(command)) {
		return {
			name: "ls with a suppressed error, chained to a print",
			fix: [
				"A missing path fails the ls, and the && then skips the print, so the",
				"call exits 1 having printed nothing (common.md):",
				"  ls A B 2>/dev/null || true      # a listing that may be empty",
				"  if [ -d A ]; then cd A; fi      # act only when it exists",
			].join("\n"),
		};
	}
	const copied = cookieCopyWithoutDelete(command);
	if (copied) {
		return {
			name: `a browser cookie database copied to ${copied} and left there`,
			fix: [
				"The copy is fine; leaving it is not. Delete it in the same command:",
				'  D=~/tmp/cookies.sqlite; cp SRC "$D" && sqlite3 "$D" "select 1"; rm -f "$D"',
			].join("\n"),
		};
	}
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
