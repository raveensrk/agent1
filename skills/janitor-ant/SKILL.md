---
name: janitor-ant
metadata:
  scope: global
description: Clean up only the code a change added or touched - dead code, bloat, duplication and mess - with no change in behaviour, tests run after. In normal use it cleans the current branch's changes against main, shows the cleanup and applies it after a yes. Run by Ishikari's janitor ant it never asks and follows the ant's git steps. Use when the user says clean up this change, tidy my diff, janitor, or runs /janitor-ant. For a whole-project sweep use /maintain instead.
argument-hint: "[base ref, default main]"
---

# Janitor

Clean the mess a change left. Only that change, nothing else.

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

## Scope

- The changed lines: the ranges `ant.py scope` gives. Base: its choice
  (origin's default, then `main`, then `master`), or the one the user names.
- Ishikari: the range its ant names.
- Code outside the changed lines stays as it is, even if it is messy. Exception:
  a helper the change made dead or duplicate may go.

## What to clean

- Dead code: unused functions, variables, imports, branches, commented-out code.
- Duplication: the same logic written twice in the change, or next to an
  existing helper it could call.
- Bloat: needless wrappers, layers, options or checks nothing needs.
- Mess: debug prints, stray TODOs the change left, leftover files.

## Rules

- Change no behaviour. Public interfaces, output and data stay the same.
- Small and careful: no rewrites, no renames across files, no new features.
- After the cleanup, run `ant.py tests`. `new-failure`: undo the cleanup.
  `already-failing`: compare the two tails; undo only if a new test fails.
- Nothing worth cleaning: change nothing and say so.

## Normal mode

1. Run `ant.py scope`. Read those ranges and the code around them.
2. Show the cleanup: each item with its file, line and why. Wait for a yes. No
   user to ask: apply it without a yes.
3. Apply, run the tests, commit as `refactor: clean up <what>`.

## Ishikari mode

Loaded by Ishikari's janitor ant. Never ask. Follow the ant's own git steps
(worktree, commit, landing) and its reply format. Write what you changed and
why, in a few lines, to the note file it names.
