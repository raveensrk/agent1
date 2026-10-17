# Working style

------------------------------------------------------------------------------

When using lists always prefer numbered lists.

------------------------------------------------------------------------------

Nothing vague - precise goal / result.

------------------------------------------------------------------------------

Use a past example as the format to match.

------------------------------------------------------------------------------

Grill me and ask clarifying questions until you understand the task before starting a task.

------------------------------------------------------------------------------

Ask one question at a time. When a decision is needed, ask it as an MCQ and mark the option you recommend with "(recommended)".

------------------------------------------------------------------------------

Never put more than one question on a line. Split them into numbered lines, one question each.

Bad:

"Do you want me to record it as a win, or add a task to check the ledger?"

Good:

1. Do you want me to record it as a win?
2. Do you want me to add a task to check the ledger?

------------------------------------------------------------------------------

Verify a library call in a scratch buffer or a one-liner before using it in code.

------------------------------------------------------------------------------

A bulk or destructive change prints a per-file plan first, then applies, and a formatter or rewriter is proven on copies before it sweeps: run it on one or two representative files in `~/tmp`, diff the result, then apply it across the tree. The sweep that skipped that step rewrote 15 `SKILL.md` frontmatter blocks on 04 Oct 2026.

------------------------------------------------------------------------------

Minimal fix - the smallest change that solves the problem. Do not expand scope across layers unless each layer is load-bearing.

------------------------------------------------------------------------------

For operational tasks, prefer native CLI commands and short shell sequences over ad-hoc Python/JavaScript wrappers when existing tools can perform the task safely. Before writing a wrapper, explain the specific capability the native CLI lacks.

------------------------------------------------------------------------------


When a command fails because a dependency is missing, stop and ask: install it, or use an alternative. Never silently substitute a different tool or runner.

------------------------------------------------------------------------------

Read the exact region before an edit when this session has not shown that text - one guessed `oldText` aborts the whole batch and costs a retry.

------------------------------------------------------------------------------

A repeated question gets a fresh measurement, not the old answer. Re-scan, diff against the previous answer, and report what changed; another session or process may have altered the machine meanwhile.

------------------------------------------------------------------------------

End a bash call so it exits 0 when finding nothing is a valid answer: `grep -c ... || true`, `ls <glob> 2>/dev/null || true`. A clean scan that exits 1 is reported as an error and reads as a failure - 12 of those in one session.

------------------------------------------------------------------------------

Machine-wide: search with `rg`, never `grep -r` - recursive grep walks `.git` and `node_modules`. Measured on this machine, one `grep -rn` over `~/repos` (17 GB, 169,203 files) ran 111 s of a 137 s session and had to be aborted; `rg -l` answered the same question in 2.6 s. `harness/extensions/command_guard.ts` blocks the recursive form, and a `curl` or `wget` with no timeout, printing the replacement either way. Bound the path either way.

------------------------------------------------------------------------------

Machine-wide: a path a command already named needs no second scan to confirm it. When that path turns out missing, ask one question instead of searching for an alternative: the sweep cost 111 s on a task whose whole ambiguity was one question.

------------------------------------------------------------------------------

An ambiguous request that follows unrelated work and could target either the harness or the project in cwd: confirm scope with one question before editing anything outside cwd (`~/.pi`, dotfiles, `~/repos`); default to the project in cwd.

------------------------------------------------------------------------------

Symlinks: never create one, never commit one. Warn me first and name the alternative you chose instead - [no_symlinks.py](harness/checks/no_symlinks.py) decides it.

------------------------------------------------------------------------------

