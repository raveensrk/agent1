---
id: "5s2dm9m0aq"
title: "Calibrate the efficiency bands before shipping them"
state: "done"
due: ""
priority: "C"
tag: ["voice_score"]
repeat: ""
effort: ""
postpone: 0
created: "2026-10-04"
closed: "2026-10-04T18:00"
---

Do this before freezing the PASS and GOOD constants for the tokens line. The voice bands came from 162 past samples and a measured gap; this number deserves the same, and it was never measured.
1) Hand-label first: pick 10 blocks by hand, 5 wasteful (pre-rule verbose thinking from early October sessions, or a deliberately long explanation) and 5 tight (telegraph replies from the 2026-10-03 session). Jev must separate them: wasteful below 1.5, tight above 2.0.
2) Population run: reuse /Users/raveen_kumar_personal/tmp/voice_probe/calibrate.py, adapted to the new questions. It posts to https://api.typesafe.ai/v1/systemone with TYPESAFE_API_KEY (the key is in the environment), batches 6 questions per call, and reads the 25 newest sessions under /Users/raveen_kumar_personal/.pi/agent/sessions/.
3) Sanity check: rank-correlate Jev's efficiency score against the deterministic evidence from task 1 (filler count, repeat count, deflate density). If the correlation is weak, report it and stop rather than shipping the number.
4) Set PASS and GOOD in the measured gap, and record both numbers in the extension header with the date and the sample size.
2026-10-04: hand set of 10 (5 pre-rule thinking, 5 telegraph replies) scored wasteful 0.17-0.52, tight 0.81-2.62 (only 1/5 above the plan's 2.0, stable to 0.07 across 3 runs); population 87 blocks from 25 newest sessions, median 0.66, max 2.41; Spearman -0.691 fillers, +0.525 deflate density, -0.232 repeats; EFF_PASS 0.75 in the one measured gap, EFF_GOOD 1.5 top quartile, both recorded in the header with date and sample sizes
