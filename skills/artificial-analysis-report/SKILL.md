---
name: artificial-analysis-report
description: Stats-only Artificial Analysis report for the newest GLM, DeepSeek and Grok model, listing every published effort with index, token prices and AA dollars per task. Use when the user asks for /artificial-analysis-report, an artificial analysis report, the latest GLM or DeepSeek or Grok model stats, or all effort levels for those models.
---

# Artificial Analysis report

One dark HTML page. Stats only: no prose, no sources, no how-to. Newest model
per lab, every effort level Artificial Analysis published for it.

## Run

```bash
~/repos/agent1/skills/artificial-analysis-report/scripts/artificial_analysis_report.py
```

The script does the whole job: fetch, write `/Users/raveen_kumar_personal/tmp/artificial_analysis_report.html`, open it in Firefox. Do not hand-build the page or re-fetch anything.

- `AA_API_KEY` must be set. It is already in the environment; missing key exits with one line, no report.
- Labs: `Z AI` (GLM), `DeepSeek`, `SpaceXAI` (Grok). Their names as the AA API spells them are the `LABS` list in the script. A fourth lab is one string.
- Newest = highest `release_date` for that lab. Variants = same release date and same name before the parenthesis. That is what makes Grok 4.7 low, high and xhigh one table.
- Prices come from the AA API; cached input and dollars per task come from the AA comparison pages, which are the only place AA prints them.

## Rules

- The path is stable and rewritten every run. A newer model must replace the old page, so never reuse a previous report and never ask about overwriting.
- The table is sorted by index score, highest first. Rows without a published score sit at the bottom.
- Every dash is a not-retrieved cell. Never write 0, never guess an effort level AA did not publish.
- Index version is read off the comparison page and printed in the kicker. Never mix versions.
- First-party list prices, subscription plans, and long-context quirks are out of scope. That is [model-price-report](../model-price-report/SKILL.md).

## Check

```bash
~/repos/agent1/skills/artificial-analysis-report/scripts/artificial_analysis_report.py --self-test
```

Passes on the fixed comparison-page fixture: parser, version, prices, dashes.
Run it after touching the parser. Then run the report twice and confirm the
table changes only where AA changed.
