---
name: ishikari
metadata:
  scope: global
description: Run the Ishikari workflow on a task - ants review it, plan it, build it in parallel worktrees, check and fix it, test it combined, and merge it in a straight line - asking the user only while planning, then running on its own. Use when the user runs /ishikari, or says run ishikari, use the ants, or build this with Ishikari. Needs Claude Code's Workflow tool and a git repo.
argument-hint: "<task> [repo path]"
---

# Ishikari

Drive three workflows for one task. A running workflow cannot ask the user, so
this skill runs them in turn. It asks the user only the investigator ant's
questions in step 2. Answering them approves the whole run, merge to main
included. Never ask for approval of the requirement or the plans. After that, never
ask: decide by the rules in steps 3 and 4 and report at the end.

Design, rules and diagram:
[age_of_agents/index.md](../../age_of_agents/index.md).

## Files

| File                         | Job                                          |
| ---------------------------- | -------------------------------------------- |
| `scripts/ishikari.py`        | setup, config; only writer of boards, reqs   |
| `scripts/ishikari-plan.js`   | investigate, requirement, design, plans      |
| `scripts/ishikari-build.js`  | build, check, fix, combined test             |
| `scripts/ishikari-finish.js` | merge, upkeep, move main                     |
| `assets/boards/*.md`         | board templates: bulletin, bounty, critiques |

All paths are relative to this skill's folder. Ishikari keeps its state in
`~/.ishikari/<repo>-<hash>/`, outside the repo; nothing there is committed.
Setup copies the three scripts into `<repo>/.git/ishikari/workflows/`, inside
the working directory, so the Workflow tool may load them by `scriptPath`.

## Rules

- Ask every question with the `/ask-simple` skill, and only in step 2. Never
  answer for the user.
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
- `question`: ask that one question with `/ask-simple`, never batched. Head it
  `Question <n> of about <n + remaining>`, where n counts from 1. Add its `why`
  line when set. Append `{question, answer, critique}` to `answered` (`''` if
  skipped) and run plan again with `{env, task, answered, findings}`, `findings`
  from the last result. Repeat until the result is not `question`.
- `blocked`: show the reason and stop.
- `plans`: do not ask. Show the `report` path (`investigation_report.md`), the
  `design` path (`architecture.md`), the requirement and each plan's title,
  files and `after` as a note, then:
  - if `requirement.needed`, pipe `requirement.entry` into
    `python3 <env.tool> req add <requirement.file>` and commit only that file;
  - pipe the `answeredCritiques` JSON into
    `python3 <env.tool> boards remove <env.state> critiques`;
  - save `testCommand` and `checkCommand` with
    `python3 <env.tool> config <env.state> <key> <value>` and add them to `env`.
- A cleanup plan from the last finish runs like any task, with `cleanup: true`
  on its finish.

## 3. Build

- Run `env.workflows.build` with `{env, plans}`. Later rounds pass `bugs`
  instead of new plans.
- Do not ask. Approve every `awaiting review` task. Drop every `escalated`,
  `blocked` and `error` task, and every task whose `after` holds a dropped
  one. Keep each dropped task, its bugs and fix history for the report.

## 4. Finish

- Run `env.workflows.finish` with `{env, approved, together, drop}`, plus
  `cleanup: true` for a cleanup run. `approved` items are `{id, branch, after}`
  from the build result.
- `bugs` and `waiting`: run a new build round for them with
  `bugs: [{task, branch, bug, after, history}]`, then finish again, without
  asking. At most 2 such rounds per run; after that drop what is left.
- `check`: if it ran and failed, run one build round for the failure as a bug,
  then finish again. If it still fails, stop and report its output. Do not
  mark requirements done.
- `mainMoved: false` with no bugs left to fix: stop and report the reason.
  Nothing is lost; finish can run again once it is fixed.
- Once main moved and `check` passed, run
  `python3 <env.tool> req done <requirement file> <ids>` for the run's
  requirements and commit only that file.
- Report once, at the end: what landed on main, each task's notes and nits,
  each dropped task with why and its bugs, the check, each new critique (one
  line each from `critiques`) and any cleanup plan, offered as the next task.
