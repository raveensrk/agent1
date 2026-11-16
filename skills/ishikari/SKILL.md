---
name: ishikari
metadata:
  scope: global
description: Run the Ishikari workflow on a task - ants review it, plan it, build it in parallel worktrees, check and fix it, test it together, and merge it in a straight line - stopping only to ask the user. Use when the user runs /ishikari, or says run ishikari, use the ants, or build this with Ishikari. Needs Claude Code's Workflow tool and a git repo.
argument-hint: "<task> [repo path]"
---

# Ishikari

Drive three workflows for one task. A running workflow cannot ask the user, so
this skill runs them in turn and asks between them.

Design, rules and diagram:
[age_of_agents/index.md](../../age_of_agents/index.md).

## Files

| File                         | Job                                          |
| ---------------------------- | -------------------------------------------- |
| `scripts/ishikari.py`        | sets up a run; the only writer of boards     |
| `scripts/ishikari-plan.js`   | review the task, write the plans             |
| `scripts/ishikari-build.js`  | build, check, fix, test together             |
| `scripts/ishikari-finish.js` | merge, upkeep, move main                     |
| `assets/boards/*.md`         | board templates: bulletin, bounty, critiques |

All paths are relative to this skill's folder. Ishikari keeps its state in
`~/.ishikari/<repo>-<hash>/`, outside the repo; nothing there is committed.

## Rules

- Ask every question with the `/ask-simple` skill. Never answer for the user.
- Run each workflow with the Workflow tool: `scriptPath` from `env.workflows`,
  `args` as a JSON object, never a string.
- Never edit code, boards or branches yourself. Ants and `ishikari.py` do.
- Never push. Main moves only by the finisher's fast-forward.
- Any result with `stage: 'error'`: show `reason` and stop.

## 1. Setup

- Repo: the path in the arguments, else the current repo. Task: the rest of the
  arguments; if there is none, ask for it.
- Run `python3 <skill>/scripts/ishikari.py setup <repo>`. Keep its JSON as `env`
  for every step. Its `workflows` field holds the three script paths.

## 2. Plan

- Run `env.workflows.plan` with `{env, task}`. If the last finish left a cleanup
  plan, offer it as an extra task.
- `review`: ask its questions, then run again with
  `{env, task, review, answers}`: one answer per question, in order, `''` if
  skipped.
- `blocked`: show the reason and stop.
- `plans`: show the requirement and each plan's title, files and `after`. Ask
  for approval. On yes:
  - write the requirement to its file and commit only that file;
  - pipe the `answeredCritiques` JSON into
    `python3 <env.tool> boards remove <env.state> critiques`;
  - add the result's `testCommand` to `env`.

## 3. Build

- Run `env.workflows.build` with `{env, plans}`. Later rounds pass `bugs`
  instead of new plans.
- Final review: for each task show status, notes, nits, base problems and fix
  history. Show escalated, blocked and error tasks with their bugs. Offer the
  diff: `git -C <repo> diff <main>...<branch>`.
- Ask which tasks to approve, which to send back (with the user's guidance) and
  which to drop. Tasks sent back go to a new build round as
  `bugs: [{task, branch, bug, after, history, guidance}]`.

## 4. Finish

- Run `env.workflows.finish` with `{env, approved, together, drop}`. `approved`
  items are `{id, branch, after}` from the build result.
- `mainMoved: false`: show the reason. Nothing is lost; run finish again once it
  is fixed.
- `bugs` and `waiting`: offer a new build round for them.
- Report what landed on main, the new critiques count and any cleanup plan.
