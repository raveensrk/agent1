---
id: "zggd0xmbg9"
title: "Jev-score tool calls and their output"
state: "done"
due: ""
priority: "C"
tag: ["voice_score"]
repeat: ""
effort: ""
postpone: 0
created: "2026-10-04"
closed: "2026-10-04T19:07"
---

Score each tool call and its result, per turn, the way voice_score.ts scores thinking and the reply. Design settled in the 2026-10-03 session; do not re-litigate:
- Unit: the tool loop of one run - one score per call, plus its result size.
- Deterministic side first: session transcripts already record every call, its args and its result size, so repeated calls, subsumed retrieval and oversized outputs are computable with no model call.
- Jev then judges whether the call was necessary, as a typed score plus a gate, multiplied, the same shape as the token-efficiency score.
- Jev sees the request plus the call and a bounded slice of its result, never the whole result.
- Display only, no nudge, and its own switch, separate from /voice-score.
- Sources: https://arxiv.org/abs/2609.30725 (subsumed retrieval, similar script generation, test re-execution), https://arxiv.org/html/2607.12161v4 (token reduction is not cost reduction), https://arxiv.org/html/2509.23586 (AgentDiet trajectory reduction).
call_score.ts: necessity x gate per call, request + bounded 600/200 result slice to Jev, deterministic repeats/subsumed reads/oversize, own /call-score switch, ledger kind call; entry draws 'calls  2.6/3 0.1/3 0.2/3' (verified by rendering a live entry). Suites green (31 pytest + 6 ts), lint 0 on changed files. Calibration 2026-10-04: hand set 10 wasteful 0.02-0.87 vs necessary 0.01-1.22, population 230 calls median 1.06 smooth, Spearman -0.34 chars / -0.17 repeats: no gap, so CALL_PASS/CALL_GOOD stay 0 and the numbers draw dim until a later calibration finds one.
