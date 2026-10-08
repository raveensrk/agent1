---
id: "gtj5pxasx2"
title: "Add a completion-time estimate to a task's properties when creating it"
state: "done"
due: ""
priority: ""
tag: ["todo_skill"]
repeat: ""
effort: ""
postpone: 0
created: "2026-10-03"
closed: "2026-10-03T16:49"
---

On create, also record how long the task is expected to take, as a task property. Prefer the org built-in Effort property - a :PROPERTIES: drawer holding :Effort: 0:30 - because org-columns, org-agenda and org-clock already read it, so no new name needs inventing; fix the format at H:MM and reject anything else. Today the CLI writes no properties and no drawers at all (SKILL.md section 6), so create needs a new flag, for example --effort 30, and must leave a file that already has drawers intact. read --json should expose the value. Update SKILL.md sections 1 (properties) and 2 (CLI) and todo_tests.el. Verify: create with an estimate, then read --json shows it; a create without the flag writes no drawer; the suite passes.
Done 2026-10-03: create --effort H:MM writes the org built-in :Effort: property through org-set-property, before any note, so it lands in the drawer below the planning line; the format check is one shared helper with set-effort and anything else is refused ('effort takes H:MM, got 30', exit 1). read --json and doing --json expose effort, null when absent. No flag means no drawer: a created task is still just the heading line. Verified live through the wrapper on a probe board - create with --effort 0:45 produced ':Effort:   0:45', read --json showed "effort":"0:45", org itself read Effort 0:45 back, and a second create without the flag added no drawer and reported effort null. A create under a container left the existing sibling's :ID: and :Effort: 2:00 untouched. Suite 40/40 in 5s. Docs: SKILL.md sections 1 and 2.
