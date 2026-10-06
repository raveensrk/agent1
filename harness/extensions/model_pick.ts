/**
 * Prompts for model and thinking level on session start, except reload.
 * Searchable pickers like
 * /model and /thinking; Esc keeps the current value.
 */
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import type { ThinkingLevel } from "@earendil-works/pi-ai";
import { Container, fuzzyFilter, getKeybindings, Input, SelectList, Spacer, Text, type SelectItem } from "@earendil-works/pi-tui";

const LEVELS: ThinkingLevel[] = ["minimal", "low", "medium", "high", "xhigh", "max"];

export default function (pi: ExtensionAPI) {
	pi.on("session_start", async (event, ctx) => {
		if (event.reason === "reload" || ctx.mode !== "tui") return;
		await pick(ctx);
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

	// Fuzzy-searchable picker; resolves to item value or null on Esc.
	function chooser(ctx: ExtensionContext, title: string, items: SelectItem[]): Promise<string | null> {
		return ctx.ui.custom<string | null>((tui, theme, _kb, done) => {
			const container = new Container();
			const search = new Input({ prompt: "Search: ", placeholder: "type to filter" });
			search.focused = true;
			const listBox = new Container();
			const style = {
				selectedPrefix: (text: string) => theme.fg("accent", text),
				selectedText: (text: string) => theme.fg("accent", text),
				description: (text: string) => theme.fg("muted", text),
				scrollInfo: (text: string) => theme.fg("dim", text),
				noMatch: (text: string) => theme.fg("warning", text),
			};
			let list: SelectList;

			function buildList(filtered: SelectItem[]) {
				list = new SelectList(filtered, Math.max(1, Math.min(filtered.length, 10)), style);
				list.onSelect = (item) => done(item.value);
				list.onCancel = () => done(null);
				listBox.clear();
				listBox.addChild(list);
			}

			container.addChild(new Text(theme.fg("accent", theme.bold(title))));
			container.addChild(new Spacer(1));
			container.addChild(search);
			container.addChild(new Spacer(1));
			container.addChild(listBox);
			container.addChild(new Spacer(1));
			container.addChild(new Text(theme.fg("dim", "type to search · ↑↓ navigate · enter select · esc cancel")));
			buildList(items);

			return {
				render(width: number) {
					return container.render(width);
				},
				invalidate() {
					container.invalidate();
				},
				handleInput(data: string) {
					const kb = getKeybindings();
					const isNav = kb.matches(data, "tui.select.up") ||
						kb.matches(data, "tui.select.down") ||
						kb.matches(data, "tui.select.confirm") ||
						kb.matches(data, "tui.select.cancel");
					if (isNav) {
						list.handleInput(data);
					} else {
						search.handleInput(data);
						const query = search.getValue();
						buildList(query ? fuzzyFilter(items, query, (item) => `${item.label} ${item.value} ${item.description ?? ""}`) : items);
					}
					tui.requestRender();
				},
			};
		});
	}
}
