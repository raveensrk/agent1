/**
 * Prompts for model and thinking level on session start, except reload.
 * Searchable pickers like
 * /model and /thinking; Esc keeps the current value.
 */
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import type { ThinkingLevel } from "@earendil-works/pi-ai";
import { Container, SelectList, Text, type SelectItem } from "@earendil-works/pi-tui";

const LEVELS: ThinkingLevel[] = ["minimal", "low", "medium", "high", "xhigh", "max"];

export default function (pi: ExtensionAPI) {
	pi.on("session_start", async (event, ctx) => {
		if (event.reason !== "reload") await pick(ctx);
	});

	async function pick(ctx: ExtensionContext) {
		if (!ctx.hasUI) return;

		// Model picker: current first, rest sorted, searchable
		const cur = (ctx as ExtensionContext).model;
		const label = (m: { provider: string; id: string }) => `${m.provider}/${m.id}`;
		const models = [...ctx.modelRegistry.getAvailable()];
		models.sort((a: any, b: any) => {
			const acur = cur && label(a) === label(cur);
			const bcur = cur && label(b) === label(cur);
			if (acur !== bcur) return acur ? -1 : 1;
			return label(a).localeCompare(label(b));
		});
		const items: SelectItem[] = models.map((m: any) => ({
			value: label(m),
			label: cur && label(m) === label(cur) ? `${label(m)}  (current)` : label(m),
		}));
		const picked = await chooser(ctx, "Select model", items);
		if (picked) {
			const m = models.find((x: any) => label(x) === picked);
			if (m) await pi.setModel(m as any);
		}

		// Thinking level picker
		const level = await chooser(ctx, "Select thinking level", LEVELS.map((l) => ({
			value: l,
			label: l,
		})));
		if (level) pi.setThinkingLevel(level as ThinkingLevel);
	}

	// Searchable SelectList overlay; resolves to item value or null on Esc
	function chooser(ctx: ExtensionContext, title: string, items: SelectItem[]): Promise<string | null> {
		return ctx.ui.custom<string | null>((tui, theme, _kb, done) => {
			const container = new Container();
			container.addChild(new Text(theme.fg("accent", theme.bold(title))));

			const selectList = new SelectList(items, Math.min(items.length, 10), {
				selectedPrefix: (text) => theme.fg("accent", text),
				selectedText: (text) => theme.fg("accent", text),
				description: (text) => theme.fg("muted", text),
				scrollInfo: (text) => theme.fg("dim", text),
				noMatch: (text) => theme.fg("warning", text),
			});
			selectList.onSelect = (item) => done(item.value);
			selectList.onCancel = () => done(null);
			container.addChild(selectList);

			container.addChild(new Text(theme.fg("dim", "type to filter • ↑↓ navigate • enter select • esc cancel")));

			return {
				render(width: number) {
					return container.render(width);
				},
				invalidate() {
					container.invalidate();
				},
				handleInput(data: string) {
					selectList.handleInput(data);
					tui.requestRender();
				},
			};
		});
	}
}
