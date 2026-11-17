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
| `assets/prompts/investigator.md` | the live investigator ant's brief      |
| `tests/test_ishikari.py`    | the tool: setup, boards, requirements, guards |
| `tests/test_workflows.mjs`   | the scripts' own logic, with stand-in ants   |

Tests: `timeout 120 python3 tests/test_ishikari.py` and
`timeout 120 node --test tests/test_workflows.mjs`.

All paths are relative to this skill's folder. Ishikari keeps its state in
`~/.ishikari/<repo>-<hash>/`, outside the repo; nothing there is committed.
Setup copies the three scripts into `<repo>/.git/ishikari/workflows/`, inside
the working directory, so the Workflow tool may load them by `scriptPath`.

## Rules

- Ask every question with the `/ask-simple` skill, and only in step 2. Never
  answer for the user. Never edit the investigation report yourself.
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

- Start ONE investigator with the Agent tool (general-purpose). Its prompt is
  [assets/prompts/investigator.md](assets/prompts/investigator.md) plus the
  inputs: `env.repo`, `env.main`, `env.state`, the task, the critiques board
  `<env.state>/boards/critiques.md`, the report path
  `<env.state>/plans/<env.run>/investigation_report.md`, and `env.testCommand`
  and `env.checkCommand` when saved. If the last finish left a cleanup plan,
  add one line to the task: `Also consider the cleanup plan at <file>.` The
  investigator decides whether to ask about it; never ask yourself.
- It replies with JSON. While `questions` is not empty, ask them all in one
  `/ask-simple` call (up to 4), headed `Questions <n>-<m> of about <m +
  remaining>`, `why` lines added when set. Send the answers back to the SAME
  agent with SendMessage (`''` if skipped). Never start a new investigator
  for an answer.
- `blocker` set: show the reason and stop.
- `reportWritten`: run `env.workflows.plan` with `{env, task, investigated:
  {testCommand, checkCommand, answeredCritiques}}` from its last reply. It
  skips Review and runs the requirement and design ants.
- Without the Agent tool, fall back to the workflow loop: run plan with
  `{env, task}`; on `question`, ask it and run again with `answered` (append
  `{question, answer, critique}`) and `findings` from the last result.
- `plans`: do not ask. Show the `report` path (`investigation_report.md`), the
  `design` path (`architecture.md`), the requirement and each plan's title,
  files and `after` as a note, then:
  - if `requirement.needed`, pipe `requirement.entry` into
    `python3 <env.tool> req add <requirement.file>` and commit only that file.
    Keep the entry's `:ID:` values: step 4 marks them done;
  - pipe the `answeredCritiques` JSON into
    `python3 <env.tool> boards remove <env.state> critiques`;
  - save `testCommand` and `checkCommand` with
    `python3 <env.tool> config <env.state> <key> <value>` and add them to `env`.
- A run whose task is the cleanup plan passes `cleanup: true` to finish, so
  cleanups never chain.

## 3. Build

- Run `env.workflows.build` with `{env, plans}`. Later rounds pass `bugs`
  instead of new plans.
- Do not ask. Approve every `awaiting review` task. Drop every `escalated`,
  `blocked` and `error` task, and every task whose `after` holds a dropped
  one. Keep each dropped task, its bugs and fix history for the report. A
  dropped task's branch is kept, never deleted, so its work can be looked at.
- `stage: 'error'` from build: show `reason` and stop; nothing reached main.

## 4. Finish

- Run `env.workflows.finish` with `{env, approved, together, drop}`, plus
  `cleanup: true` for a cleanup run. `approved` items are `{id, branch, after}`
  from the build result.
- `bugs` and `waiting`: run a new build round with both lists as `bugs`; each
  item already holds `{task, branch, bug, after}`. Then finish again with that
  build's results, without asking. At most 2 such rounds per run; after that
  drop what is left.
- `check`: if it ran and failed, run one build round with
  `bugs: [{task: 'check-fix', bug: <check.output>}]`: no branch, so a new task
  starts from the moved main. Then finish again. If the check still fails, stop
  and report its output. Do not mark requirements done.
- `mainMoved: false` with no bugs left to fix: stop and report the reason.
  Nothing is lost; finish can run again once it is fixed.
- Once main moved and `check` passed (or there is no `checkCommand`), run
  `python3 <env.tool> req done <requirement file> <ids>` with the `:ID:`
  values kept in step 2, and commit only that file.
- Report once, at the end: what landed on main, each task's notes and nits,
  each dropped task with why and its bugs, the check, each new critique (one
  line each from `critiques`) and any cleanup plan, offered as the next task.
