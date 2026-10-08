---
id: "j93rmrdhey"
title: "Print one high-priority task alone from a single command"
state: "done"
due: ""
priority: ""
tag: ["todo_skill"]
repeat: ""
effort: ""
postpone: 0
created: "2026-10-03"
closed: "2026-10-03T16:43"
---

The CLI already has doing: one TODO or IN_PROGRESS that is due today or overdue, priority A before C. This asks for the priority-only pick instead - print one high-priority task, alone, with no list around it. Decide extend doing with a flag (for example --priority A) or add a new verb, and reuse the same pick order (priority, then title, then path) so emacs.el and agenda2 stay consistent. Verify: the command prints exactly one line for a board holding several priority A tasks, and prints nothing when none exists. Docs: SKILL.md section 2.
Done 2026-10-03: extended doing with --priority A|B|C instead of a new verb - any open TODO/IN_PROGRESS at that priority, due or not, title then path, one line, --json one object; no match prints none/null, a value outside A|B|C is refused, bare doing is unchanged. Verified through the wrapper on a probe board holding three A tasks (one line, Alpha by title order), a C task, and no B task (none/null). Also fixed the warm daemon's staleness check: it tested fboundp todo-doing-pick, true for every version, so a running daemon kept old code and ignored the new flag; it now reports its loaded file's mtime and the wrapper restarts it when todo.el changes (verified: pid changed after touch). Suite 39/39 in 5s. Docs: SKILL.md section 2.
