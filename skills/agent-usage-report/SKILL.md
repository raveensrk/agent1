---
name: agent-usage-report
description: Build a self-contained interactive HTML report of every AI model used across agent harnesses (pi, Claude Code, Codex, opencode) with tokens, cost, cost per 1M, interactive charts, a session drilldown, and the market verdict - the world's three most-used frontier and three most-used flash-tier models (OpenRouter usage share, Artificial Analysis tiers), highlighted in the report. Use when the user asks what models they used, token or spend totals, a usage report, or "how much have I spent on AI".
argument-hint: "[0d | -1d | -Nd | -N | -Nw | --since YYYY-MM-DD | --until YYYY-MM-DD]"
---

# Agent usage report

Read the token logs every agent harness on this machine writes, price them,
score the models, and open one HTML report. The bundled script does all the
reading and math; you choose the window and relay the result.

## Requirements

- python3 3.9+ with `pip install -r requirements.txt` (plotly, jsonschema,
  rich). `jsonschema` and `rich` degrade gracefully if missing.
- Works on macOS and Linux.
- Network: pricing from models.dev (24h cache + bundled offline snapshot) and
  benchmarks/verdict data from the Artificial Analysis and OpenRouter APIs
  (24h cache). Offline runs degrade gracefully: spend and charts stay,
  benchmark columns and the verdict show setup hints.

## What it reads

| Harness | Default location | Cost |
|---|---|---|
| pi | `~/.pi/agent/sessions/**/*.jsonl` | recorded |
| Claude Code | `~/.claude/projects/**/*.jsonl` | computed |
| Codex | `~/.codex/sessions/**/rollout-*.jsonl`, `~/.codex/archived_sessions/` | computed |
| opencode | `~/.local/share/opencode/opencode.db` (SQLite) | recorded |
| OpenCode Zen/Go | opencode.ai console API (needs `~/.local/share/opencode_usage/zen_cookie`); lifetime aggregates only — all-time reports include them, windowed ones skip them | recorded |

Missing harnesses are skipped, not an error. Add others with
`extra_harnesses` in the config (see Setup).

## What the report contains

- Headline totals: spend, tokens, models, sessions, requests, cache hit rate.
- Model leaderboard: turns, input, output, total, blended $/1M, cost, AA
  Intelligence Index, efficiency, with a recorded vs computed cost badge.
  Models in the market verdict get a green tint and a `market top` badge;
  rows without an AA benchmark match are dimmed. Click any column header to
  sort, filter by any text, harness, or AA-matched-only; the row count updates
  live. Sorting and filtering need JavaScript; without it the table still
  renders, just unsorted and unfiltered.
- The verdict: the world's 3 most-used frontier models and 3 most-used
  flash-tier models (daily OpenRouter token share), each flagged
  "you use it" or "not in your logs".
- Charts: cost per 1M, where the money went, spend over time and burn rate,
  projects, tool usage, context pressure, an activity heatmap, model switching,
  and a waste report (failed or aborted turns and their cost).
- Interactive HTML report (plotly, inlined): still one self-contained file,
  no network needed to view it. Every bar chart has sort / top-N / filter
  menus; line charts, heatmap, donut and scatter support zoom and hover.
- A session drilldown table: the top 20 most expensive sessions.

Token fields are normalised so they always add up:
`total = input + cache_read + cache_write + output`, where `input` is uncached.
Codex folds cached tokens into its input counter, and the adapter subtracts
them, so totals stay comparable across harnesses.

## How the verdict works

The verdict is the market's, not yours: the **3 most-used frontier models** and
the **3 most-used flash-tier models** worldwide, ranked by daily OpenRouter
token share. When one of the six also appears in your logs, it is flagged
"you use it" in the verdict card and highlighted with a `market top` badge on
its leaderboard row.

Tier membership comes from Artificial Analysis data, never a hardcoded list:

- **Frontier**: top quartile of the AA Intelligence Index catalog, so the bar
  moves as the market moves.
- **Flash tier**: a model whose name carries flash/mini/lite/turbo/nano/
  instant/hydro, or one that is cheap and fast per AA data (blended price
  <= $0.5/1M and >= 80 output tokens/sec). A model named flash stays flash
  even if it scores high.

Supporting analysis (still in the report, not the verdict): per-model AA
Intelligence Index and efficiency (AA index per $1/1M you actually paid),
both derived only from models in your logs.

- AA benchmarks need a free key: `aa_api_key` in config.json or `AA_API_KEY`
  env. Market usage share needs a free OpenRouter key: `openrouter_api_key`
  in config.json or `OR_API_KEY` env. Both cached 24 hours.
- Name mismatches or pinned values: `~/.local/share/agent_report/aa.json`,
  keyed by your log's model name:
  `{"claude-opus-5": {"intelligence_index": 68.4}}`.
- Model names are normalised across harnesses (pi's `anthropic/claude-opus-5`
  and Claude Code's `claude-opus-5` merge into one row, one sample).

Benchmark scores describe models in general; the cost figures describe your
usage. Do not mix the two into a general claim about a model's value for
someone else.

## Hard rules

- Run `scripts/report.py` unchanged. Do not re-implement its parsing.
- Read-only. The script never writes to any harness log or database.
- Never invent, merge, or drop models, and never round a total by hand. Report
  only what the script prints or writes.
- The report holds your spend. It is written to `~/Downloads` by default, or
  to `output_dir` in the config, or `--out`. The script refuses to write inside
  a git repository and exits with `ERROR:` if you try.
- If the script prints a line starting with `ERROR:`, stop, show it, and fix
  the cause.

## Step 1 - Window

Pass a shortcut as the first argument, or `--since` / `--until`.

| Shortcut | Window |
|---|---|
| `0d` | today, midnight to now |
| `-1d` | yesterday only, midnight to midnight |
| `-Nd` | that one day, N days ago |
| `-N` | last N days, today included, ending now |
| `-Nw` | last N weeks, ending now |

- No argument means **all time**. This is the default; the report is a
  lifetime view unless asked otherwise.
- Map plain words: "today" is `0d`, "yesterday" is `-1d`, "last 7 days" is `-7`,
  "this week" is `-1w`.
- For any other window, work out the dates from the current local date
  (`date`) and pass `--since "YYYY-MM-DD HH:MM"` and `--until`.
- Ask one question if the window is ambiguous.

## Step 2 - Run

Run from this skill's directory, with `<skill_dir>` being the directory holding
this file. It takes a few seconds.

```bash
python3 <skill_dir>/scripts/report.py
python3 <skill_dir>/scripts/report.py -7
python3 <skill_dir>/scripts/report.py --since "2026-09-01" --until "2026-09-15"
python3 <skill_dir>/scripts/report.py --out ~/Downloads/agent_report.html
```

Useful flags:

- `--check` - detect harnesses, count records, resolve prices, write nothing.
- `--check --check-pricing` - also report how many models were priced.
- `--no-open` - write the report without opening a browser.
- `--project-name` - reveal real project names. Default hides them: projects
  and sessions are labelled `Project 1, Project 2, ...` so the report never
  leaks repo or directory names (it lands in `~/Downloads`, not in git).
- `--offline` - never touch the network; use the cached or bundled prices.
- `--refresh-pricing` - re-fetch models.dev prices, AA benchmarks and the
  OpenRouter usage share now.
- `--config PATH` - use a specific config file.

The script prints a summary: harnesses found, totals, the market verdict, and
both output paths. It writes to `~/Downloads` unless `--out` or `output_dir` says
otherwise, and opens the HTML in the browser unless `--no-open`.

## Step 3 - Report

After running, reply in chat with:

1. The window and the harnesses that contributed.
2. Totals: tokens, spend, turns, requests, sessions. Say how much of the spend
   is recorded versus estimated.
3. The verdict: name the six verdict models (3 frontier, 3 flash tier) with
   their market share, and mark which ones you used (a `*` in the CLI marks
   them).
4. Benchmark coverage: how many of your models matched AA data, and one line
   on your most efficient model (AA index per $1/1M).
5. One line on the biggest cost driver.
6. The HTML path, and whether the browser opened.

Keep it short. The HTML carries the detail; the chat message is the summary.
If the user asks "why", open the report and quote the relevant section rather
than recomputing.

## Config

Optional, at `~/.local/share/agent_report/config.json`:

```json
{
  "output_dir": "~/Downloads",
  "aa_api_key": "your-free-key-from-artificialanalysis.ai",
  "openrouter_api_key": "your-free-key-from-openrouter.ai-keys",
  "extra_harnesses": [
    {"name": "amp", "label": "Amp", "glob": "~/.amp/**/*.jsonl"}
  ]
}
```

`AA_API_KEY` and `OR_API_KEY` environment variables work too. Benchmark and
usage-share data cache under `~/.local/share/agent_report/` (aa_models.json,
or_rankings.json) for 24 hours; delete them to force a refetch.

`extra_harnesses` turns on the generic JSONL sniffer, which finds any object
with an input-ish and output-ish token key (`input_tokens`/`output_tokens`,
`prompt_tokens`/`completion_tokens`, and camelCase variants).

Price overrides go in `~/.local/share/agent_report/prices.json`, keyed by
`provider/model`, in dollars per million:

```json
{ "anthropic/claude-opus-5": {"input": 5, "output": 25, "cache_read": 0.5, "cache_write": 6.25} }
```

Resolution order: your `prices.json`, then `~/.pi/agent/models-store.json`,
then models.dev, then the bundled snapshot.

## Setup - add a harness

1. Run `python3 <skill_dir>/scripts/report.py --check` to see what is detected.
2. If the harness is not listed, find its log directory and format.
3. If it writes JSONL with a usage object, add it under `extra_harnesses` and
   re-run `--check`.
4. If it needs real parsing (SQLite, protobuf, unusual field names), add a
   module in `scripts/adapters/` exposing `NAME`, `LABEL`, `available()`,
   `discover()`, `records()`, and register the name in
   `scripts/adapters/__init__.py`. Copy `adapters/pi.py` as the template and
   add a fixture under `tests/fixtures/`.

## Maintenance

- `python3 scripts/refresh_snapshot.py` updates the offline price snapshot.
- `python3 tests/run_tests.py` runs the adapter, pricing, scoring and render
  tests against fixtures. Run it after any edit.
