---
id: "mhjmw17sxr"
title: "Refuse to run while a board has duplicate task titles"
state: "obsolete"
due: ""
priority: "D"
tag: ["waypoint"]
repeat: ""
effort: ""
postpone: 0
created: "2026-10-08"
closed: "2026-10-11T19:26"
---

Rewritten 2026-10-10 for Waypoint (the org boards are gone).

Today Waypoint refuses a title only when a command names it and it matches more than one task. Instead, every command checks first: if two open tasks in the same repo's task/ folder share a title, it exits non-zero and lists each duplicate with its file path. Nothing runs until one is renamed, finished or dropped by hand.

- Scope: open tasks within one task/ folder. task/archive/ (done and dropped) is history and stays out of the check.
- Tests: a read (list), a write (edit) and done all refuse while a duplicate exists, and run once it is renamed.

## Log

- obsolete 2026-10-11 19:26: moved into the task-router plan: ~/repos/waypoint/plan.md, Invalid task handling item 5 (reads warn, writes refuse)
