---
id: "anzzf3b5tw"
title: "Second display line for tokens, evidence in the expanded view"
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

The entry gains one line under the existing one:
  voice  think 2.8  reply 2.2
  tokens think 1.4  reply 2.6
- Same band colours and thresholds as the voice line, one decimal per number, worst not separated out.
- Blocks under FLOOR (200 chars) stay unscored, same as voice. When a run has a voice score but no efficiency score, print the empty tokens line and say nothing else.
- Expanded view, per block: filler words found, duplicate span count, chars, estimated tokens, Jev score, gate probability, confidence. Example: reply load-bearing 2.6 gate 0.95 conf 0.60 fillers 3 repeats 1 1840 chars.
- Display only, as before: no nudge, no continue, the entry is a custom entry and never reaches the model's context.
Render it through a pure renderLines-style helper so the text can be unit-tested without a terminal.
renderLines draws voice + tokens lines, expiry and evidence detail; suite asserts both, expanded evidence line
