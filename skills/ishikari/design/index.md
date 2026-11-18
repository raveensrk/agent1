# Index

Design documentation and design bible for Ishikari, a workflow where AI agents
("ants") work in parallel to complete a task.

## Goal

Take any task from the user and finish it with many ants working in parallel.
The user is asked only once: the investigator ant's questions. Answering
them approves the whole run, merge to main included. The add requirement ant
only adds: it never asks. Build, check, fix, merge and upkeep run on their own,
and the run ends with one report.

Ishikari is a higher-order workflow: a plan can name another saved workflow as
its job. The build script runs that workflow in place of a worker ant.

## Flow

01. **Task in.** The user gives a task. It can be anything.

02. **Investigator Ant** has one goal: a bulletproof investigation report, so
    no later ant needs to ask. It critiques the task and finds the
    repo's test command. When it lacks facts it sends up to 5
    **Researcher Ants** in parallel; they search the web and the whole computer,
    read only, never secrets, and report back. It is one live agent for the
    whole talk, run by the skill, not a workflow: it reads the repo once and
    gets each answer as a message. It asks up to 4 independent questions at
    a time with `/ask-simple`, with a best-guess count:
    "Questions 1-3 of about 5". It
    stops once nothing important is unclear, then writes
    `investigation_report.md` in the run's plans folder: goal, scope, every
    decision, facts with sources, constraints, risks, assumptions, acceptance
    checks and commands. Every claim cites an answer, a fact or the repo.
    It writes nothing to the logbook itself: it runs outside any workflow,
    and the main session never writes the logbook. When `ishikari-plan`
    starts after it, it logs one `investigated` entry with the report path;
    the investigator's researchers are not logged. Without the Agent tool,
    the plan workflow runs the investigator and its researcher ants itself,
    and logs each reply.

03. **Add Requirement Ant** only adds the requirement. It reads only the
    investigation report and the repo; where the report and its own idea
    differ, the report wins. It drafts the requirement with the
    `/add-requirement` skill and shows it can be built from the repo's code and
    docs, writing a throwaway spike outside the repo only when that is not
    enough. It never asks the user, and never designs or plans. The main session
    pipes its entry into `ishikari.py req add` and commits it.

03b. **Architect Ant** reads the report and the requirement and writes
    `architecture.md` beside the report: the parts of the change, the files each
    part owns, and every name, interface and data shape that crosses between
    parts, so parallel workers fit together. It maps each acceptance check to
    the part that proves it, then writes one plan per worker ant.
    Like every workflow ant, the add requirement ant and the architect ant
    each get a logbook entry the moment they reply.

04. **Plans.** Workers cannot ask questions, so each plan is complete. Tasks are
    split so no two edit the same file, and each task has its own test file.
    Only a task that must edit another task's file lists that task in `after`:
    it starts as soon as that task is built, on top of its branch. Before
    anything is built, the plan script rejects bad or unknown ids, loops in
    `after`, two tasks that edit one file without one being after the other,
    and a requirement that is not an `.org` file in the repo or has no `:ID:`.
    File paths are normalised first, so `./a.py` and `a.py` count as one file.

05. **Worker Ant** builds its plan in its own git worktree, at most 5 at a time.
    It decides on its own, goes as far as it can, and commits all its work,
    including the docs its change affects, so docs land with the code. A worker
    that gets stuck reports why, and that becomes a bug.

06. **Inspector Ant**: one per built task, started the moment the task or a
    fix for it is built. No ant watches for that: the build script starts every
    ant, so it starts the inspector as soon as the worker returns. It reads only; it never changes code.
    - **Checks:** the task's own work against its plan, and against
      `architecture.md`: a name or interface that differs from the design is a
      bug. It runs the tests in the task's worktree.
    - **Pass:** no bugs. The task waits for the combined test. Style points go
      to the final report as notes.
    - **Fail:** it returns each bug, with how to see it, and the first fix
      plan, so round 1 needs no detective. The build script keeps the bugs and
      hands them to the next ant; the logbook only records them.
    - **Tasks built on others** are checked only once those are final. A
      changed base is merged in first; a failed base blocks the task.
    - **Re-check:** after each fix it checks every open bug again, by its id.

07. **Detective Ant**: finds why a bug is still open after a failed fix. It
    reads only; it never writes code.
    - **Round 1** needs no detective: the worker builds the inspector's first
      fix plan.
    - **Round 2 on:** for each bug still open, it finds the cause and writes
      the next fix plan. A worker ant builds it, and the inspector re-checks
      each open bug by its id.
    - **Memory:** each round sees every earlier round's cause, plan and
      outcome, so it never repeats a failed idea.
    - **Give up:** a bug still open after its last try drops the task, and tasks
      built on it drop too; the final report lists them.
    - An ant that crashes is retried once and never counts as a bug.

08. **Combined test, by the Integrator Ant.** Tasks are built and inspected
    alone, so two can pass alone and still break when combined. When every
    task is done, the integrator ant merges all passing tasks in a straight
    line in a scratch copy, a throwaway copy that never touches main, and runs
    the tests once. It is a dress rehearsal for the merger ant in Finish. A task
    that clashes takes in the tasks it clashes with and goes back through the
    fix loop, and the test runs once more. No one reviews by hand.

09. **Merger Ant** runs straight after. It adds every passing task's
    commits in a straight line, with no merge commits, in a scratch copy, in
    dependency order, and tests once. It may reuse the combined test's merge
    (see [Finish](../SKILL.md#4-finish)). It refuses a task
    whose base was dropped. A failed merge, or a task left waiting, goes back
    to a new build round on its own; what is left after the last round is
    dropped and reported. Main moves forward only as a fast-forward, which git
    refuses if it would overwrite local edits.

## Upkeep ants

They run once per finish, on the merged result, before main moves.

- **Janitor ant** finds mess left by the merged tasks, and only that, and writes
  a cleanup plan. A worker ant builds it at once on top of the merged scratch
  copy, and an inspector ant checks it and runs the tests: the combined test.
  A failed check gets one fix round (detective, worker, inspector). Passed: the
  cleanup lands as its own commits after the tasks, in the same main move.
  Still failing: it is dropped, main moves with the tasks alone, the cleanup
  branch is kept and the next plan stage hands its plan to the investigator ant,
  which may ask about it. One cleanup per run: a dropped cleanup's own run gets
  no janitor, so cleanups never chain.
- **Judge ant** gives the final verdict. It runs after the janitor's cleanup has
  landed or been dropped, reads the plans (investigation report, architecture
  and every worker plan) and the merged code with the cleanup on top, and
  scores the whole run 0-10 on one question: does the implementation match the
  plans? It lists each gap as a concrete fix. With three or more tasks it
  delegates first: one **Juror ant** per task, up to 5 at once, each scoring
  its task against that task's plan. The judge weighs their reports, checks
  how the tasks fit together and decides the score itself; it is not an
  average. One or two tasks: the judge works alone. At 7 or more, main moves. Below
  7 with gaps, one fix round: a worker ant closes the gaps on top of the
  merged scratch copy, an inspector ant checks it and runs the tests, a merger
  ant fast-forwards the scratch copy to it (the only way the fix lands), and
  the judge scores again. Still below 7, or the fix failed (its branch is kept
  and the verdict says why): main moves anyway and the verdict is
  flagged in the report. The judge never blocks main, so a run never gets
  stuck on a score.

## Rules

- Ants work in parallel wherever nothing forces an order. Fix rounds, tasks in
  `after` and merges run in order.
- Only the main session asks the user questions, and only in the plan stage.
  Ants report problems in their results; after planning, the main session
  decides by the fixed rules in the skill and reports at the end.
- Only worker ants write code. Every other ant reads, plans, reviews, merges or
  records to the logbook.
- At most 5 worker ants run at the same time, fix workers included. Upkeep ants
  and the ants of a saved workflow do not count.
- A worker ant never resets an existing branch: a fix round reuses the task's
  worktree and branch, so earlier work is never lost.
- Each run has its own id, and every branch is `ishikari/<run>/<task>`, so a new
  task never builds on an old task's branch.
- Ishikari keeps everything outside the repo, in its state folder
  `~/.ishikari/<repo>-<hash>/`: the logbook, the plans, the worktrees and the
  saved commands. The only copy inside the repo is the scripts, under `.git`.
  None of it is ever committed, and the repo's main checkout is touched only by the
  final fast-forward.
- Only Ishikari's tool,
  [`ishikari.py`](../scripts/ishikari.py), writes the logbook
  and the requirement entries. Each write holds a lock, so two runs never lose
  each other's entries. Requirement writes replace the file in one step, so a
  crash never leaves half a file; the logbook is only ever appended to. Lock files live in `~/.ishikari/locks`, never in the repo.
- Every workflow ant's reply is logged the moment it comes, in plan, build and
  finish, through a logbook clerk ant; a failed append never blocks or fails
  the run. The live investigator gets only the `investigated` entry
  `ishikari-plan` logs for it. Build and finish also append a summary at the
  end of the stage.
- Never trust an ant's answer shape. The scripts check every reply: a missing
  or broken field is an error, never a silent pass. A combined test counts only
  when every task is reported merged and a commit is given. Main counts as moved
  only when something was merged and the finisher says so. Branch names from
  earlier rounds must look like `ishikari/<run>/<task>`, since they go into git
  commands. In the fallback plan loop (no Agent tool), the investigator
  asking a question it already asked stops the run.
- Requirement writes keep the file's own line endings. A logbook entry with an
  unknown field, or without run, who or event, is refused, and a newline in a
  value never starts a new field.
- A dropped task's branch is kept, never deleted, so its work can be looked at
  later. Only merged tasks' branches and scratch branches are removed.
- Each ant thinks only as hard as its job needs: low for the logbook clerk,
  finisher and upkeep ants; medium for the investigator, researchers, add
  requirement ant, workers, inspectors and merger; high for the architect and
  the detective.

## Running Ishikari

A running workflow cannot stop to ask the user, so Ishikari is three workflows.
The main session asks the user only between the two plan runs, for the
investigator ant's questions; after that it drives everything on its own.

| Workflow          | Stages                      | Ends with            |
| ----------------- | --------------------------- | -------------------- |
| `ishikari-plan`   | review, requirement, design | plans to build       |
| `ishikari-build`  | build, check, fix, combined | tasks to merge       |
| `ishikari-finish` | merge, upkeep, main         | main moved, new bugs |

The scripts: [`ishikari-plan.js`](../scripts/ishikari-plan.js),
[`ishikari-build.js`](../scripts/ishikari-build.js) and
[`ishikari-finish.js`](../scripts/ishikari-finish.js).

The [`/ishikari`](../SKILL.md) command runs all four steps below
and stops to ask the user only in step 2.

1. Run `python3 scripts/ishikari.py setup <repo>`. It makes the state folder,
   starts the logbook if there is none, copies the three scripts into
   `<repo>/.git/ishikari/workflows/` where the Workflow tool may load them, and
   prints the run's `env`: repo, state folder, run id, main branch, tool path,
   script paths, and the repo's saved `testCommand` and `checkCommand`.
2. The live investigator asks its questions, then `ishikari-plan` writes the
   requirement, design and plans (see
   [Plan](../SKILL.md#2-plan)). The plans go straight to
   build. First `ishikari.py req add` writes the requirement (none for a
   refactor), the main
   session commits it. `ishikari.py config` saves the test and check commands.
3. Run `ishikari-build` with `env` and the plans. Every task
   `awaiting review` is approved without asking. Escalated, blocked and error
   tasks, and tasks built on them, are dropped and listed in the report.
4. Run `ishikari-finish` with `env`, the approved tasks, the build's `together`
   result (the combined test's) and any tasks to drop. One task with no `after`
   skips the trial merge: its inspector already tested it. After main moves, the finisher runs
   `checkCommand` to build and check the real app; a failed check comes back
   once as a `check-fix` task built from the moved main. Failed merges and
   waiting tasks come back in the next build as `bugs`. The
   janitor's cleanup is built and checked inside finish, with its own one fix
   round, and lands with the tasks; only a dropped cleanup's plan goes to the
   next plan stage, and that cleanup run gets no janitor. The judge's
   verdict (score, gaps, flagged) is in the result. Once the check passes,
   `ishikari.py req done` marks the run's requirements DONE. The skill's
   [Limits](../SKILL.md#limits) table is the source of truth
   for every loop cap.

## Diagram

Stages run left to right: plan, build, check, fix, finish. The scripts hand work
from ant to ant directly. The Logbook sits apart: a shared ledger, one plain
text recfile per repo, `~/.ishikari/<repo>-<hash>/logbook.rec`, outside the
repo. It is append only: nothing in it is ever changed or removed. In the
map's words: logbook clerk ant: appends each ant's entry the moment the ant
replies, in plan, build and finish. The live investigator gets only an
investigated entry. Build and finish add a summary at the end. No ant reads it.
Each entry says who, the task and what came of it (built, 2 bugs found, score
6, died); the clerk appends it while the run goes on, and a failed append never
blocks or fails the run. The live investigator runs outside any workflow, so
`ishikari-plan` logs one `investigated` entry for it, with the report path. The
summaries hold each task's status, each bug with its tries, the cleanup, the
judge's verdict and whether main moved. The cost: one small
clerk call per ant call. You add your own notes with `ishikari.py log note`; they are notes,
never orders. Read it with `ishikari.py log status` (each
task's latest event), `recsel` or any editor.

An animated metro map: four rows read left to right, and short transfer spurs
name where a cross-row link goes. Every agent label in the three scripts has a
station, helper ants included (verifier, the fast-forward merger, the cleanup
detective, the jurors), and short notes name each skipped step. Built by
[`metro.py`](metro.py); run `python3 metro.py` after a flow change.
`test_metro_map` in [`test_ishikari.py`](../tests/test_ishikari.py) checks it
against the scripts.

![Ishikari metro map](ishikari-metro.svg)
