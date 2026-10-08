---
id: "mhjmw17sxr"
title: "Refuse to run while a board has duplicate task titles"
state: "todo"
due: ""
priority: "D"
tag: []
repeat: ""
effort: ""
postpone: 0
created: "2026-10-08"
closed: ""
---

Today a duplicate title is refused only when a verb names it as a ref (ambiguous ref). Instead, every verb should check first: if any board it reads or writes holds two tasks with the same title, exit non-zero and list each duplicate with its file and line. Nothing runs until the duplicates are fixed by hand (rename one, or delete/obsolete it).
- Decide the scope: duplicates within one board, or across every board a read scans.
- Archives (*.org_archive) are history and stay out of the check.
- Tests: a read, a write and doing all refuse while a duplicate exists, and run once it is renamed.
