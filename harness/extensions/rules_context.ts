/**
 * rules context: the durable rules are in the prompt, not in a read the agent
 * can skip.
 *
 * Measured 2026-10-03: of the six files docs/rules/README.md names for session start, two
 * were never read (code_style.md and docs/rules/jobs.md) and docs/rules/git.md only when the first
 * commit came up. The misses line up with the session's costs: a 300s unbounded
 * suite run with no ETA (docs/rules/jobs.md) and ad-hoc probe scripts (code_style.md).
 *
 * pi reads AGENTS.md verbatim and does not expand `@path` imports - verified in
 * dist/core/resource-loader.js, and the docs never mention imports - so a file
 * that is only *named* stays optional. This hook appends docs/rules/README.md itself, and
 * names the topic files with what each is for, so a skipped read is a decision
 * rather than an oversight.
 *
 * Measured 2026-10-04: a fresh session asked to name itself answered "I am Pi",
 * because experimental.md was only *named*. A trial rule a session may skip is
 * not being trialled, so docs/rules/experimental.md is appended too - after docs/rules/README.md, so
 * the precedence reads in order.
 *
 * ponytail: the whole file on every run, ~270 lines. Trim it to the rules that
 * actually get missed if the context cost ever shows up in a token report.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";


const COMMON = join(homedir(), "repos/agent1/docs/rules/README.md");
const EXPERIMENTAL = join(homedir(), "repos/agent1/docs/rules/experimental.md");

/** A rule file that may not exist yet. A missing file is not an error here. */
function readIfPresent(path: string): string {
	try {
		return readFileSync(path, "utf8");
	} catch {
		return "";
	}
}

/** Topic files docs/rules/README.md points at, with the reason to read each one. */
const TOPICS: [string, string][] = [
	["docs/rules/git.md", "commits and pull requests"],
	["docs/rules/jobs.md", "ETA rules for long-running jobs"],
	["docs/rules/external.md", "probing external systems, live accounts, credentials on disk"],
	["docs/rules/browser.md", "browser and computer use rules"],
	["docs/rules/macos.md", "macOS command traps"],
	["docs/rules/agent1.md", "writing a CLI app (read section CLI)"],
	["docs/rules/markdown.md", "writing Markdown"],
	["docs/rules/pi.md", "pi package management"],
	["docs/rules/removal.md", "removing apps, packages and harnesses"],
];

/** docs/rules/repos.md matters only where ~/repos exists - the user asked for that gate,
 * and it is a pure filesystem test, decided here not by the model. */
const REPOS_TOPIC: [string, string] = [
	"docs/rules/repos.md",
	"nested git repo policy for ~/repos (loaded only when ~/repos exists)",
];

function topics(): [string, string][] {
	return existsSync(join(homedir(), "repos")) ? [...TOPICS, REPOS_TOPIC] : TOPICS;
}

export function rulesSection(
	text: string,
	topics: [string, string][] = TOPICS,
	experimental = "",
): string {
	if (!text.trim()) return "";
	const lines = [
		"## Rules (loaded from ~/repos/agent1/docs/rules/README.md)",
		"",
		text.trim(),
		"",
		"Read the topic file when the task touches it:",
		...topics.map(([name, why]) => `- agent1/${name} - ${why}`),
	];
	if (experimental.trim()) {
		lines.push(
			"",
			"## Experimental rules (loaded from ~/repos/agent1/docs/rules/experimental.md)",
			"",
			"Live trial rules. They win over anything above that conflicts, until the",
			"user promotes one into rules/ or deletes it.",
			"",
			experimental.trim(),
		);
	}
	return lines.join("\n");
}

/** The rules as they stand on disk now. Shared with harness/hook.ts. */
export function currentRules(): string {
	try {
		return rulesSection(readFileSync(COMMON, "utf8"), topics(), readIfPresent(EXPERIMENTAL));
	} catch {
		return "## Rules\n\n~/repos/agent1/docs/rules/README.md is missing, so the session-start rules did not load. Read the topic files under ~/repos/agent1/ before starting.";
	}
}

export default function (pi: ExtensionAPI) {
	pi.on("before_agent_start", (event) => {
		const section = currentRules();
		if (!section) return;
		return { systemPrompt: `${event.systemPrompt}\n\n${section}` };
	});
}
