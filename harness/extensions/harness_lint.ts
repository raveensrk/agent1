/**
 * harness lint: the reactive half of the harness.
 *
 * After the agent finishes a run, run agent1's deterministic checks over the
 * files this session edited and hand any findings, and any check that failed
 * to run, back as a message, so the agent reacts to a signal instead of being
 * asked to remember a rule. This is the pi equivalent of a Claude "Stop" hook
 * running rubocop on changed files.
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
/** A check lint.py could not run or could not read: the files it covers are not known clean. */
export type Failure = { check: string; root: string; error: string };
export type Report = { findings: Finding[]; failures: Failure[] };

export function key(entry: Finding | Failure): string {
	// A failure is one check in one repo, whatever its error says: the text can
	// change run to run, and each new text would spend another nudge.
	if ("root" in entry) return `${entry.check}:${entry.root}`;
	return `${entry.check}:${entry.path}:${entry.line}`;
}

export function lint(files: string[], cwd: string): Promise<Report> {
	return new Promise((resolve) => {
		execFile(
			"python3",
			[LINT, "--json", ...files],
			{ cwd, timeout: TIMEOUT_MS, maxBuffer: 1 << 22 },
			(_error, stdout) => {
				// lint exits 1 on findings and 2 on a failed check, and prints the JSON
				// either way; only unparsable output is a failure
				try {
					const report = JSON.parse(stdout) as Partial<Report>;
					resolve({ findings: report.findings ?? [], failures: report.failures ?? [] });
				} catch {
					resolve({ findings: [], failures: [] });
				}
			},
		);
	});
}

/** The message that hands FINDINGS, then FAILURES, back to the agent. */
export function findingsMessage(findings: Finding[], failures: Failure[] = []): string {
	const lines = findings
		.slice(0, SHOWN)
		.map((f) => `- ${f.path}:${f.line}: ${f.check}: ${f.message}`);
	if (findings.length > SHOWN) lines.push(`- and ${findings.length - SHOWN} more`);
	const found = [
		`harness lint found ${findings.length} findings in the files this session edited:`,
		...lines,
		"",
		"Fix them, or say why one is a false positive. If a rule is wrong rather than the code, say so and fix the rule.",
	];
	if (failures.length === 0) return found.join("\n");

	// The line lint.py prints on stderr, so a broken check reads the same in both places.
	const failed = [
		...failures.map((f) => `lint: check ${f.check} failed in ${f.root}: ${f.error}`),
		"",
		"A failed check is not a pass: the files it covers are not known clean. Fix the check, or tell the user it is broken.",
	];
	if (findings.length === 0) return failed.join("\n");
	return [...found, "", ...failed].join("\n");
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

		const report = await lint(files, ctx.cwd);
		const findings = report.findings.filter((f) => !reported.has(key(f)));
		const failures = report.failures.filter((f) => !reported.has(key(f)));
		if (findings.length === 0 && failures.length === 0) return;
		[...findings, ...failures].forEach((f) => reported.add(key(f)));
		continuations += 1;

		return {
			entries: [
				{
					type: "custom_message",
					customType: "harness-lint",
					content: findingsMessage(findings, failures),
					display: true,
				},
			],
			continue: true,
		};
	});
}
