---
id: "5tgpwfh31n"
title: "Validate the deadline forms in the CLI"
state: "obsolete"
due: ""
priority: ""
tag: ["todo_skill"]
repeat: ""
effort: ""
postpone: 0
created: "2026-10-03"
closed: "2026-10-06T23:13"
---

  Found 2026-10-02 in a session review.
  - scripts/todo create "Bad" --deadline "2026-10-02 10:00" exits 0 and writes DEADLINE: <2026-10-02 Fri 10:00>.
  - SKILL.md says the CLI rejects a time, angle brackets and a hand-written day name.
  - Cause: the check around line 272 of scripts/todo.el is (and deadline (ignore-errors (org-time-string-to-absolute deadline))), which accepts far more than a bare YYYY-MM-DD.
  - Done when a time, angle brackets and a day name each exit non-zero with a clear message, a bare 2026-11-05 still works, and a test covers each rejection.
Reshaped 2026-10-03 with Raveen: the original ask (reject a deadline time) died when 24 routines got a time of day in DEADLINE the same day; what stayed real is that org absorbed garbage silently. Measured before the fix, all exit 0: --deadline garbage wrote today's date, 2026-13-45 wrote 2027-02-14, 'next friday' wrote 2026-10-09, 2026-11-05 +1w wrote a deadline with the repeater dropped. Now todo--checked-deadline accepts exactly the three documented forms - 2026-11-05, 2026-11-05 20:30, <2026-11-19 Thu 20:30 +1w> - and refuses anything else on create --deadline and set-deadline with a message naming them, plus '2026-13-45 is not a real date' when the shape is right but the date is not (an encoded round-trip check, so month roll-over cannot pass). Verified through the wrapper: 5 bad forms exit 1 and write nothing, 3 good forms write the exact stamp, set-deadline garbage leaves the old DEADLINE untouched, and all 24 routines still read with their time. Suite 41/41 in 5s. Docs: SKILL.md Dates.
Closed 2026-10-06. The 2026-10-03 fix validated the date only, so the time field still took any two digits and org rolled it over in silence: create and set-deadline accepted '2026-11-05 25:00' (wrote <2026-11-06 Fri 01:00>) and '2026-11-05 20:99', in the bare and the stamped form. Measured before the fix: 5 bad forms - garbage, 2026-13-45, next friday, 2026-11-05 +1w, 2026-11-05 25:00 - of which the last exited 0. Org's own parser does not catch it either: org-parse-time-string returns hour 25 rather than nil, and org-duration-to-minutes reads 25:00 as 1500 minutes. Fix: todo--checked-deadline now encodes the HH:MM pair and reads it back (decode-time/encode-time round trip, the same test calendar-date-is-valid-p does for the date) and refuses any pair that moves. Verified through the wrapper on scratch boards: 4 bad times exit 1 with '25:00 is not a real time', 5 good forms still write the exact stamp (2026-11-05, 2026-11-05 20:30, <... 20:30 +1w> written as ++1w, 00:00, 23:59), and a refused set-deadline leaves the old DEADLINE untouched. Tests: 3 time cases added to todo-deadline-takes-three-forms-and-refuses-the-rest plus a set-deadline time case; suite 86/86 in 6.96s. Whole population: all 48 deadlines across every board pass todo--checked-deadline, 0 refused. Docs: SKILL.md Dates. harness/lint.py --changed: 12 checks, 5 files, 0 findings.

## Log

- obsolete 2026-10-06 23:13: archived while still open
