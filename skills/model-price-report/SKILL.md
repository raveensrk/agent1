---
name: model-price-report
description: Compare LLM subscription plans, first-party API prices, and Artificial Analysis intelligence scores for every published thinking effort, then open or write a dark HTML report. Use when the user asks for model pricing, intelligence scores, effort or reasoning levels, Grok or SuperGrok plans, DeepSeek, GLM, or a model score report. Pass --overwrite to replace the newest report in place.
---

# Model price report

One current intelligence scale. First-party prices. Every published effort, not just the top score. Do not invent a missing cell.

## Reuse

Search `~/tmp` then `/tmp/explain` for `<snake_case_topic>*.html`. Use `stat` mtime. Pick the newest match.

- `--overwrite`: rewrite the newest match in place, even if it is younger than 7 days. Tell the user the path you overwrote. If no match exists, write `~/tmp/<snake_case_topic>.html` and say it is new.
- Younger than 7 days, no flag: `open` it and stop. Tell the user the path and the age in days. Do not write.
- 7 days or older, no flag: do not overwrite it. Write `~/tmp/<snake_case_topic>_<YYYYMMDD>.html`. Tell the user the old path, its age, and the new path.
- None found: write `~/tmp/<snake_case_topic>.html`. Tell the user it is new.

`--overwrite` is the only permission to overwrite. "refresh" or "update" without that flag still follows the age rules.

## Sources, in order

1. First-party price page for each lab. Fetch it. A blocked marketing site stays unverified.
2. Artificial Analysis release page for that model. It lists the published efforts (`xhigh`, `high`, `max`, `medium`, `low`, non-reasoning). Then the model or comparison page for each effort's index score and dollars per index task.
3. Subscription pages only if the user asked about a consumer plan. Subscription price is not API price. Say they are separate bills.

Blogs lose when they disagree with a fetched first-party page. A faster or larger sibling (example: FlashX) is a different model, not an effort level.

## Rules

- Record the index version (example: v4.3.2). Do not mix an older index into the table or the bars.
- Compare index scores, not AA page ranks.
- List price is often identical across efforts. Still show input, cached input, and output on every effort row. Show AA dollars per task when retrieved. Higher effort costs more because reasoning tokens bill as output.
- Long-context, peak or off-peak, cache, and regional multipliers stay in the price note. Do not collapse them into one rate.
- A dash means not retrieved. Never write 0. Mark AA estimates (`*`) as estimates.
- Vendor self-benchmarks stay labeled as vendor numbers.
- Plain hyphens only. No em dashes.

## Report

One file. CSS inlined. No CDN. No remote fonts. Dark theme: background `#07080c`, card `#141821`, text `#f3efe6`, muted `#9b968c`, gold kicker `#e4b15a`. System sans. Radial gold and blue glows. 16px radius cards.

Required sections:

1. Hero and 3 stat cards.
2. Effort table, one row per published effort: model, effort, index, input, cached input, output, AA dollars per task.
3. Numbered how-to-use list.
4. Source links.
5. Yellow caveat box for anything not fetched.

Then `open` the file. Tell the user the path.

Skipped: charts library, live picker scrape, rank column. Add a chart lib only if the user asks for interactive sort.
