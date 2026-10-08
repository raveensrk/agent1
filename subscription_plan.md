# Subscription Plan

Model recommendations and reviews: [Models](model.org). Recorded model use: [Model usage history](model_usage_history.org). Harness reviews: [Harness](harness.org).

What to buy, what it covers, and what it costs. Prices are dated and sourced; measured spend comes from this machine's own logs. Review date 2026-10-07.

Currency: India INR as charged, converted at 1 USD = 96.42 INR (frankfurter.dev, rate date 2026-10-06).

## Current state

- Metered: OpenRouter (pi and opencode), billed from credits.
- Subscription: OpenCode Go, key held by opencode; lifetime Zen/Go console spend 40.02 USD.
- pi credentials: `xai` and `openrouter` OAuth, a `vercel-ai-gateway` API key, `OPENCODE_API_KEY` env for opencode. The xAI entry is OAuth, not an API key, so Grok turns run through the xAI account path, not the metered API.
- Local: Ollama, three models, 26 GB on disk, no marginal cost.
- Absent: no Claude Code and no Codex CLI state on this machine.

<!-- publish_hide -->

## Measured spend, 30 days

Window 2026-09-07 to 2026-10-07. Cost is the value recorded in the log, not list-price arithmetic. For subscription-backed OAuth routes it is imputed, not necessarily billed.

| Model | Channel | Turns | Recorded USD |
|------------------------|------------|------:|-------------:|
| Grok 4.7 | xai | 1027 | 244.15 |
| DeepSeek V4.1 Flash | openrouter | 4680 | 20.35 |
| GLM 5.3 Flash | opencode | 1022 | 6.96 |
| Claude Opus 5.5 | openrouter | 40 | 4.61 |
| DeepSeek V4.1 Flash | opencode | 505 | 4.47 |
| GLM 5.3 Flash | openrouter | 306 | 2.59 |
| GPT 6 Luna | opencode | 23 | 0.03 |
| OpenRouter auto routes | openrouter | 411 | 0.00 |
| **Total** | | 8046 | 283.17 |

- 283.17 USD = 27,300 INR for the month, against a target budget of 40 USD = 3,857 INR.
- Grok 4.7 is 86 percent of the recorded bill on 13 percent of the turns.
- Tokens: 42.6M uncached input, 920.8M cached input, 5.9M output. A 96 percent cache hit rate is what keeps the flash lines cheap.

## Channel finding: DeepSeek off-peak

- OpenRouter bills DeepSeek at the peak rate around the clock: 0.30 in, 0.006 cached, 1.20 out per 1M.
- DeepSeek's own off-peak rate is half: 0.15, 0.003, 0.60. Peak hours are 01:00 to 04:00 and 06:00 to 10:00 UTC, Monday to Friday.
- Measured on log timestamps: 99.3 percent of DeepSeek turns fall off-peak (5,147 of 5,182). Only 35 are peak.
- Same tokens direct: 7.48 USD per month, against 14.82 USD at OpenRouter list and 20.35 USD recorded. The channel costs 7 to 13 USD a month.
- Caveat: pi's usage record has no `reasoning` field, so reasoning tokens are likely absent from the output count while still being billed. Recorded cost is the truth; computed cost is a floor.

## Value per unit of capability

Artificial Analysis Intelligence Index v4.3.2, first-party pages and the 2026-10-03 report.

| Model | Index | USD per Index task |
|--------------------------------|------:|-------------------:|
| Claude Opus 5.5 (max) | 58.0 | 5.98 |
| Grok 4.7 (xhigh) | 46.4 | 3.74 |
| GLM 5.3 (max) | 45.0 | - |
| Kimi K3 (max) | 44.0 | 2.00 |
| Grok 4.7 (low) | 42.2 | 1.25 |
| GLM 5.3 Flash | 41.8 | 0.25 |
| DeepSeek V4.1 Flash (max) | 39.5 | 0.27 |
| DeepSeek V4.1 Flash (no think) | 24.7 | 0.15 |

Flash tier is 10 to 17 times better value per index point. Opus 5.5 is the capability ceiling and the worst value per point of the paid routes.

## Prices verified 2026-10-07

| Plan | Price as charged | USD | Notable |
|----|----|---:|----|
| ChatGPT Go | 399 INR | 4.14 | limited Codex |
| ChatGPT Plus | 1,999 INR | 20.73 | expanded Codex usage |
| ChatGPT Pro | 10,699 INR | 110.96 | over budget |
| Claude Pro | 20 USD monthly | 20.00 | Opus included, quota unpublished |
| Claude Pro annual | 200 USD upfront | 16.67 | equals 17 USD per month |
| Claude Pro India | 2,399 INR (press) | 24.88 | not fetched on a vendor page |
| Claude Max 5x | from 100 USD | 100.00 | over budget |
| Google AI Plus | 399 INR | 4.14 | no pi-usable quota |
| Google AI Pro | 1,950 INR | 20.22 | no pi-usable quota |
| Google AI Ultra 5x | 6,500 INR | 67.41 | over budget |
| SuperGrok | 30 USD | 30.00 | India 2,900 INR unverified |
| GLM Coding Lite | 12.60 promo, 18 list | 12.60 | 2,000 credits per 5 h |
| GLM Coding Pro | 56 promo, 80 list | 56.00 | over budget |
| Kimi Plus | 19 monthly, 180 yearly | 19.00 | Kimi Code from Plus up |
| Kimi Pro | 39 monthly | 39.00 | 2x agent credits |
| MiniMax Plus | 22 USD | 22.00 | 5 h and weekly windows |
| OpenCode Go | 10 USD | 10.00 | 30 models in the pi catalog |
| OpenCode Go Plus | 40 USD | 40.00 | higher limits |
| GitHub Copilot Pro | 10 USD | 10.00 | excludes Opus 5.5 |
| GitHub Copilot Pro+ | 39 USD | 39.00 | 70 USD of AI credits |
| GitHub Copilot Max | 100 USD | 100.00 | over budget |
| Cursor Individual | 20 USD | 20.00 | editor-bound |
| Windsurf Pro | 20 USD | 20.00 | editor-bound |

## pi fit, plan by plan

Verified 2026-10-08 against the local pi 1.0.4 install: bundled provider list, `docs/providers.md`, and `pi --list-models` (catalogs refreshed 06:35 IST). Status: ✅ pi consumes the plan; ⚠️ pi consumes with a caveat; ❌ pi cannot consume the plan. No plan was removed from the price table above; unsuitable plans stay listed here with their reason.

| Plan | pi | Reason |
|---|---|---|
| ChatGPT Go | ⚠️ | Codex login works in pi; Go's limited Codex quota suits light agent use only. |
| ChatGPT Plus | ✅ | Codex login works in pi; expanded Codex usage. |
| ChatGPT Pro | ✅ | Codex login works in pi; over budget. |
| Claude Pro | ⚠️ | Runs on `ANTHROPIC_OAUTH_TOKEN`; Anthropic's position on third-party harnesses is unsettled. |
| Claude Pro annual | ⚠️ | Same route and same risk; cheapest per-month Claude price. |
| Claude Pro India | ⚠️ | Same route and risk; price is press-reported, not on a vendor page. |
| Claude Max 5x | ⚠️ | Same route and risk; over budget. |
| Google AI Plus | ❌ | pi has no Google-AI-subscription login; only metered `GEMINI_API_KEY` and Vertex routes, which the plan quota does not cover. |
| Google AI Pro | ❌ | Same; plan quota not reachable from pi. |
| Google AI Ultra 5x | ❌ | Same; also over budget. |
| SuperGrok | ✅ | `xaiOAuth` verified in pi; covers the measured Grok 4.7 turns. |
| GLM Coding Lite | ⚠️ | `zai` route exists in pi, but Z.ai's published tool list excludes pi - terms risk. |
| GLM Coding Pro | ⚠️ | Same as Lite; over budget. |
| Kimi Plus | ⚠️ | `kimi-coding` route exists in pi; whether Plus exposes it, and the credit window, need console confirmation. |
| Kimi Pro | ⚠️ | Same as Plus; 2x agent credits. |
| MiniMax Plus | ✅ | `minimax` and `minimax-cn` routes in the pi build; 5 h and weekly windows apply. |
| OpenCode Go | ✅ | Verified: 30 models in the local pi catalog via `opencode-go`; current subscription. |
| OpenCode Go Plus | ✅ | Same route, higher limits. |
| GitHub Copilot Pro | ✅ | `github-copilot` login works in pi; excludes Opus 5.5. |
| GitHub Copilot Pro+ | ✅ | `github-copilot` login works in pi; only pi-reachable Opus 5.5 subscription route. |
| GitHub Copilot Max | ✅ | Same route; over budget. |
| Cursor Individual | ❌ | Editor-bound auth; no login a harness can use. |
| Windsurf Pro | ❌ | Editor-bound auth; no login a harness can use. |

💡 pi also supports subscriptions absent from the price survey: Qwen Token Plan (`qwen-token-plan`), Xiaomi MiMo Token Plan (`xiaomi-token-plan-cn`, `-sgp`), Moonshot CN (`moonshotai-cn`), Vercel AI Gateway (metered; a key already sits in auth on this machine). Add them at the next price sweep.

## Recommendation

At a 40 USD budget, in order of return. Every option runs in pi; the pi-fit table above holds the per-plan caveats.

1. OpenCode Go 10 USD plus SuperGrok 30 USD. Exactly 40 USD. Go's catalog already covers every model metered today - DeepSeek V4.1 Flash, GLM 5.3 Flash, Kimi K3, Grok 4.7, GPT 6 Luna - and SuperGrok covers the Grok turns already served through xAI OAuth. This removes roughly 28 USD a month of metered spend. Keep 5 to 10 USD of OpenRouter funded as overflow, because Go's limits are unpublished.
2. Copilot Pro+ 39 USD plus OpenCode Go 10 USD, 49 USD. Puts Opus 5.5 in pi with 7,000 credits, about 70 USD of Opus usage, roughly 1,215 turns at the measured 0.0575 USD per turn.
3. Kimi Plus 19 USD plus OpenCode Go 10 USD, 29 USD. Cheapest route to a frontier quota; K3 costs 2.00 USD per index task.
4. Pure OpenRouter at 40 USD buys the measured flash mix (19.60 USD) plus about 350 Opus turns or about 220 Grok turns. Weaker than option 1.

Break-even rules measured this session.

- Copilot Pro+ pays for itself above about 678 Opus 5.5 turns a month; below that, pay per token.
- A Grok subscription beats metered Grok above 126 turns a month at 0.2377 USD per turn.
- Subscription beats the flash lines only if its limits exceed 4,680 DeepSeek turns and 1,328 GLM Flash turns a month.

## Open questions

- xAI OAuth: subscription quota or metered console billing. This decides whether the 244.15 USD Grok line is a bill or an imputed figure, and therefore whether the 40 USD plan works. Unresolved.
- GLM Coding Plan terms restrict use to a published tool list - Claude Code, Codex, ZCode, Kilo Code, Cline, OpenCode, OpenClaw. pi is not on it.
- Anthropic's position on a Claude subscription through a third-party harness is unsettled; pi ships `ANTHROPIC_OAUTH_TOKEN` support and that is all that is claimed here.
- GitHub does not publish a 5-hour or daily limit for Copilot Pro+. Session and weekly token limits existed in the request-based era and were never given window lengths. Monthly credits, forfeited at 00:00 UTC on the first, are the documented cap.
- OpenCode Go publishes no numeric limits.
- Kimi's help centre says credits refresh every 7 days and unused credits are lost; the membership page says new plans dropped the weekly window. Confirm in the console after subscribing.
- Gemini 4 Argon, announced 2026-09-30, goes to paid API customers and Google AI Ultra subscribers next, undated. It has no public model ID, and the Gemini API model list still tops out at `gemini-3.1-pro-preview`.

## Method

- Local scan: `~/.pi/agent/sessions/**/*.jsonl` read with the agent-usage-report readers; 9,040 usage records in window. Provider and model taken from each record, not from a catalog.
- Off-peak classification: a Lua scan of the same logs, UTC weekday and hour computed from the ISO timestamp, against DeepSeek's published peak windows.
- opencode: `~/.local/share/opencode/` SQLite and the OpenCode Zen/Go console adapter. Console totals are lifetime aggregates, not windowed.
- Harness survey: pi, opencode, Ollama present; Claude Code and Codex absent.
- pi fit: pi 1.0.4 bundled provider transports (`openai-codex`, `github-copilot`, `kimi-coding`, `zai`, `minimax`, `qwen-token-plan`, `xiaomi-token-plan-*`, `moonshotai-cn`, `anthropic`), `docs/providers.md`, and `pi --list-models` with catalogs refreshed 2026-10-08 06:35 IST. Credential inventory from `auth.json` keys and the environment, values not read.
- Web: first-party pages only, fetched 2026-10-07, except where a row is marked press or tracker.
