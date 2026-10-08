---
id: "38rqagn96e"
title: "Efficiency evidence: filler, duplicate spans, density helpers with tests"
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

The deterministic half of the token-efficiency score, in /Users/raveen_kumar_personal/repos/agent1/harness/extensions/voice_score.ts (same file; it stays node-loadable because it only type-imports pi). Pure functions, no model call, no I/O, no theme.
- fillers(text): case-insensitive word-boundary matches for: just, really, basically, simply, actually, essentially, quite, very, note that, it is worth noting, it is important to note, in order to, the fact that. Returns the words found with counts.
- repeats(text): split into sentence-ish spans (on blank lines and sentence ends), normalize (lowercase, strip punctuation), and treat two spans as duplicates when the Jaccard overlap of their word sets is >= 0.8. Returns the count of spans beyond the first in each duplicate group.
- density(text): chars, estimated tokens (chars / 4), and zlib deflate ratio (compressed length / raw length), where a high ratio means high information density.
Tests in /Users/raveen_kumar_personal/repos/agent1/harness/tests/test_voice_score.ts: one positive case, one negative case and the empty string for each helper.
Run: timeout 180 node --experimental-strip-types /Users/raveen_kumar_personal/repos/agent1/harness/tests/test_voice_score.ts
Why: measured facts beat a judge's opinion. This evidence goes in the expanded view next to Jev's number, and it is the sanity check on Jev during calibration (task 6).
Order: tasks 1-8 in board order; each is one session-sized unit that leaves the tree green.
fillers/repeats/density/evidence in harness/extensions/voice_score.ts; suite green: timeout 180 node --experimental-strip-types harness/tests/test_voice_score.ts
