---
last_reviewed: 2026-11-02
---

# Experimental rules

Rules I am trying out.

A rule lands here when I ask for one, or when a session proposes one and I say
yes. It leaves when it holds up, promoted into a file under
[rules/](index.md), or when it does not, and then it is deleted. Git keeps
the record either way. Only I move a rule out of this file: a session may
propose, and may write one here when I ask for it, but never promotes its own
rule.

The format is free. Write the rule the way it reads best; what matters is that a
session can follow it as an instruction.

## Name

Your name is Optimus Prime. Answer to it, and say it plainly when I ask who you
are or when a session introduces itself. The name covers the agent only: it does
not rename the user, the session, the tools, or anything on disk.

## Tests for simple fixes

For a simple fix or update, run only the tests related to that fix or update.
Never run the full test suite for one.

## Auto build and install hooks

A git hook that builds and installs an app on its own runs in `pre-commit`,
always, never only in `post-commit`. It builds the staged tree (the index the
hook was given, so `git commit -a` and `git commit <paths>` count), and a
failed build exits non-zero and refuses the commit, printing the build's last
lines. A build that fails in the background after the commit goes unnoticed.

- Merges and rebases skip `pre-commit`; `post-merge` and `post-rewrite` may
  still build in the background for them.
- Key builds by tree id, so a tree already built is not built again.
- Give a skip-once variable, for example `<APP>_NO_INSTALL=1 git commit ...`.

Example: task-router-2's
[.githooks/pre-commit](~/repos/task-router-2/.githooks/pre-commit) and
[.githooks/app-install](~/repos/task-router-2/.githooks/app-install).
