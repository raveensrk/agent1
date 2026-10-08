/**
 * telegraph: the voice rule lives with its switch, not in experimental.md.
 *
 * The rule was prose in experimental.md, so turning it off meant editing the
 * rules file. The switch belongs to the feature: /telegraph on|off decides
 * whether telegraph.md reaches the prompt on the next request, and off leaves
 * nothing behind.
 *
 * The rule is appended, never replaced. pi hands each before_agent_start handler
 * the prompt as it stands and takes the last returned systemPrompt, so
 * `${event.systemPrompt}\n\n${ruleSection(...)}` composes with rules_context.ts
 * in either load order.
 *
 * The Jev score line is its own command instead: /voice-score in voice_score.ts,
 * one classifier call per run asked about. Thresholds and evidence for that
 * number live in voice_score.ts.
 *
 * Config: ~/.local/state/agent1/telegraph.json {"enabled": bool}, one switch
 * for every harness - Claude Code reads it through harness/hook.ts. Absent or
 * malformed means on, because a missing switch must not silently drop a voice
 * rule.
 */
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export const RULE_PATH = join(homedir(), "repos/agent1/harness/extensions/telegraph.md");
export const CONFIG_PATH = join(homedir(), ".local/state/agent1/telegraph.json");

export function readEnabled(path = CONFIG_PATH): boolean {
	try {
		const config = JSON.parse(readFileSync(path, "utf8")) as { enabled?: unknown };
		return config.enabled !== false;
	} catch {
		return true;
	}
}

export function writeEnabled(enabled: boolean, path = CONFIG_PATH): void {
	mkdirSync(dirname(path), { recursive: true });
	writeFileSync(path, `${JSON.stringify({ enabled }, null, 2)}\n`);
}

/** The rule file verbatim, or empty when it is missing. */
export function readRule(path = RULE_PATH): string {
	try {
		return readFileSync(path, "utf8").trim();
	} catch {
		return "";
	}
}

/** The rule with its provenance, ready to append to a prompt. */
export function ruleSection(rule: string, path = RULE_PATH): string {
	if (!rule.trim()) return "";
	return [
		`## Voice rules (loaded from ${path})`,
		"",
		rule.trim(),
	].join("\n");
}

export default function (pi: ExtensionAPI) {
	pi.on("before_agent_start", (event) => {
		if (!readEnabled()) return;
		const section = ruleSection(readRule());
		if (!section) return;
		return { systemPrompt: `${event.systemPrompt}\n\n${section}` };
	});

	pi.registerCommand("telegraph", {
		description: "Turn the telegraph voice rule on or off, or show its state",
		handler: async (args, ctx) => {
			const word = args.trim().toLowerCase();
			const enabled = readEnabled();
			if (word === "on" || word === "off") {
				writeEnabled(word === "on");
				ctx.ui.notify(
					word === "on"
						? `telegraph rule: on - injected from ${RULE_PATH}`
						: "telegraph rule: off - the section is dropped from the next request",
					"info",
				);
				return;
			}
			if (word && word !== "status") {
				ctx.ui.notify("usage: /telegraph on|off|status", "warning");
				return;
			}
			ctx.ui.notify(
				`telegraph rule: ${enabled ? "on" : "off"} - rule ${readRule() ? "found" : "MISSING"} at ${RULE_PATH}; the Jev score is /voice-score`,
				"info",
			);
		},
	});
}
