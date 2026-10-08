---
id: "384qqkxx94"
title: "Fix the warm-daemon test hang in the todo skill suite"
state: "done"
due: ""
priority: ""
tag: ["todo_skill"]
repeat: ""
effort: ""
postpone: 0
created: "2026-10-02"
closed: "2026-10-03T16:50"
---

  Found 2026-10-02 in a session review.
  - Hang: emacs -Q --batch -l tests/todo_tests.el -f ert-run-tests-batch-and-exit exits 124. The two tests todo-warm-wrapper-reuses-the-daemon and todo-warm-write-does-not-kill-emacs never finish.
  - Not caused by commit b906475, the todo-main change that clears command-line-args-left: the suite hangs the same way with the committed test file and the committed scripts/todo.el.
  - A standalone ./scripts/todo --warm create --file ~/tmp/probe/todo.org finishes in 1.7 s, so the daemon start is fine. The hang is inside the test call to todo-warm-write.
  - Each failing run leaves a live hung emacsclient ... (todo-warm-write ...) and leaked sockets at ${TMPDIR}/emacs<uid>/todo-skill-test-*.
  - Done when the full suite exits 0 with 36 of 36 passed twice in a row and leaves no extra daemon, socket or emacsclient process.
Done 2026-10-03. Cause: the daemon (not batch Emacs) pops select-safe-coding-system-interactively when the text to write has a character its inferred coding system cannot hold - here 'create Apr–Jun' under LANG=en_IN.UTF-8, which Emacs maps to a non-UTF-8 coding system - and waits forever for a keypress that no daemon user can give. Batch mode never prompts, which is why only the warm tests hung, and emacsclient then waited on the socket with no timeout. Fix: coding-system-for-write is utf-8-unix in scripts/todo.el; a sample of the hung daemon's stack showed server--process-filter -> select-safe-coding-system-interactively -> completing-read -> command_loop waiting on pselect. Also found while verifying: the wrapper proved daemon freshness with fboundp todo-doing-pick, true for every version, so an edited file never reached a running daemon; the daemon now reports its loaded file's mtime and the wrapper restarts on any change. Verified: full suite exits 0 twice in a row (40/40 now, was 36 tests when written; 5.0s and 4.9s), then 0 leftover bg-daemon / emacsclient / todo-skill-test processes and 0 sockets in ${TMPDIR}/emacs<uid>/.
