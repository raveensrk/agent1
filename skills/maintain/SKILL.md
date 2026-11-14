---
name: maintain
metadata:
  scope: global
description: Maintain a project - find dead code, bloat and redundancy, split large code blocks into small focused units, add helper scripts that save tokens or raise quality, and suggest one improvement. Use when the user says perform maintenance, clean up this project, remove dead code, reduce bloat, or runs /maintain. Prints the plan and waits for a yes before changing anything; behavior stays the same.
argument-hint: "[path or area, e.g. src/ui]"
---

# Maintain a project

Clean the project without changing what it does. Plan first, change after a
yes, verify each step.

## 1. Look first

- Read the repo's `AGENTS.md` or `CLAUDE.md`, its requirements and its docs.
- Learn how it builds and tests. Run both once, before any change, and note
  what already fails.
- Limit the scan to the path or area given as an argument, if any.

## 2. Find

Collect findings in these groups. Each finding names the path, the line and
the evidence.

1. Dead code: unused files, functions, exports, dependencies, config keys and
   commented-out blocks. Evidence is a search showing no caller, not a guess.
   Mind dynamic use: reflection, string lookups, entry points, public API.
2. Bloat: vendored or generated files under version control, oversized
   assets, dependencies that one small function could replace.
3. Redundancy: duplicated code, docs saying the same thing twice, two scripts
   doing one job.
4. Large blocks: functions, files or components too long to read at once.
   Propose the split: the new units, their names, what each owns.
5. Helper scripts: repeated multi-step commands, or lookups an agent redoes
   each session, that a script would make shorter or more reliable.
6. One idea: a single improvement, tweak or optimization worth doing next.
   One, not a list.

## 3. Plan

Print the findings as one numbered table: group, path, action (delete, merge,
split, add), why. Keep the idea from group 6 apart, below the table.

Then stop and wait for a yes. The user may answer with row numbers to pick a
subset. When what was found does not match what was asked, in count or in
scope, ask before removing anything.

## 4. Apply

- One logical step at a time: a deletion, a merge, a split, a script.
- After each step, run the tests and the build related to it. Both must pass
  before the next step. A step that breaks either is reverted, not patched
  around.
- Commit each step on its own, with a Conventional Commits message.
- New scripts follow the repo's script rules: executable, a line-1 shebang,
  `-h` and `--help`.
- Update docs that named anything deleted, moved or renamed.

## 5. Report

- What changed and why, one line per step, with its commit.
- What was found but left alone, and why.
- Lines and files removed, and space freed, as exact numbers.
- The one idea from group 6, if it was not applied.

## Rules

- Behavior stays the same. A finding that changes behavior is a proposal for
  the user, never a cleanup.
- Change no file before the yes in step 3.
- Delete only what the plan listed.
- Never remove a test to make a step pass.
