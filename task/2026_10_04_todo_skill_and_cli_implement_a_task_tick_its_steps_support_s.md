---
id: "qyjzxgw4p6"
title: "Todo skill and CLI: implement a task, tick its steps, support subtasks"
state: "todo"
due: ""
priority: "C"
tag: []
repeat: ""
effort: ""
postpone: 0
created: "2026-10-04"
closed: ""
---

Decided 2026-10-04, both halves. The CLI stays the only writer; the agent does the work.
A) Implement flow:
- A per-ref read returning the whole record: title, state, priority, tags, deadline, effort, path, note and steps. Today read --records returns every task and doing returns one, but a single ref cannot be fetched whole.
- A verb to tick one step by index, plus its counterpart: todo check <ref> N and todo uncheck <ref> N. Today an agent implementing a task cannot mark a - [ ] step done, and hand-editing a board is banned.
- SKILL.md documents the flow: set IN_PROGRESS, implement, check each step as it lands, append one result line, complete.
B) Structural subtasks:
- A task may contain child tasks with their own states. This replaces the rule that a task may never contain a task, so SKILL.md and the suite change together.
- Roll-up: a parent cannot become DONE while a child is open. Decide one behaviour and document it: refuse with a message naming the open child, or auto-complete. Refusing fits the rule that no refusal stays silent about its replacement.
- Keep the existing traps intact: a column-0 star inside a #+BEGIN_* block is still refused, refs stay title-based, and archive still only takes a completed task.
- capture --container is today's way to group tasks without states; SKILL.md should say when a container is still the right shape.
Tests: extend the skill's own suite (scripts/test, bounded, prints failures) with a check/uncheck round-trip, a single-ref record read, a parent refused while a child is open, and archiving a completed child.
Also update the skill's rule text in /Users/raveen_kumar_personal/repos/agent1/skills/todo/SKILL.md in the same change; the rules live there, not in the CLI.
