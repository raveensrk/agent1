/**
 * Prompts for model and thinking level on every session start
 * (startup, resume, new, fork, reload). Esc keeps the current value.
 */
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import type { ThinkingLevel } from "@earendil-works/pi-ai";

const LEVELS: ThinkingLevel[] = ["minimal", "low", "medium", "high", "xhigh", "max"];

export default function (pi: ExtensionAPI) {
	pi.on("session_start", async (_event, ctx) => {
		await pick(ctx);
	});

	async function pick(ctx: ExtensionContext) {
		if (!ctx.hasUI) return;

		// Model picker: current choice first, rest sorted
		const models = [...ctx.modelRegistry.getAllModels()];
		const cur = pi.getModel();
		const label = (m: any) => `${m.provider}/${m.id}`;
		models.sort((a: any, b: any) => {
			const acur = cur && a.provider === cur.provider && a.id === cur.id;
			const bcur = cur && b.provider === cur.provider && b.id === cur.id;
			if (acur !== bcur) return acur ? -1 : 1;
			return label(a).localeCompare(label(b));
		});
		const picked = await ctx.ui.select(
			"Model",
			models.map((m: any) => label(m) + (cur && label(m) === label(cur) ? "  (current)" : "")),
		);
		if (picked) {
			const m = models.find((x: any) => label(x) === picked.replace("  (current)", ""));
			if (m) await pi.setModel(m as any);
		}

		// Thinking level picker
		const level = await ctx.ui.select("Thinking level", LEVELS);
		if (level) pi.setThinkingLevel(level as ThinkingLevel);
	}
}
