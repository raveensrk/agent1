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

const GREP_NAMES = new Set(["grep", "egrep", "fgrep", "rgrep", "ggrep"]);
const FETCHERS = new Set(["curl", "wget"]);
const TIMEOUT_FLAG = /(^|\s)--(max-time|connect-timeout|timeout)(=\S+)?(\s|$)|(^|\s)-m(\s|$|\d)/;

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
		if (!hit) return;
		return {
			block: true,
			reason: `Blocked: ${hit.name}. ${MEASURED}\n${hit.fix}\nBound the path for a search, and keep the timeout on every fetch.`,
		};
	});
}
