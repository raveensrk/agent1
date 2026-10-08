/**
 * failure_nudge: one line offers learn-from-failure after repeated hard errors.
 *
 * The signal is the streak, as the user picked it: one hard error is noise,
 * two in a row is a pattern. The nudge fires once when the streak reaches the
 * limit and stays quiet until a successful result resets it, so a session
 * that keeps failing does not get spammed. Interactive sessions only; print
 * mode has no one to nudge.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export const NUDGE_AT = 2;

export function nudgeText(tool: string): string {
	return `${tool} failed twice in a row - say "learn from failure" to scan and fix`;
}

export default function (pi: ExtensionAPI) {
	let streak = 0;

	pi.on("tool_result", (event, ctx) => {
		if (!event.isError) {
			streak = 0;
			return;
		}
		streak += 1;
		if (streak !== NUDGE_AT || !ctx.hasUI) return;
		ctx.ui.notify(nudgeText(event.toolName), "info");
	});
}
