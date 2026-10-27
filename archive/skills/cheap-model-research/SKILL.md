---
name: cheap-model-research
metadata:
  scope: global
description: Deep research on the currently available cheap and intelligent LLMs, restricted to models available in pi and/or opencode (availability marked), written as a self-contained HTML report in ~/Downloads. Use when the user asks for a cheap model comparison, model price/intelligence report, or "which cheap model should I use". Free models are included and marked.
---

# Cheap model research

Build a self-contained HTML report of the cheapest models with usable
intelligence that `pi` and/or `opencode` can use. Each model is tagged with
its availability: both / pi only / opencode only. Free models are included
and marked.

## Pipeline

1. **Catalog** - run the bundled script, it does the mechanical work:

   ```bash
   python3 <skill_dir>/scripts/catalog.py
   ```

   It parses `pi --list-models` and `opencode models`, unions the two lists
   (exact `provider + model id` pairs), tags each model's availability
   (`both` / `pi` / `opencode`), enriches with pricing,
   context, and capabilities from https://models.dev/api.json, and prints one
   JSON object to stdout. Never hand-run the intersection yourself.

   - `price_usd_per_m`: blended `usd/M` at a 3:1 input:output ratio.
     `pricing` is `free` (both directions 0), `paid`, or `unknown` (no cost
     in models.dev, e.g. plan-only access).
   - `usable`: reasoning or tool-call capable, text output, context >= 32k.
     The report's shortlist comes from `usable` models only.
   - For presentation, dedupe identical model ids across providers: one row
     per model id, cheapest price shown, availability = union of the tools
     that offer it.

2. **Intelligence scores** - web-research one score per shortlisted model
   (Artificial Analysis index, LMArena, or a named benchmark with a date).
   Record the score and its source URL. If no score is found, say so in the
   report rather than guessing. Coverage rule: score-verify every usable
   model with blended price ≤ $0.50/M (the cheap lane) plus all free
   models; models a benchmark source does not track are marked "not
   tracked", never guessed.

3. **Latency ping-pong (podium models)** - run the bundled benchmark:

   ```bash
   python3 <skill_dir>/scripts/ping_pong.py <winner> <runner1> <runner2>
   ```

   Same prompts through `pi -p`, wall-clock: 3 one-word runs (median) and 1
   long reasoning prompt per model. Report short median and long wall time
   per model; note that timing includes pi CLI startup equally and that
   long time mixes thinking and generation. The script retries with
   backoff on provider failures.

4. **Cutoff** - data-driven, stated in the report: keep the cheapest models
   whose verified score clears a usable-for-agentic-coding bar. Never fix
   the cutoff in this file; compute it from the data and say what you used.

5. **HTML report** - write `~/Downloads/cheap_models_YYYY-MM-DD.html`
   (local date). Self-contained means:

   - inline CSS, inline JS, inline SVG only; no CDN, no webfonts, no
     external images, no network requests of any kind;
   - a sortable/filterable table (plain inline JS, no libraries);
   - a price-vs-intelligence scatter as inline SVG, log-scale price axis;
   - a short write-up per shortlisted model: strengths, caveats, why it is
     on the list;
   - generated date, pi/opencode versions, the skill name
     (`cheap-model-research`), and time taken (catalog start → report
     write, wall clock), plus the method paragraph with the exact
     cutoff used;
   - the report calls out exactly 1 winner and 2 runner-up picks at the
     top, each justified from the verified data (price, score,
     availability);
   - citations section: every price and score claim links to
     its source.

6. **Verify** - before finishing, confirm the file has no `http` URL in a
   `src=`/`href=` attribute, then print the path.

## Report conventions

- Only models in the script's union. No additions, no exceptions.
- Free models are listed and marked "free". Plan-only/unknown-priced models
  go in a separate short section, not the main table.
- Report calls out exactly 1 winner and 2 runner-up picks at the top, each
  justified from the verified data (price, score, availability).
- Every number traces to models.dev, a provider page, or a benchmark page.
  Invented prices or scores are a bug.

## Hard rules

- Run `scripts/catalog.py` unchanged; do not replace it with ad-hoc curl
  and grep.
- Read-only: the script may only cache models.dev data under
  `~/.cache/cheap_model_research/`.
- If either CLI fails or the union is empty, stop and report the
  failure, do not fall back to a hand-written model list.
