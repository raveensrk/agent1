---
id: "n5h1hr6cgr"
title: "read and doing must honor --file"
state: "done"
due: ""
priority: ""
tag: ["todo_skill"]
repeat: ""
effort: ""
postpone: 0
created: "2026-10-03"
closed: "2026-10-03T17:21"
---

Done 2026-10-03. read and doing ignored --file and read --dir plus the config default_dirs instead, so read --file ~/repos/agent1/todo.org silently answered for 12 boards - it misled two verifications in this session (a capture I thought was on agent1's board lives on agent2's). Fix: todo-read takes an optional file and reads exactly that board when given; read and doing pass it, --file wins over --dir, and a missing file fails with the path. Verified live: read --file agent1/todo.org returns 9 tasks from 1 path, read --file Main_Quest/todo.org returns 47 from that file only (recurring.org excluded), doing --file recurring.org picks from it, read with no --file still scans the config dirs (181 tasks, 12 boards), and a missing file exits 1 with 'Opening input file: No such file or directory'. Suite 44/44 in 5s. Docs: SKILL.md section 2.
