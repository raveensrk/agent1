---
id: "kd8k86bhvv"
title: "Append one voice_score ledger row per scored block"
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

File: /Users/raveen_kumar_personal/.local/share/voice_score/scores.jsonl. mkdir -p the directory; machine-local data, never committed, never inside a repo.
One JSON object per line, appended, one row per scored block:
{"at":"2026-10-04T04:40:00-07:00","session":"01a103cc","kind":"reply","voice":2.2,"efficiency":2.5,"gate":0.95,"chars":1840,"fillers":3,"repeats":1,"tokens":460}
- session comes from the PI_SESSION_ID environment variable when present, else an empty string.
- Append with one writeFileSync(path, line, {flag: "a"}); wrap it in try/catch and stay silent on failure, so a bad path never breaks a turn.
Why: re-calibration from real turns and trends over time, without re-parsing every transcript.
~/.local/share/voice_score/scores.jsonl gained 3 rows from two live pi -p runs, one per scored block, both scores and evidence
