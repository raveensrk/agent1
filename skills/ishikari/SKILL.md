---
name: ishikari
metadata:
  scope: global
description: Run the Ishikari workflow on a task - ants review it, plan it, build it in parallel worktrees, check and fix it, test it combined, and merge it in a straight line - asking the user only while planning, then running on its own. Use when the user runs /ishikari, or says run ishikari, use the ants, or build this with Ishikari. Needs Claude Code's Workflow tool and a git repo.
argument-hint: "<task> [repo path] [--parallel <n>]"
---

# Ishikari

Drive four workflows for one task: plan, build, finish, then the retrospective. A running workflow cannot ask the user, so
this skill runs them in turn. It asks the user only the investigator ant's
questions in step 2, plus one fast path confirm for a trivial task (2b).
Answering them approves the whole run, merge to main included. Never ask for approval of the plans. After that,
never ask: decide by the rules in steps 3 and 4 and report at the end.

Design, rules and diagram:
[design/index.md](design/index.md).

## Files

| File                             | Job                                      |
| -------------------------------- | ---------------------------------------- |
| `scripts/ishikari.py`            | setup, config; sole logbook writer       |
| `scripts/ishikari-plan.js`       | check the investigator's plans           |
| `scripts/ishikari-build.js`      | build, check, fix, combined test         |
| `scripts/ishikari-finish.js`     | merge, upkeep, move main                 |
| `scripts/ishikari-retro.js`      | retrospective of the run, read only      |
| `assets/prompts/investigator.md` | the investigator's brief: ask, specs, plans |
| `tests/test_ishikari.py`         | tool: setup, logbook, guards             |
| `tests/test_workflows.mjs`       | script logic, with stand-in ants         |

Tests: `timeout 120 python3 tests/test_ishikari.py` and
`timeout 120 node --test tests/test_workflows.mjs`.

All paths are relative to this skill's folder. Ishikari keeps its state in
`~/.ishikari/<repo>-<hash>/`, outside the repo; nothing there is committed.
Setup copies the four scripts into `<repo>/.git/ishikari/workflows/<run>/`,
inside the working directory, so the Workflow tool may load them by
`scriptPath`; each run has its own copy.

## Rules

- Save every workflow result, as it comes: pipe its JSON into
  `python3 <env.tool> save <env.state> <env.run> <stage>` with stage `plan`,
  `build`, `finish` or `retro`. It writes `<stage>-<n>.json` in the run's plans
  folder, numbered per stage. Save each live investigator reply the same way,
  as stage `investigate`. The retrospective ant reads them.
- A result with `logLost`: the logbook clerk failed twice. Pipe that list into
  `python3 <env.tool> log append <env.state>` yourself, and say so in the report.
- Ants live only for their task. An ant started with the Agent tool is stopped
  with TaskStop the moment its task is done, failed or abandoned. Workflow ants
  end when their `agent()` call returns, so they need no stop.
- Ask every question with the `/ask-simple` skill, and only in step 2 (if
  `/ask-simple` is unavailable, ask directly in chat format). Never
  answer for the user. Never edit the product spec, the tech spec or a
  plan yourself: the investigator writes them.
- Every ant runs on Opus at low effort, but one: the investigator, the one
  ant the whole run stands on, runs on Fable at max effort (fallback: latest
  Opus at max effort).
- Run each workflow with the Workflow tool: `scriptPath` from `env.workflows`,
  `args` as a JSON object, never a string. A workflow that was killed or
  paused, or that crashed part way: run it again with the same `scriptPath`
  and `args` plus `resumeFromRunId`, so ants that already replied are not run
  again. Never start it fresh while its ants may still be alive.
- Never edit code, the logbook or branches yourself. Ants and
  `ishikari.py` do. The one exception is the fast path (2b), and even there
  the logbook goes through `ishikari.py`.
- Never push. Main moves only by the finisher's fast-forward.
- Any result with `stage: 'error'`: show `reason`, build nothing more, and go
  to the retrospective (section 5). A stop is never silent: the retrospective still runs.

## Limits

| Cap                                  | Value | Where                      |
| ------------------------------------ | ----- | -------------------------- |
| Workers at once (default)            | 1     | build `MAX_WORKERS`        |
| Workers at once, with `--parallel`   | 5     | build `MAX_PARALLEL`       |
| Tries per bug, then escalated        | 3     | build `MAX_TRIES`          |
| Fix rounds per fix loop              | 3     | build `MAX_ROUNDS`         |
| Combined test rounds                 | 2     | build                      |
| Questions per `/ask-simple` call     | 4     | investigator prompt        |
| Questions in all                     | 8     | investigator prompt        |
| Researchers at once                  | 5     | investigator prompt        |
| Plan check, send-backs               | 1     | skill rule, step 2c        |
| Plans per spec id, at least          | 1     | plan coverage check        |
| Build rounds for merge bugs, waiting | 2     | skill rule, step 4         |
| Check-fix rounds                     | 1     | finish `checkFixDone`      |
| Janitor runs at changed lines        | 100+  | finish `JANITOR_MIN_LINES` |
| Judge pass score (out of 10)         | 7     | finish `PASS`              |
| Judge fix rounds, per finish         | 1     | finish                     |
| Jurors at once (3+ tasks, default)   | 1     | finish `MAX_JURORS`        |
| Jurors at once, with `--parallel`    | 5     | finish `MAX_JURORS`        |
| Files per worker plan, about         | 3     | investigator prompt        |

A task enters a fix loop after its first check, and again after a stuck build,
a changed base or a clash; each loop has its own 3 rounds.

## 1. Setup

- No Workflow tool or no Agent tool in this session: say which is missing and
  stop here, before setup. Nothing else can stand in for them.
- Repo: the path in the arguments, else the current repo.
  Task: the rest of the arguments; if there is none, ask for it.
- `--parallel <n>` in the arguments, n from 2 to 5: keep it as `parallel`.
  Without it `parallel` is 1, the default: the tasks are still split, one
  worker ant per plan, but a single worker, detective or juror runs at any
  moment. With it, up to n run at once. Researchers are read only and stay at
  5 either way. Any other value: say `--parallel takes a whole number from 2
  to 5` and stop, before setup.
- Run `python3 <skill>/scripts/ishikari.py setup <repo> [--main <branch>]`.
  Keep its JSON as `env` for every step. Its `workflows` field holds the four
  script paths (`plan`, `build`, `finish`, `retro`). It also holds `testCommand` and `checkCommand` once saved for
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
    `not a git repo: <repo>`: show the message and stop;
  - `the <what> path ... has a space or a character ...` or `main branch name
    ... is not safe`: the path or name cannot go into the ants' shell
    commands. Show the message and stop; the user moves or renames it.
- A setup that stops has no run: no retrospective.

## 2. Plan

One live investigator ant does all the planning: it asks, proves the task can
be built, and writes two specs and every worker plan:

- `product_spec.md`: the product's behaviours (`B1`, `B2`...) and invariants
  (`I1`, `I2`...), each written so an ant can check it. Nothing else.
- `tech_spec.md`: the architecture and the code's shape.
- `<id>.md`: one thin plan per worker ant: its slice of the specs (files, the
  spec ids it covers, interfaces, tests), with nothing copied from them. A
  one-worker run has no plan file: the worker builds straight from the specs.

It stays alive until its plans pass the check, or a fast path lands. The Agent tool is needed: without
it, say so and stop; there is no other way to plan.

### 2a. Investigate

1. Start ONE investigator with the Agent tool (general-purpose, model `fable`,
   effort `max`; fallback: latest Opus at `max` effort). Its prompt is
   [assets/prompts/investigator.md](assets/prompts/investigator.md) plus the
   inputs: `env.repo`, `env.main`, `env.state`, the task, the plans folder
   `<env.state>/plans/<env.run>/`, and `env.testCommand` and `env.checkCommand`
   when saved. If the last line `<run>/(janitor ant)` of
   `python3 <env.tool> log status <env.state>` says `cleanup dropped`, and
   `<env.state>/plans/<that run>/cleanup*.md` exists, add one line to the task:
   `Also consider the cleanup plan at <file>.` The investigator decides whether
   to ask about it; never ask yourself.
2. It replies with JSON. While `questions` is not empty, ask them all in one
   `/ask-simple` call (up to 4; fallback: ask directly in chat format), headed `Questions <n>-<m> of about <m +
   remaining>`, `why` lines added when set. Send the answers back to the SAME
   agent with SendMessage, as JSON `[{"question", "answer"}]` (`''` if
   skipped). Never start a new investigator for an answer. This holds in both
   of its parts: it may ask again while it designs.
3. Guard the talk; the investigator is an ant, so its replies are checked:
   - a reply that is not the JSON: ask once more for only the JSON;
   - a question it already asked, or more than 8 questions in all: do not ask
     it; tell it to take its recommended answer and go on;
   - no reply, a second non-JSON reply, or a reply with none of questions, a
     written flag or blocker: stop it with TaskStop, show what happened, and
     go to the retrospective (section 5);
   - TaskStop fails: note it for the report and carry on.
4. `blocker` set, at any point: stop the investigator with TaskStop, show the
   reason, and go to the retrospective (section 5).
5. `productSpecWritten` (part 1 is done): check that
   `<plans folder>/product_spec.md` exists; if not, treat it as no
   reply (2a.3). Keep its `ids` list. Save `testCommand` and `checkCommand` with
   `python3 <env.tool> config <env.state> <key> <value>`, the value quoted as
   one argument, and add them to `env`. `config` refuses a value with a line
   break or a backtick: send its message to the SAME investigator once and
   take the command from its next reply; refused again, treat it as no reply
   (2a.3).
   Then:
   - `trivial: true`: go to 2b;
   - else send it `go on` and continue at 2c.

### 2b. Fast path (trivial task)

The investigator judged the task trivial (`trivialWhy`). It waits, alive.

1. Ask with `/ask-simple`: `This looks trivial: <trivialWhy>. Take the fast
   path?` Answers: `Yes, fast path (Recommended)`, `No, full plan`. No: send
   the investigator `go on` and continue at 2c.
2. Yes: you do the work, the one exception to "never edit code yourself".
   Read the product spec first: build its behaviours, keep its invariants.
   - `git -C <env.repo> worktree add -b ishikari/<env.run>/fast
     <env.state>/worktrees/<env.run>-fast <env.main>`; edit and commit there.
   - No test command at all: escalate (step 3); a fast path never lands
     untested.
   - In the worktree run the test command, then the check command when set.
   - Both pass: check that `git -C <env.repo> branch --show-current` is
     `env.main` and `git -C <env.repo> status --porcelain
     --untracked-files=no` prints nothing; then
     `git -C <env.repo> merge --ff-only ishikari/<env.run>/fast`, remove the
     worktree (`git -C <env.repo> worktree remove --force <env.state>/worktrees/<env.run>-fast`)
     and delete the branch (`git -C <env.repo> branch -D ishikari/<env.run>/fast`). Wrong branch, local changes or a refused
     fast-forward (main moved on): never force it; escalate (step 3).
   - Log it: pipe `[{"run": env.run, "who": "main session", "event": "fast
     path landed", "detail": "<sha>: <trivialWhy>"}]` into `python3 <env.tool>
     log append <env.state>`.
3. Escalate when the work turns out bigger (more than 2 files, a design
   choice, more than one task) or a test or the check fails and a small fix
   does not clear it: remove the worktree (`git -C <env.repo> worktree remove --force <env.state>/worktrees/<env.run>-fast`),
   delete the branch (`git -C <env.repo> branch -D ishikari/<env.run>/fast`, the edits go),
   and send the investigator `go on: a fast path was tried and given up:
   <why>`. Continue at 2c, passing `escalated: '<why>'` to the plan check. The
   run carries on without asking.
4. Landed: stop the investigator with TaskStop, and report what landed (sha,
   files), and the tests and check. A landed fast path ends the run: no
   retrospective.

### 2c. Tech spec and plans

1. The investigator now proves the task can be built, writes
   `tech_spec.md` and one plan file per task. It may ask more questions
   (2a.2 and 2a.3 hold). `blocker`: 2a.4.
2. `plansWritten`: check that `tech_spec.md` exists in the plans folder, and
   `<id>.md` for every plan in its `plans` list when there are two or more
   (one plan: no plan file is written). A missing file is a problem to send
   back (step 4).
3. Run `env.workflows.plan` with `{env, task, ids, plans, testCommand,
   checkCommand}` from its reply, plus `escalated` after a given-up fast path.
   No ant plans there: the script only checks the list (plan ids, loops in
   `after`, two tasks on one file, paths inside the repo, and that every
   behaviour and invariant id is covered by a plan and no plan covers an
   unknown one) and logs the `investigated` entry.
4. `problems`: send the list back to the SAME investigator once; it fixes the
   plans and replies again. Run the check again with `recheck: true`. Problems
   a second time: stop the investigator, show them, and go to the retrospective (section 5).
5. `plans`: stop the investigator with TaskStop; its work is over. Do not ask.
   Show the `productSpec` and `techSpec` paths and each plan's title, files,
   `covers` and `after` as a note.
- A run whose task is a dropped cleanup plan passes `cleanup: true` to finish,
  so cleanups never chain.

## 3. Build

- Run `env.workflows.build` with `{env, plans, parallel}`. Later rounds pass `bugs`
  instead of new plans, and `parallel` again. A detective reuses its worker's test result only when
  the worktree's HEAD is the worker's sha and the tree is clean.
- Do not ask. Approve every `awaiting review` task. Drop every `escalated`,
  `blocked` and `error` task, and every task whose `after` holds a dropped
  one; repeat until no such task is left. Keep each dropped task, its bugs
  and fix history for the report. A dropped task's branch is kept, never
  deleted, so its work can be looked at.
- No task approved: still run finish once, with `approved: []` and the drops,
  so they reach the logbook. Nothing merges and main stays.
- `stage: 'error'` from build: show `reason` and go to the retrospective (section 5); nothing reached
  main.

## 4. Finish

- Run `env.workflows.finish` with `{env, approved, together, drop, round,
  landed, parallel}`, plus `cleanup: true` for a cleanup run. `approved` items are
  `{id, branch, after}` from the build result. `round` is this run's finish
  number (1, then 2, ...): a later finish uses its own upkeep branches, so
  branches kept by an earlier one stay. `landed` holds every task id the
  earlier finishes of this run reported in `merged`: their branches are gone,
  and a task built on one must not be blocked for it.
- `bugs` and `waiting`: run a new build round with both lists as `bugs`; each
  item already holds `{task, branch, bug, after}`. Then finish again, without
  asking: `approved` is that build's passing tasks plus every `notMoved` item
  of the finish before (merged in its scratch copy, but main did not move, so
  they still have to land). At most 2 such rounds per run; after that drop
  what is left.
- Never take the finisher ant's word for main. After every finish with a
  `sha`, run `git -C <env.repo> merge-base --is-ancestor <sha> <env.main>`:
  exit 0 means main holds the checked commit. `mainMoved: true` but it fails:
  main did not move; treat the result as `mainMoved: false`, its `merged`
  tasks as `notMoved`, and say so in the report. `mainMoved: false` but it
  succeeds (the finisher died after the move): main did move; count the
  `notMoved` tasks as landed and say so.
- `checkFix` set (check failed, no check-fix yet): run one build round with
  `bugs: [checkFix]`: no branch, so a new task starts from the moved main.
  Then finish again with `checkFixDone: true` (finish also assumes it when
  `check-fix` is in `approved` or `drop`). `checkFixRefused`: the check
  still fails; report `check.output` and go to the retrospective (section 5).
- `mainMoved: false` with no bugs left to fix: report the reason and go to
  the retrospective (section 5). Nothing is lost; finish can run again once it is fixed.
- `upkeepStopped` set: the scratch copy could not be put back after a rejected
  cleanup, judge fix or docs update, so the rest of upkeep was skipped. Main
  still moved only to the last checked commit. Report it.
- How finish works, so its results read right:
  - it reuses build's trial merge (`together.sha`) when the approved set
    matches it or only adds tasks, main is an ancestor of it and `git cherry`
    finds every reused task's commits in it; else it merges from main;
  - the merger ant then checks its own merge with `git cherry`; a task the
    merger called merged but git finds missing comes back as a merge bug;
  - upkeep order: janitor, judge (with its fix round), docs ant. Work an ant
    lands counts only with its checks passed and its new commit named;
    anything else is put back on the scratch copy, and main moves to the last
    checked commit, never to a branch name;
  - after the cleanup, the judge ant scores the whole run 0-10 against the
    product spec, id by id: does each behaviour hold, does each invariant
    hold. Detectives check tasks against the plan and the tech spec; the
    judge does not score those. With 3+ tasks it first
    sends one juror ant per task (one at a time, or `parallel` at once) and decides from their reports;
    the score is its own call, not an average. Below 7: one fix round
    (worker, then a detective that lands the fix), then a second score. At 7 or
    more the same round still runs, only for the gaps the judge lists as
    `bugs` (wrong behaviour, never a missing test alone). Still below 7: main moves
    anyway and `verdict.flagged` is true;
  - last, the docs ant runs `/docs` in update mode on the final code (or updates
    the documentation directly if `/docs` is unavailable), in its
    own worktree; it lands only if the docs' own `build.sh check` (when
    present) and the tests pass and it changed docs only. No `docs/` or
    `doc/`: it changes nothing, since create mode needs the user. Dropped: its
    branch `ishikari/<run>/_docs` is kept, `docs.reason` says why, main still
    moves.
- Report once, at the end: what landed on main, each task's notes and nits,
  each dropped task with why and its bugs, the check, the judge's `verdict` (score,
  gaps; say FLAGGED when `flagged`), the cleanup: `landed`, or dropped with its
  `reason` and `branch`, its plan offered as the next task, and the docs
  update: `landed`, or dropped with its `reason` and `branch`.
  Every workflow ant's result is in the logbook the moment it replies (the live
  investigator gets only an `investigated` entry), so a crashed run
  still leaves its trail. End with where the full record is: `python3 <env.tool> log status <env.state>
  <env.run>`.

## 5. Retrospective

- Once, as the very last step of every run that got past setup, however it
  ended: main moved, stopped, blocked or error. Only two endings have none: a
  setup that stopped, and a fast path that landed.
- Run `env.workflows.retro` with `{env, outcome}`: `outcome` says how the run
  ended in a few words. The retrospective ant reads this run's logbook, the
  plans folder (product spec, tech spec, plans, cleanup note, stage results), the
  run's git history and Ishikari's own source, and writes
  `<env.state>/plans/<env.run>/retrospective.md`. It is read only: it changes
  no code, branch or repo file, and the script checks that: it compares the
  repo's refs, worktrees and status before and after. Never act on its
  findings yourself.
- Add to the final report: its `summary`, the top 3 `findings` (category,
  title, `where`) and the path to `retrospective.md`. `stage: 'error'`: say
  the retrospective failed and why; the run's result stands.
