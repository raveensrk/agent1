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
questions in step 2, plus one fast path confirm for a trivial task (2c).
Answering them approves the whole run, merge to main included. Never ask for approval of the requirement or the plans. After that,
never ask: decide by the rules in steps 3 and 4 and report at the end.

Design, rules and diagram:
[design/index.md](design/index.md).

## Files

| File                             | Job                                      |
| -------------------------------- | ---------------------------------------- |
| `scripts/ishikari.py`            | setup, config; sole logbook, reqs writer |
| `scripts/ishikari-plan.js`       | investigate, requirement, design, plans  |
| `scripts/ishikari-build.js`      | build, check, fix, combined test         |
| `scripts/ishikari-finish.js`     | merge, upkeep, move main                 |
| `assets/prompts/investigator.md` | the live investigator ant's brief        |
| `tests/test_ishikari.py`         | tool: setup, logbook, reqs, guards       |
| `tests/test_workflows.mjs`       | script logic, with stand-in ants         |

Tests: `timeout 120 python3 tests/test_ishikari.py` and
`timeout 120 node --test tests/test_workflows.mjs`.

All paths are relative to this skill's folder. Ishikari keeps its state in
`~/.ishikari/<repo>-<hash>/`, outside the repo; nothing there is committed.
Setup copies the three scripts into `<repo>/.git/ishikari/workflows/`, inside
the working directory, so the Workflow tool may load them by `scriptPath`.

## Rules

- Ants live only for their task. An ant started with the Agent tool is stopped
  with TaskStop the moment its task is done, failed or abandoned. Workflow ants
  end when their `agent()` call returns, so they need no stop.
- Ask every question with the `/ask-simple` skill, and only in step 2. Never
  answer for the user. Never edit the investigation report yourself.
- Run each workflow with the Workflow tool: `scriptPath` from `env.workflows`,
  `args` as a JSON object, never a string.
- Never edit code, the logbook, requirements or branches yourself. Ants and
  `ishikari.py` do. The one exception is the fast path (2c), and even there
  the logbook and requirements go through `ishikari.py`.
- Never push. Main moves only by the finisher's fast-forward.
- Any result with `stage: 'error'`: show `reason` and stop.

## Limits

| Cap                                  | Value | Where                      |
| ------------------------------------ | ----- | -------------------------- |
| Workers at once                      | 5     | build `MAX_WORKERS`        |
| Tries per bug, then escalated        | 3     | build `MAX_TRIES`          |
| Fix rounds per task                  | 3     | build `MAX_ROUNDS`         |
| Combined test rounds                 | 2     | build                      |
| Questions per `/ask-simple` call     | 4     | investigator prompt        |
| Questions in all (live investigator) | 8     | investigator prompt        |
| Research bursts per question (2b)    | 2     | plan `MAX_RESEARCH`        |
| Researchers per burst (2b)           | 5     | plan `MAX_RESEARCHERS`     |
| Same question twice (2b)             | error | plan same-question         |
| Build rounds for merge bugs, waiting | 2     | skill rule, step 4         |
| Check-fix rounds                     | 1     | finish `checkFixDone`      |
| Janitor runs at changed lines        | 100+  | finish `JANITOR_MIN_LINES` |
| Judge pass score (out of 10)         | 7     | finish `PASS`              |
| Judge fix rounds                     | 1     | finish                     |
| Jurors at once (3+ tasks)            | 5     | finish `MAX_JURORS`        |
| Files per worker plan, about         | 3     | architect prompt           |

## 1. Setup

- Repo: the path in the arguments, else the current repo.
  Task: the rest of the arguments; if there is none, ask for it.
- Run `python3 <skill>/scripts/ishikari.py setup <repo> [--main <branch>]`.
  Keep its JSON as `env` for every step. Its `workflows` field holds the three
  script paths. It also holds `testCommand` and `checkCommand` once saved for
  this repo. `env.run` is `YYYYmmdd-HHMMSS-xxxx` (4 hex digits).
- Main branch: `origin/HEAD` if a local branch of that name exists, else
  `main`, `master`, `trunk`. From a linked worktree, setup uses the main
  checkout. That checkout must be on the main branch with no uncommitted
  tracked changes.
- Setup stops with a message:
  - `no main branch in <repo>: ...; pass --main <branch>` or
    `main branch <m> does not exist in <top>; pass --main <branch>`: ask the
    user which branch, rerun with `--main`;
  - `<top> is on <x>, not the main branch <m>; check out <m> first`,
    `<top> has uncommitted changes; commit or stash them first` or
    `not a git repo: <repo>`: show the message and stop.

## 2. Plan

### 2a. Live investigator

1. Start ONE investigator with the Agent tool (general-purpose, model `opus`,
   effort `low` when the tool takes it; its researchers the same). Its prompt is
   [assets/prompts/investigator.md](assets/prompts/investigator.md) plus the
   inputs: `env.repo`, `env.main`, `env.state`, the task, the report path
   `<env.state>/plans/<env.run>/investigation_report.md`, and `env.testCommand`
   and `env.checkCommand` when saved. If the last finish dropped a cleanup,
   add one line to the task: `Also consider the cleanup plan at <file>.` The
   investigator decides whether to ask about it; never ask yourself.
2. It replies with JSON. While `questions` is not empty, ask them all in one
   `/ask-simple` call (up to 4), headed `Questions <n>-<m> of about <m +
   remaining>`, `why` lines added when set. Send the answers back to the SAME
   agent with SendMessage (`''` if skipped). Never start a new investigator
   for an answer.
3. `blocker` set: stop the investigator with TaskStop, show the reason and stop.
4. `reportWritten`: stop the investigator with TaskStop first; its work is
   over and the report is all later ants read. Then run `env.workflows.plan`
   with `{env, task, investigated: {testCommand, checkCommand}}` from its
   last reply. It skips Review, logs one `investigated` entry with the report
   path, then runs the requirement and design ants. With `env.requirements`
   empty (the repo keeps no `requirements.org` or `requirements/*.org`), it
   skips the add requirement ant and returns `requirement.needed: false`.
   If the reply has `trivial: true`, go to 2c before running the plan.

### 2b. Fallback (no Agent tool)

1. Run `env.workflows.plan` with `{env, task}`.
2. On `question`, ask it and run again with `answered` (append
   `{question, answer}`) and `findings` from the last result.
3. A question already in `answered` returns `stage: 'error'`.
4. `trivial`: the report is written; go to 2c.

### 2c. Fast path (trivial task)

The investigator judged the task trivial (`trivialWhy`). No more ants run.

1. Ask with `/ask-simple`: `This looks trivial: <trivialWhy>. Take the fast
   path?` Answers: `Yes, fast path (Recommended)`, `No, full plan`. No: run
   `env.workflows.plan` with `{env, task, investigated: {testCommand,
   checkCommand}}` and go on at 2d.
2. Yes: you do the work, the one exception to "never edit code yourself".
   Read the report first; it is the spec.
   - `git -C <env.repo> worktree add -b ishikari/<env.run>/fast
     <env.state>/worktrees/<env.run>-fast <env.main>`; edit and commit there.
   - In the worktree run `env.testCommand`, then `env.checkCommand` when set.
   - Both pass: `git -C <env.repo> merge --ff-only ishikari/<env.run>/fast`,
     then remove the worktree and delete the branch.
   - With `env.requirements` set, draft the requirement entry the
     /add-requirement way, pipe it into `python3 <env.tool> req add <file>`,
     and after main moves run `req done` with its `:ID:`s; commit only that file.
   - Log it: pipe `[{"run": env.run, "who": "main session", "event": "fast
     path landed", "detail": "<sha>: <trivialWhy>"}]` into `python3 <env.tool>
     log append <env.state>`.
3. Escalate when the work turns out bigger (more than 2 files, a design
   choice, more than one task) or a test or the check fails and a small fix
   does not clear it: remove the worktree, delete the branch (the edits go),
   and run `env.workflows.plan` with `{env, task, investigated: {testCommand,
   checkCommand}, escalated: '<why>'}`. It logs the escalation and tells the
   planners why. Go on at 2d; the run carries on without asking.
4. Report what landed (sha, files), the tests and check, and the requirement.

### 2d. Plans

- `plans`: do not ask. Show the `report` path (`investigation_report.md`), the
  `design` path (`architecture.md`), the requirement and each plan's title,
  files and `after` as a note, then:
  - if `requirement.needed`, pipe `requirement.entry` into
    `python3 <env.tool> req add <requirement.file>` and commit only that file.
    Keep the entry's `:ID:` values: step 4 marks them done;
  - save `testCommand` and `checkCommand` with
    `python3 <env.tool> config <env.state> <key> <value>` and add them to `env`.
- A run whose task is a dropped cleanup plan passes `cleanup: true` to finish,
  so cleanups never chain.

## 3. Build

- Run `env.workflows.build` with `{env, plans}`. Later rounds pass `bugs`
  instead of new plans. A detective reuses its worker's test result only when
  the worktree's HEAD is the worker's sha and the tree is clean.
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
- `checkFix` set (check failed, no check-fix yet): run one build round with
  `bugs: [checkFix]`: no branch, so a new task starts from the moved main.
  Then finish again with `checkFixDone: true` (finish also assumes it when
  `check-fix` is in `approved` or `drop`). `checkFixRefused`: the check
  still fails; stop and report `check.output`. Do not mark requirements done.
- `mainMoved: false` with no bugs left to fix: stop and report the reason.
  Nothing is lost; finish can run again once it is fixed.
- Once main moved and `check` passed (or there is no `checkCommand`), run
  `python3 <env.tool> req done <requirement file> <ids>` with the `:ID:`
  values kept in step 2, and commit only that file. No ids kept (no
  requirement, or `env.requirements` is empty): skip it.
- How finish works, so its results read right:
  - it reuses build's trial merge (`together.sha`) when the approved set
    matches it or only adds tasks, and git shows main and each reused branch
    tip are ancestors of it; else it merges from main;
  - the merger ant then checks its own merge with `git cherry`; a task the
    merger called merged but git finds missing comes back as a merge bug;
  - before the janitor, the docs ant runs `/docs` in update mode on the
    merged copy, in its own worktree; it lands only if `docs/build.sh check`
    (when present) and the tests pass. No `docs/` or `doc/`: it changes
    nothing, since create mode needs the user. Dropped: its branch
    `ishikari/<run>/_docs` is kept, `docs.reason` says why, main still moves;
  - after the cleanup, the judge ant scores the whole run 0-10 against the
    plans (report, architecture, worker plans). With 3+ tasks it first
    sends one juror ant per task (5 at once) and decides from their reports;
    the score is its own call, not an average. Below 7: one fix round
    (worker, detective), then a second score. Still below 7: main moves
    anyway and `verdict.flagged` is true.
- Report once, at the end: what landed on main, each task's notes and nits,
  each dropped task with why and its bugs, the check, the judge's `verdict` (score,
  gaps; say FLAGGED when `flagged`) and the cleanup: `landed`, or dropped with its
  `reason` and `branch`, its plan offered as the next task.
  Every workflow ant's result is in the logbook the moment it replies (the live
  investigator gets only an `investigated` entry), so a crashed run
  still leaves its trail. End with where the full record is: `python3 <env.tool> log status <env.state>
  <env.run>`.
