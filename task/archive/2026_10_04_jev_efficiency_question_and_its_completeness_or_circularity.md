---
id: "cd9an27fyb"
title: "Jev efficiency question and its completeness or circularity gate"
state: "done"
due: ""
priority: "C"
tag: ["voice_score"]
repeat: ""
effort: ""
postpone: 0
created: "2026-10-04"
closed: "2026-10-04T17:53"
---

One Jev call per run stays the rule; the efficiency questions join the voice questions inside it at agent_before_settle. Two questions per block.
1) Efficiency score e, 0-3, HIGHER IS BETTER so the colours match the voice line. Instruction: How token-efficient is b0 for this task? Judge only the text, not whether the reasoning is correct.
   Criteria: 0: at least half the tokens are non-essential, restatement, filler or material the task did not ask for | 1: noticeable waste, repeated points, throat-clearing or detail beyond what the task needed | 2: mostly load-bearing, a few clauses or hedges could go | 3: every sentence carries information needed for this task, nothing could be cut without losing content.
2) Gate, a bool per block. Reply: Does the reply deliver everything this turn learned that the user needs, judged against the request and the trace? true: it covers what the task needed; false: something needed is missing. Thinking: Does the thinking avoid circularity? true: each step advances the reasoning, nothing re-derived; false: it repeats or re-derives a point it already settled.
Then efficiency = e x p(gate). The gate carries the omission penalty, because a bare conciseness score is weak on its own (ConCISE measured an LLM conciseness rating at r = -0.108 against human ratings, while compression-based measures reached 0.628: https://arxiv.org/html/2511.16846v2).
Do not add a second Jev call, and do not change the voice questions.
e/g questions in buildQuestions, efficiency = e x gate; one classify call; live pi -p session entry holds both score sets
