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
| `scripts/ishikari.py`        | setup, config; only writer of boards, reqs   |
| `scripts/ishikari-plan.js`   | review the task, write the plans             |
| `scripts/ishikari-build.js`  | build, check, fix, test together             |
| `scripts/ishikari-finish.js` | merge, upkeep, move main                     |
| `assets/boards/*.md`         | board templates: bulletin, bounty, critiques |

All paths are relative to this skill's folder. Ishikari keeps its state in
`~/.ishikari/<repo>-<hash>/`, outside the repo; nothing there is committed.
Setup copies the three scripts into `<repo>/.git/ishikari/workflows/`, inside
the working directory, so the Workflow tool may load them by `scriptPath`.

## Rules

- Ask every question with the `/ask-simple` skill. Never answer for the user.
- Run each workflow with the Workflow tool: `scriptPath` from `env.workflows`,
  `args` as a JSON object, never a string.
- Never edit code, boards, requirements or branches yourself. Ants and
  `ishikari.py` do.
- Never push. Main moves only by the finisher's fast-forward.
- Any result with `stage: 'error'`: show `reason` and stop.

## 1. Setup

- Repo: the path in the arguments, else the current repo. Task: the rest of the
  arguments; if there is none, ask for it.
- Run `python3 <skill>/scripts/ishikari.py setup <repo>`. Keep its JSON as `env`
  for every step. Its `workflows` field holds the three script paths. It also
  holds `testCommand` and `checkCommand` once saved for this repo.

## 2. Plan

- Run `env.workflows.plan` with `{env, task}`. If the last finish left a cleanup
  plan, offer it as an extra task.
- `review`: ask its questions, then run again with the same `scriptPath`,
  `resumeFromRunId` set to the first run's id, and `{env, task, answers}`: one
  answer per question, in order, `''` if skipped. The review replays from
  cache; never retype it.
- `blocked`: show the reason and stop.
- `plans`: show the requirement and each plan's title, files and `after`. Ask
  for approval. On yes:
  - if `requirement.needed`, pipe `requirement.entry` into
    `python3 <env.tool> req add <requirement.file>` and commit only that file;
  - pipe the `answeredCritiques` JSON into
    `python3 <env.tool> boards remove <env.state> critiques`;
  - save `testCommand` and `checkCommand` with
    `python3 <env.tool> config <env.state> <key> <value>` and add them to `env`.
- A cleanup plan from the last finish changes no behaviour: this plan
  approval is its only gate. If the build then returns it `awaiting review`
  with no bugs, go straight to finish with `cleanup: true`, without asking
  again; show the result after.

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

- Run `env.workflows.finish` with `{env, approved, together, drop}`, plus
  `cleanup: true` for a cleanup run. `approved` items are `{id, branch, after}`
  from the build result.
- `mainMoved: false`: show the reason. Nothing is lost; run finish again once it
  is fixed.
- `bugs` and `waiting`: offer a new build round for them.
- `check`: if it ran and failed, show its output and offer a build round for
  the failure. Do not mark requirements done.
- Once main moved and `check` passed (or the user saw the app work), run
  `python3 <env.tool> req done <requirement file> <ids>` for the run's
  requirements and commit only that file.
- Report what landed on main, the check, each new critique (one line each from
  `critiques`) and any cleanup plan.
