/**
 * edit guard: refuse an edit whose oldText is not in the file exactly once.
 *
 * Measured in the 2026-10-03 session: 54 edit calls, 3 refused by the tool
 * itself - two "Could not find edits[0]" from a guessed region and one "Found 2
 * occurrences of edits[5]" that aborted a whole batch. Each cost a read, a
 * rewrite and a retry, and the 2-occurrence failure only surfaced after the
 * other edits in the same call were already matched.
 *
 * common.md has the rule: "Read the exact region before an edit when this
 * session has not shown that text - one guessed oldText aborts the whole batch
 * and costs a retry." A rule a check can decide belongs in a check, so this one
 * decides it: the block prints the nearest text with line numbers, which is the
 * read the rule asks for, so the next attempt is the right one.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { readFileSync } from "node:fs";

type Edit = { oldText?: unknown; newText?: unknown };
type Input = { path?: unknown; edits?: unknown };

/** Every line in TEXT containing NEEDLE, 1-based. */
export function occurrences(text: string, needle: string): number[] {
	if (!needle) return [];
	const lines = text.split("\n");
	const first = needle.split("\n")[0]?.trim() ?? "";
	const hits: number[] = [];
	// Count real substring occurrences for the "exactly once" rule, then name
	// the lines so the fix can show both places.
	let from = 0;
	let seen = 0;
	while (true) {
		const at = text.indexOf(needle, from);
		if (at === -1) break;
		seen += 1;
		hits.push(text.slice(0, at).split("\n").length);
		from = at + 1;
	}
	if (seen === 0 && first) {
		lines.forEach((line, index) => {
			if (line.includes(first)) hits.push(index + 1);
		});
	}
	return hits;
}

/** A window of the file around the first line of NEEDLE, for the block reason. */
export function nearestWindow(text: string, needle: string, span = 6): string {
	const lines = text.split("\n");
	const first = (needle.split("\n")[0] ?? "").trim();
	let at = first ? lines.findIndex((line) => line.includes(first)) : -1;
	if (at === -1) at = 0;
	const start = Math.max(0, at - 2);
	const end = Math.min(lines.length, start + span);
	return lines
		.slice(start, end)
		.map((line, index) => `  ${start + index + 1}: ${line}`)
		.join("\n");
}

/** The block reason for one edit call, or null when every edit is safe. */
export function editHit(path: string, text: string, edits: Edit[]): string | null {
	const seen: string[] = [];
	for (const [index, edit] of edits.entries()) {
		const oldText = typeof edit.oldText === "string" ? edit.oldText : "";
		if (!oldText) {
			return `Blocked: edits[${index}] has no oldText. Every edit needs the exact existing text to replace.`;
		}
		if (seen.some((earlier) => earlier.includes(oldText) || oldText.includes(earlier))) {
			return (
				`Blocked: edits[${index}] overlaps an earlier oldText in the same call.\n` +
				`Merge them into one edit, or make them disjoint.`
			);
		}
		seen.push(oldText);
		const where = occurrences(text, oldText);
		const exact = text.split(oldText).length - 1;
		if (exact > 1) {
			return (
				`Blocked: edits[${index}] oldText appears ${exact} times in ${path} (lines ${where.join(", ")}).\n` +
				`Add a surrounding line from the one you mean until it is unique, or split the edit per location.`
			);
		}
		if (exact === 0) {
			return (
				`Blocked: edits[${index}] oldText is not in ${path}.\n` +
				`Nearest text${where.length ? `, lines ${where.join(", ")}` : ""}:\n` +
				`${nearestWindow(text, oldText)}\n` +
				`Read that region and retry with the exact text - one guessed oldText aborts the whole batch.\n` +
				`  read ${path}   # offset ${Math.max(0, (where[0] ?? 1) - 3)}, limit 12`
			);
		}
	}
	return null;
}

export default function (pi: ExtensionAPI) {
	pi.on("tool_call", (event) => {
		if (event.toolName !== "edit") return;
		const input = event.input as Input;
		if (typeof input.path !== "string" || !Array.isArray(input.edits)) return;
		let text: string;
		try {
			text = readFileSync(input.path, "utf8");
		} catch {
			return;
		}
		const reason = editHit(input.path, text, input.edits as Edit[]);
		if (reason) return { block: true, reason };
	});
}
