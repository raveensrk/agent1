/**
 * harness lint: the reactive half of the harness.
 *
 * After the agent finishes a run, run agent1's deterministic checks over the
 * files this session edited and hand any findings back as a message, so the
 * agent reacts to a signal instead of being asked to remember a rule. This is
 * the pi equivalent of a Claude "Stop" hook running rubocop on changed files.
 *
 * The full-population run stays a deliberate act (`python3 harness/lint.py
 * --repos`); this only ever looks at what this session touched, because a repo
 * full of old findings would otherwise nag on every run.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { execFile } from "node:child_process";
import { homedir } from "node:os";
import { join } from "node:path";

const LINT = join(homedir(), "repos/agent1/harness/lint.py");
// ponytail: fixed caps, raise them if a session ever needs more than three nudges
export const MAX_CONTINUATIONS = 3;
const SHOWN = 20;
const TIMEOUT_MS = 30_000;

export type Finding = { check: string; path: string; line: number; message: string };

export function key(finding: Finding): string {
	return `${finding.check}:${finding.path}:${finding.line}`;
}

export function lint(files: string[], cwd: string): Promise<Finding[]> {
	return new Promise((resolve) => {
		execFile(
			"python3",
			[LINT, "--json", ...files],
			{ cwd, timeout: TIMEOUT_MS, maxBuffer: 1 << 22 },
			(_error, stdout) => {
				// lint exits 1 when it finds something; only unparsable output is a failure
				try {
					resolve((JSON.parse(stdout) as { findings?: Finding[] }).findings ?? []);
				} catch {
					resolve([]);
				}
			},
		);
	});
}

/** The message that hands FINDINGS back to the agent. */
export function findingsMessage(findings: Finding[]): string {
	const lines = findings
		.slice(0, SHOWN)
		.map((f) => `- ${f.path}:${f.line}: ${f.check}: ${f.message}`);
	if (findings.length > SHOWN) lines.push(`- and ${findings.length - SHOWN} more`);
	return [
		`harness lint found ${findings.length} findings in the files this session edited:`,
		...lines,
		"",
		"Fix them, or say why one is a false positive. If a rule is wrong rather than the code, say so and fix the rule.",
	].join("\n");
}

export default function (pi: ExtensionAPI) {
	let edited = new Set<string>();
	let reported = new Set<string>();
	let continuations = 0;

	pi.on("agent_start", () => {
		continuations = 0;
	});

	pi.on("tool_call", (event) => {
		if (event.toolName !== "write" && event.toolName !== "edit") return;
		const path = (event.input as { path?: unknown }).path;
		if (typeof path === "string") edited.add(path);
	});

	pi.on("agent_before_settle", async (event, ctx) => {
		if (edited.size === 0 || continuations >= MAX_CONTINUATIONS) return;
		const files = [...edited];
		edited = new Set();

		const findings = (await lint(files, ctx.cwd)).filter((f) => !reported.has(key(f)));
		if (findings.length === 0) return;
		findings.forEach((f) => reported.add(key(f)));
		continuations += 1;

		return {
			entries: [
				{
					type: "custom_message",
					customType: "harness-lint",
					content: findingsMessage(findings),
					display: true,
				},
			],
			continue: true,
		};
	});
}
