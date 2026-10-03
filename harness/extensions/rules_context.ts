/**
 * rules context: the durable rules are in the prompt, not in a read the agent
 * can skip.
 *
 * Measured 2026-10-03: of the six files common.md names for session start, two
 * were never read (code_style.md and jobs.md) and git.md only when the first
 * commit came up. The misses line up with the session's costs: a 300s unbounded
 * suite run with no ETA (jobs.md) and ad-hoc probe scripts (code_style.md).
 *
 * pi reads AGENTS.md verbatim and does not expand `@path` imports - verified in
 * dist/core/resource-loader.js, and the docs never mention imports - so a file
 * that is only *named* stays optional. This hook appends common.md itself, and
 * names the topic files with what each is for, so a skipped read is a decision
 * rather than an oversight.
 *
 * ponytail: the whole file on every run, ~270 lines. Trim it to the rules that
 * actually get missed if the context cost ever shows up in a token report.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const COMMON = join(homedir(), "repos/agent1/common.md");

/** Topic files common.md points at, with the reason to read each one. */
const TOPICS: [string, string][] = [
	["emoji_legend.md", "the emoji vocabulary for reports"],
	["code_style.md", "how to write code"],
	["git.md", "commits and pull requests"],
	["jobs.md", "ETA rules for long-running jobs"],
	["skills/todo/SKILL.md", "the todo skill, the board's only writer"],
];

export function rulesSection(text: string, topics: [string, string][] = TOPICS): string {
	if (!text.trim()) return "";
	return [
		"## Rules (loaded from ~/repos/agent1/common.md)",
		"",
		text.trim(),
		"",
		"Read the topic file when the task touches it:",
		...topics.map(([name, why]) => `- agent1/${name} - ${why}`),
	].join("\n");
}

export default function (pi: ExtensionAPI) {
	pi.on("before_agent_start", (event) => {
		let section: string;
		try {
			section = rulesSection(readFileSync(COMMON, "utf8"));
		} catch {
			section =
				"## Rules\n\n~/repos/agent1/common.md is missing, so the session-start rules did not load. Read the topic files under ~/repos/agent1/ before starting.";
		}
		if (!section) return;
		return { systemPrompt: `${event.systemPrompt}\n\n${section}` };
	});
}
