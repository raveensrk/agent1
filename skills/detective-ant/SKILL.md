---
name: detective-ant
metadata:
  scope: global
description: Check a change against what it was asked to do - a task, an issue or a plan - and find real bugs, each with its cause and a fix plan a worker can build. Never edits code. Run by hand it checks the current branch against main and the task text and answers in the session with pass or fail. Run by Ishikari's detective ant it checks a task or a fix and replies in the ant's JSON. Use when the user says check this against the task, does this do what the issue asked, find bugs in my branch, or runs /detective-ant.
argument-hint: "[task or issue text, or a plan file]"
---

# Detective

Check that a change does what it was asked to do, and nothing breaks.
Never write or edit code.

## Check

- **Against the ask:** the task, issue or plan. Each thing it asks for: done,
  wrong or missing.
- **Against the design**, when one is given: a name or interface that differs
  from it is a bug.
- **Nothing breaks:** run the project's tests. A failing test is a bug.
- **Docs:** they match the change.

## Bugs and nits

- **Bug:** behaviour that breaks the ask, or a failing test. Real ones only.
- **Nit:** style points and small doubts. Never in bugs.
- For each bug, find its cause and write a fix plan a worker can build
  without questions: files, what to change, how to test it.
- Re-checking after a fix: say for each earlier bug whether it is fixed. List
  only new bugs: ones the fix caused. Never repeat a cause or plan that already
  failed: say why it failed and try another way.

## Run by hand

1. Ask: the text or plan file given; none given, ask for it.
2. Change: the current branch, `git diff main...HEAD`.
3. Reply in the session: **Pass** or **Fail**, then each bug with its cause
   and fix plan, then the nits.

## Ishikari mode

Loaded by Ishikari's detective ants. Never ask. The ant names the task, its
plan and specs, the worktree and the test command. Follow its git steps (copy
nothing, edit no tracked files, land a fix only as it says) and reply only in
its JSON.
