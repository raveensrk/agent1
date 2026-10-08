---
id: "bg499w9491"
title: "Capture the user request and a compact tool-call trace per run"
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

In /Users/raveen_kumar_personal/repos/agent1/harness/extensions/voice_score.ts, next to the existing think/reply collection.
- message_end with role user: keep the last request text, truncated to 2000 chars.
- message_end with an assistant toolCall block (check the transcript shape first; blocks are type toolCall): record name plus a 120-char args summary.
- message_end with role toolResult: attach the result size in chars to the call.
- Cap the trace at 12 entries, oldest dropped, one line each: read voice_score.ts (1,840 chars result).
- Reset at agent_start, exactly like think and reply today.
Write this caveat into the code: a thinking block is judged against calls made after it, because that is the only way to know whether the thinking was needed at all.
Jev state layout, backticked paths, per task 3: request, trace, then one field per block.
Verify before moving on: a pi -p run with PI_VOICE_TRACE=1 logs the trace once, so the capture can be seen without the ledger (task 5).
request+toolCall/toolResult capture, 12-entry cap; PI_VOICE_TRACE=1 pi -p logged request and one call with its result size
