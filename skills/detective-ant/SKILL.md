---
name: detective-ant
metadata:
  scope: global
description: Check a change against what it was asked to do - a task, an issue or a plan - and find real bugs, each with its cause and a fix plan a worker can build. Never edits code. In normal use it checks the current branch against main and the task text and answers in the session with pass or fail. Run by Ishikari's detective ant it checks a task or a fix and replies in the ant's JSON. Use when the user says check this against the task, does this do what the issue asked, find bugs in my branch, or runs /detective-ant.
argument-hint: "[task or issue text, or a plan file]"
---

# Detective

Check that a change does what it was asked to do, and nothing breaks. Never
write or edit code.

## Which mode

- **Ishikari mode** only when your prompt says you are an ant of the Ishikari
  workflow and tells you to follow this skill's Ishikari mode. Then follow
  [Ishikari mode](#ishikari-mode) and the ant's prompt, and nothing else.
- **Normal mode** every other time: the user runs the skill, it triggers in a
  normal session, or another skill or agent calls it. Then follow
  [Normal mode](#normal-mode) and ignore everything Ishikari-only: no Ishikari
  spec or plan files, no JSON reply, no Ishikari paths, never wait for an ant's
  inputs.
- **No user to ask** in normal mode (another agent called it): never wait. Take
  the recommended answer, go on, and list each question with the answer taken at
  the end.

## Tools

Fixed steps are done by `python3 <this skill's folder>/../ishikari/scripts/ant.py`, never by hand. It calls no model and prints
JSON. Run it from the repo.

- `ant.py scope [--base B]`: the base and every changed file with its line
  ranges.
- `ant.py tests [--base B] -- <test command>`: runs the tests on the base and
  on HEAD; `verdict` is `pass`, `new-failure`, `already-failing` or `fixed`.

## Check

- **Against the ask:** the task, issue or plan. Each thing it asks for: done,
  wrong or missing.
- **Against the design**, when one is given: a name or interface that differs
  from it is a bug.
- **Nothing breaks:** run `ant.py tests`. `new-failure` is a bug.
  `already-failing`: compare the two tails; only a test that fails after and
  not before is a bug, the rest is a nit.
- **Docs:** they match the change.

## Bugs and nits

- **Bug:** behaviour that breaks the ask, or a failing test. Real ones only.
- **Nit:** style points and small doubts. Never in bugs.
- For each bug, find its cause and write a fix plan a worker can build without
  questions: files, what to change, how to test it.
- Re-checking after a fix: say for each earlier bug whether it is fixed. List
  only new bugs: ones the fix caused. Never repeat a cause or plan that already
  failed: say why it failed and try another way.

## Normal mode

1. Ask: the text or plan file given; none given, ask for it.
2. Change: run `ant.py scope` (a branch the user names wins), then
   `ant.py tests`.
3. Reply in the session: **Pass** or **Fail**, then each bug with its cause and
   fix plan, then the nits. Fail when bugs is not empty, Pass otherwise; nits
   never make it fail.

## Ishikari mode

Loaded by Ishikari's detective ants. Never ask. The ant names the task, its plan
and specs, the worktree and the test command. Follow its git steps (copy
nothing, edit no tracked files, land a fix only as it says) and reply only in
its JSON.
