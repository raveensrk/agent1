# Index

Design documentation and design bible for Ishikari, a workflow where AI
agents ("ants") work in parallel to complete a task.

## Goal

Take any task from the user and finish it with many ants working in
parallel. The user is asked only at fixed gates: task review, requirement
approval, final review and escalation. Everything between runs on its own.

Ishikari is a higher-order workflow: it can take other workflows as
arguments and run them inside itself.

## Flow

1. **Task in.** The workflow receives a task. It can be anything.
2. **ARTA** (Ant-Review-Task-Agent) reviews and critiques the task, then asks
   the user for feedback with the `/ask-simple` skill.
3. **AARA** (Ant-Add-Requirement-Agent) runs once the task is approved. It
   writes a requirement with the `/add-requirement` skill, asks the user for
   feedback, and commits the requirement after approval.
4. **Plan.** AARA writes a plan for each ant worker in a temporary area.
   Workers cannot ask questions, so the plan must be complete and correct.
5. **AW** (Ant Worker) builds its plan in its own git worktree, in parallel
   with the other workers. It decides on its own and goes as far as it can.
   When done it posts its status to the bulletin board.
6. **Anti-monitor ant** starts with the workflow and watches the bulletin
   board. For each completed task it spawns an inspector.
7. **Inspector ant** inspects and reviews the completed task.
   - No bugs: marks the task complete on the bulletin board. It then waits
     for the user's final review.
   - Bugs: posts them to the bug bounty board.
8. **Detective ant** is spawned while the bug bounty board is non-zero. It
   debugs and finds the cause, but never writes code. It writes a fix plan
   and spawns an ant worker to build the fix. When the fix is built, it
   keeps the bounty status updated and hands the fix back to the same
   inspector for re-inspection. After 3 failed tries on a bug it escalates
   to the user.
9. **Merger ant** runs after the user approves a task on the bulletin
   board. It merges the worker's branch into main and sets the status to
   `done`. If the merge breaks main, it posts a bug to the bug bounty
   board, and the detective ant handles it like any other bug.

## Always-on ants

- **Janitor ant** cleans and maintains the codebase after each task is
  done.
- **Librarian ant** maintains the docs after each task is done.
- **Philosopher ant** questions and critiques ongoing work at any time. It
  only comments, in [`boards/critiques.md`](boards/critiques.md); it never
  pauses or blocks work.

## Rules

- All ants work in parallel without blocking each other.
- Only ARTA and AARA ask the user questions, plus the detective on
  escalation. Workers never ask.
- The boards are plain files every ant can read and write:
  [`boards/bulletin.md`](boards/bulletin.md),
  [`boards/bounty.md`](boards/bounty.md) and
  [`boards/critiques.md`](boards/critiques.md).
- Only ant workers write code or build. Every other ant reads, plans,
  reviews or posts to a board.
- At most 5 ant workers run at the same time, fix workers included.
- One workflow script, kept next to this file, starts and connects all
  the ants.

## Diagram

Stages run top to bottom: plan, build, check, fix, finish. Each board
sits in the stage that reads it. D2 source: [`ishikari.d2`](ishikari.d2),
rendered with the TALA layout:
`d2 --layout=tala ishikari.d2 ishikari.svg`.

```d2
direction: down

user: User (me) {shape: person; width: 80; height: 80}

plan: 1. Plan {
  left: 0
  top: 0
  direction: right
  task: Task {shape: oval}
  arta: ARTA\nAnt-Review-Task-Agent
  aara: AARA\nAnt-Add-Requirement-Agent
  plans: Worker plans\n(temporary area) {shape: page}
  task -> arta: review
  arta -> aara: approved
  aara -> plans: commit requirement,\nwrite plans
}

build: 2. Build {
  left: 0
  top: 700
  aw: Ant Workers (AW)\none worktree each, max 5 {style.multiple: true}
  bulletin: Bulletin board {shape: cylinder}
  aw -> bulletin: post "built"
}

check: 3. Check {
  left: 0
  top: 1500
  direction: right
  monitor: Anti-monitor ant
  inspector: Inspector ant
  monitor -> inspector: spawn per\ncompleted task
}

fix: 4. Fix {
  left: 0
  top: 1900
  direction: right
  bounty: Bug bounty board {shape: cylinder}
  detective: Detective ant\nplans fixes, writes no code
  bounty -> detective: spawn
}

finish: 5. Finish {
  left: 0
  top: 2400
  merger: Merger ant
}

always_on: Always-on ants {
  janitor: Janitor ant\ncleans code after each task
  librarian: Librarian ant\nupdates docs after each task
  philosopher: Philosopher ant\ncritiques, never blocks
  critiques: Critiques board {shape: cylinder}
  philosopher -> critiques: critique {style.stroke-dash: 3}
}

plan.arta <-> user: critique, /ask-simple
plan.aara <-> user: approve requirement
plan.plans -> build.aw: start in parallel
check.monitor -> build.bulletin: watch {style.stroke-dash: 3}
check.inspector -> build.bulletin: no bugs
check.inspector -> fix.bounty: bugs found
fix.detective -> build.aw: fix plan
fix.detective -> check.inspector: re-inspect
fix.detective -> user: escalate after 3 tries
build.bulletin -> user: final review
user -> finish.merger: approved
finish.merger -> build.bulletin: merge, set "done"
finish.merger -> fix.bounty: merge broke main
```

![Ishikari workflow](ishikari.svg)
