# agent-usage-report

An [Agent Skill](https://agentskills.io) that builds one self-contained HTML
report of every AI model you used, across every agent harness on your machine:
tokens, cost, cost per 1 million tokens, and which model is the most
intelligent and which is the most efficient.

The repo root **is** the skill: `SKILL.md` plus its `scripts/`, `assets/` and
`tests/`.

```
SKILL.md                              how an agent runs this
scripts/report.py                     CLI entry point
scripts/collect.py                    reads harnesses, segments turns into requests
scripts/pricing.py                    prices via models.dev, pi store, bundled snapshot
scripts/benchmarks.py                 AA Intelligence Index via the AA API (24h cache)
scripts/popularity.py                 market usage share via the OpenRouter API (24h cache)
scripts/score.py                      efficiency, tier classification, market verdict
scripts/render.py                     interactive plotly charts, self-contained HTML
scripts/adapters/                     one module per harness
assets/prices_snapshot.json.gz        offline price table (~80 KB)
tests/                                fixture-based tests
```

## Requirements

- python3 3.9+ plus `pip install -r requirements.txt` (plotly, jsonschema,
  rich). `jsonschema` and `rich` degrade gracefully if missing.
- macOS or Linux.
- Network is optional: pricing comes from
  [models.dev](https://models.dev/api.json), cached for 24 hours, with a
  bundled offline snapshot as fallback.

## Install

This skill lives in the [agents](https://github.com/raveensrk/agents) repo at
`skills/agent-usage-report/`. Install it from there (and record it for a clean
uninstall):

```bash
~/repos/agent1/install.py
```

Otherwise symlink this directory into each harness's skills directory by hand:

```bash
ln -s ~/repos/agent1/skills/agent-usage-report ~/.agents/skills/agent-usage-report   # pi, Codex
ln -s ~/repos/agent1/skills/agent-usage-report ~/.claude/skills/agent-usage-report   # Claude Code
```

Reload the harness (pi: `/reload`) after installing or editing.

## Usage

Run from the repo root.

```bash
python3 scripts/report.py                 # all time, opens the report
python3 scripts/report.py -7              # last 7 days
python3 scripts/report.py -1d             # yesterday
python3 scripts/report.py --since 2026-09-01 --until 2026-09-15
python3 scripts/report.py --check         # detect harnesses, write nothing
python3 scripts/report.py --offline --no-open
```

| Shortcut | Window |
|---|---|
| `0d` | today, midnight to now |
| `-1d` | yesterday only |
| `-Nd` | that one day, N days ago |
| `-N` | last N days, today included |
| `-Nw` | last N weeks |

The report is one self-contained HTML file (plotly.js is inlined, so it is
several MB) written to `~/Downloads` and opened in the browser. Override with
`--out PATH`, or `output_dir` in the config. The script refuses to write inside
a git repository, because the report contains your spend.

## Harnesses

| Harness | Location | Cost |
|---|---|---|
| pi | `~/.pi/agent/sessions/**/*.jsonl` | recorded |
| Claude Code | `~/.claude/projects/**/*.jsonl` | computed |
| Codex | `~/.codex/sessions/**/rollout-*.jsonl` | computed |
| opencode | `~/.local/share/opencode/opencode.db` | recorded |

Add an unrecognised harness that writes JSONL with a usage object by declaring
it in `~/.local/share/agent_report/config.json`:

```json
{
  "extra_harnesses": [
    {"name": "amp", "label": "Amp", "glob": "~/.amp/**/*.jsonl"}
  ]
}
```

For a harness that needs real parsing (SQLite, protobuf, unusual field names),
add a module under `scripts/adapters/` exposing `NAME`, `LABEL`, `available()`,
`discover()` and `records()`, then register it in `scripts/adapters/__init__.py`.
Copy `scripts/adapters/pi.py` as the template.

Every adapter normalises its token accounting so that
`total = input + cache_read + cache_write + output`, where `input` is uncached.
Codex folds cached tokens into its input counter, and the adapter subtracts
them, so totals stay comparable across harnesses.

## Scoring

## The verdict

The verdict is the market's, not yours: the 3 most-used frontier models and
the 3 most-used flash-tier models worldwide, ranked by daily OpenRouter token
share (free key: `openrouter_api_key` in config or `OR_API_KEY` env). Models
that also appear in your logs are flagged "you use it" and highlighted with a
`market top` badge on their leaderboard row.

Tier membership comes from Artificial Analysis data, never a hardcoded list:
frontier = top quartile of the AA Intelligence Index catalog; flash tier =
models whose name carries flash/mini/lite/turbo/nano/instant/hydro, or that
are cheap (blended price <= $0.5/1M) and fast (>= 80 output tokens/sec) per
AA data. A model named flash stays flash even if it scores high.

## Scoring

Model quality comes from the Artificial Analysis Intelligence Index, an
independent public benchmark (0-100), not from your usage. Benchmark data is
fetched live from the AA API (free key: set `aa_api_key` in config or
`AA_API_KEY` env), cached 24 hours; pin or fix values in
`~/.local/share/agent_report/aa.json` keyed by your log's model name.

| Metric | Source | Direction |
|---|---|---|
| AA Intelligence Index | artificialanalysis.ai | higher better |
| $ per 1M tokens | your blended cost | lower better |

Efficiency = AA index divided by the blended cost per 1M tokens you paid, then
ranked. Models without an AA benchmark match are dimmed.

Model names are normalised across harnesses, so the same model logged under
different spellings (pi's `anthropic/claude-opus-5`, Claude Code's
`claude-opus-5`) merges into one leaderboard row and one score sample.

The report also includes a session drilldown: the 20 most expensive sessions,
with project, model mix and cost provenance.

Set your keys and output dir in
`~/.local/share/agent_report/config.json`:

```json
{
  "output_dir": "~/Downloads",
  "aa_api_key": "your-free-key-from-artificialanalysis.ai",
  "openrouter_api_key": "your-free-key-from-openrouter.ai-keys"
}
```

Price overrides live in `~/.local/share/agent_report/prices.json`, keyed by
`provider/model` in dollars per million:

```json
{ "anthropic/claude-opus-5": {"input": 5, "output": 25, "cache_read": 0.5, "cache_write": 6.25} }
```

Resolution order: your `prices.json`, then `~/.pi/agent/models-store.json`,
then models.dev, then the bundled snapshot. Harnesses that log real spend
(pi, opencode) keep it; every other cost is an estimate, badged as such in the
report.

## Tests

```bash
python3 tests/run_tests.py
```

The adapter tests point every harness at `tests/fixtures/` through environment
overrides, so they never read real logs. Expected token totals are written out
explicitly: if an adapter changes its parsing, the tests fail loudly.

`python3 scripts/refresh_snapshot.py` regenerates the offline price snapshot.

## License

MIT. See [LICENSE](./LICENSE).
