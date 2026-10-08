---
id: "b2m1cktyq9"
title: "todo CLI: error on a column-0 * heading inside a #+BEGIN_* block instead of silently ignoring it - org-mode and the agenda treat it as a real task. Update SKILL.md traps and tests."
state: "done"
due: ""
priority: ""
tag: []
repeat: ""
effort: ""
postpone: 0
created: "2026-09-30"
closed: "2026-10-03T16:58"
---

Done 2026-10-03: todo-write scans the text it is about to replace and refuses a file that leaves a column-0 heading inside a #+BEGIN_* block, naming file:line and the one-space fix, before anything is written. read skips such a line while org and the agenda count it as a real task, so the board could hold a task no verb here could see. First run over every board in default_dirs (31 files): 0 offences. Verified through the wrapper: the broken probe board exits 1 with 'block_probe2/todo.org:5: a column-0 * heading sits inside #+SRC' and stays byte-identical, the same line indented passes, and a copy of the 24-routine board still takes writes. Suite 43/43 in 5s. Docs: SKILL.md Examples and traps.
