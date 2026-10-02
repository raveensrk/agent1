/**
 * search guard: refuse a recursive grep before it runs.
 *
 * `grep -r` walks .git and node_modules and has no built-in bound. On
 * 2026-10-02 a single `grep -rn "bookmarks.txt" ~/dot ~/repos --include="*" -l`
 * ran 111s of a 137s session (17 GB, 169,203 files) and had to be aborted,
 * while `rg -l` finished the same question in 2.6s. Blocking with the
 * replacement command is the point: the next attempt must be the right one.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const GREP_NAMES = new Set(["grep", "egrep", "fgrep", "rgrep", "ggrep"]);

function isRecursiveFlag(word: string): boolean {
	if (word === "--recursive") return true;
	if (!/^-[^-]/.test(word)) return false;
	return word.includes("r") || word.includes("R");
}

/** True when the command runs grep with a recursive flag. */
export function recursiveGrep(command: string): boolean {
	// ponytail: quoted spans are dropped, not parsed, so a heredoc can hide a hit
	const bare = command.replace(/'[^']*'/g, "''").replace(/"[^"]*"/g, '""');
	for (const segment of bare.split(/\|\||&&|[;|\n]/)) {
		const words = segment.trim().split(/\s+/);
		const at = words.findIndex((w) => GREP_NAMES.has(w.split("/").pop() ?? ""));
		if (at === -1) continue;
		if (words.slice(at + 1).some(isRecursiveFlag)) return true;
	}
	return false;
}

const REASON = [
	'Blocked: recursive grep. `grep -r` walks .git and node_modules - measured here, one such call over ~/repos ran 111s and was aborted, while rg answered in 2.6s.',
	"Use rg, which skips hidden and gitignored paths by default:",
	'  rg -n "pattern" ~/repos',
	'Add -uu only when ignored files are genuinely wanted, and `git grep -n "pattern"` inside a repo. For a file list, bound the path and skip the walk: rg -l "pattern" ~/repos/agent1.',
].join("\n");

export default function (pi: ExtensionAPI) {
	pi.on("tool_call", (event) => {
		if (event.toolName !== "bash") return;
		const command = (event.input as { command?: unknown }).command;
		if (typeof command !== "string" || !recursiveGrep(command)) return;
		return { block: true, reason: REASON };
	});
}
