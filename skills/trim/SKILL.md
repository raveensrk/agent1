---
name: trim
metadata:
  scope: global
description: Find features too complex for a project's goal and report each one with its size in lines of code, a simpler way to do it and the lines that would save. Use when the user says trim, reduce features, cut scope, find overbuilt or overengineered code, what is too complex for this project, or runs /trim. Reports first and removes or simplifies only the features the user picks.
argument-hint: "[path or area, e.g. src/export]"
---

# Trim a project

Judge each feature against what the project is for. Report the ones that are
bigger or more complex than the goal needs. Change nothing until the user
picks.

Not the same as `maintain`: that finds dead code. This finds live code that
does more than the project needs.

## 1. Find the goal

- Read the repo's `README`, `AGENTS.md` or `CLAUDE.md`, requirements and docs.
- Write the goal in one or two plain lines: who uses it, for what.
- If no goal is written down, ask the user for it in one short question
  before scanning. Never guess the goal.
- Limit the scan to the path or area given as an argument, if any.

## 2. List the features

- A feature is something a user can do: "export to PDF", "sync over SSH",
  "theme picker". Not a folder, not a module.
- Map each feature to all its code: files, functions, tests, config, scripts.
  Code shared by several features goes to a `shared` row, not counted twice.
- Count lines of code per feature: no blank lines, no comment lines. Use
  `cloc` or `tokei` when installed, a script otherwise. Report source and
  test lines apart.

## 3. Judge each feature

Flag a feature when one of these holds, and name which:

1. Out of scope: the goal does not need it.
2. Overbuilt: it fits the goal but is far larger than the job needs -
   plugin systems for one plugin, config for values never changed, layers
   that only pass calls through, general code with one caller.
3. Rare and costly: little use for its size, measured by tests, docs, callers
   or git history, not by guess.

For each flagged feature, give a simpler way to do it and its new size as an
estimate in lines. "Remove" is a valid simpler way.

## 4. Report

Print one numbered table, largest saving first:

| # | Feature | Lines (src / test) | Reason | Simpler way | New lines | Saved |

Below it:

- The goal used for judging, one line.
- Total lines in scope, total flagged, total that could be saved.
- Features checked and kept, one line each, so the user sees what passed.

Then stop and wait. The user answers with row numbers to pick, or none.

## 5. Apply the picked rows

- One feature at a time. Remove or simplify it as the report said.
- Run the tests and build related to it. Both must pass before the next one;
  a change that breaks either is reverted.
- Remove the feature's tests, docs and config with it. Never remove a test
  only to make a step pass.
- Commit each feature on its own, with a Conventional Commits message.
- When what is found does not match what was picked, in count or in scope,
  ask before removing.

## 6. Report back

- Per feature: what changed, lines before and after, commit.
- Total lines removed, exact.

## Rules

- Change no file before the user picks rows in step 4.
- Every size is a measured number; only "New lines" is an estimate, and it is
  marked as one.
- Behavior outside the picked features stays the same.
