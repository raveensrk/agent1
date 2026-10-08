---
id: "v3a7zq35dt"
title: "Verify the efficiency score: suites, lint, live probe, one TUI turn"
state: "done"
due: ""
priority: "C"
tag: ["voice_score"]
repeat: ""
effort: ""
postpone: 0
created: "2026-10-04"
closed: "2026-10-04T18:17"
---

1) timeout 900 bash /Users/raveen_kumar_personal/repos/agent1/harness/self_check   # every suite, then the full-population lint
2) timeout 300 python3 /Users/raveen_kumar_personal/repos/agent1/harness/lint.py /Users/raveen_kumar_personal/repos/agent1/harness/extensions/voice_score.ts /Users/raveen_kumar_personal/repos/agent1/harness/tests/test_voice_score.ts /Users/raveen_kumar_personal/repos/agent1/harness/README.md   # 0 findings expected
3) Live probe: timeout 120 pi -p "List six facts about lighthouses, one per line, no preamble, no closing line." - then confirm the newest file under /Users/raveen_kumar_personal/.pi/agent/sessions/ holds a voice-score entry with both score sets, and that /Users/raveen_kumar_personal/.local/share/voice_score/scores.jsonl gained rows.
4) The user's probe: one turn in a fresh pi session, both lines visible, and the pasted result.
5) Expected magnitudes: still one Jev call per run, two more questions per scored block, under 1 s and well under $0.001 per turn. Numbers must be real, not estimated.
harness/self_check: 27 pytest passed, all 5 ts suites ok, lint --repos 12532 files 63 findings (machine-wide, pre-existing; the 3 changed files lint 0); live pi -p run wrote an entry with both score sets + evidence and the ledger 3 -> 5 rows; user TUI turn drew 'voice  think 1.7/3  reply 1.9/3' and 'tokens think 0.2/3  reply 2.5/3'; magnitudes: one Jev call per run, 3 questions per block (was 1), 424 ms measured for 2 blocks and 6 questions, 1385 tokens, /bin/bash catalog cost on the typesafe route, /bin/bash.000058 at the OpenRouter 0.042/M rate
