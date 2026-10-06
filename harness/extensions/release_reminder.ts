import { mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export function remind(dir: string, version: string, notify: (message: string) => void) {
	const file = join(dir, "last_notified_pi_version");
	let previous: string | undefined;
	try {
		previous = readFileSync(file, "utf8").trim();
	} catch (err) {
		if ((err as NodeJS.ErrnoException).code !== "ENOENT") throw err;
	}
	if (previous === version) return;
	// Missing state establishes baseline; only subsequent changes notify.
	if (previous !== undefined) {
		notify(`Pi changed ${previous || "unknown"} → ${version}. Run /skill:pi-release-upgrade`);
	}
	mkdirSync(dir, { recursive: true });
	const tmp = `${file}.${process.pid}.tmp`;
	writeFileSync(tmp, `${version}\n`, { mode: 0o600 });
	renameSync(tmp, file);
}

export default function (pi: ExtensionAPI) {
	pi.on("session_start", async (_event, ctx) => {
		if (ctx.mode !== "tui") return; // Headless probes must not consume reminders.
		const { getAgentDir, VERSION } = await import("@earendil-works/pi-coding-agent");
		remind(getAgentDir(), VERSION, (message) => ctx.ui.notify(message, "info"));
	});
}
