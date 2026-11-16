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
   debugs and fixes, keeps the bounty status updated, and hands each fix
   back to the same inspector for re-inspection. After 3 failed tries on a
   bug it escalates to the user.

## Always-on ants

- **Janitor ant** cleans and maintains the codebase.
- **Librarian ant** maintains the docs.
- **Philosopher ant** questions and critiques ongoing work at any time. It
  only comments; it never pauses or blocks work.

## Rules

- All ants work in parallel without blocking each other.
- Only ARTA and AARA ask the user questions, plus the detective on
  escalation. Workers never ask.
- The boards are plain files every ant can read and write:
  [`boards/bulletin.md`](boards/bulletin.md) and
  [`boards/bounty.md`](boards/bounty.md).
- At most 5 ant workers run at the same time.

## Diagram

D2 source: [`ishikari.d2`](ishikari.d2), rendered with the TALA layout:
`d2 --layout=tala ishikari.d2 ishikari.svg`.

```d2
direction: down

task: Task {shape: oval}
user: User (me) {shape: person}

arta: ARTA\nAnt-Review-Task-Agent
aara: AARA\nAnt-Add-Requirement-Agent
plan: Worker plans\n(temporary area) {shape: page}
aw: Ant Workers (AW)\none worktree each {style.multiple: true}

bulletin: Bulletin board {shape: cylinder}
bounty: Bug bounty board {shape: cylinder}

monitor: Anti-monitor ant
inspector: Inspector ant
detective: Detective ant

always_on: Always-on ants {
  janitor: Janitor ant\ncleans the codebase
  librarian: Librarian ant\nmaintains the docs
  philosopher: Philosopher ant\ncritiques, never blocks
}

task -> arta: review
arta <-> user: critique, /ask-simple
arta -> aara: approved
aara <-> user: requirement, /add-requirement
aara -> plan: commit requirement, write plans
plan -> aw: start in parallel
aw -> bulletin: post "built"
monitor -> bulletin: watch {style.stroke-dash: 3}
monitor -> inspector: spawn per completed task
inspector -> bulletin: no bugs: "awaiting review"
inspector -> bounty: bugs found
bounty -> detective: spawn when non-zero
detective -> inspector: fixed, re-inspect
detective -> bounty: update status
detective -> user: escalate after 3 failed tries
bulletin -> user: final review
always_on.philosopher -> bulletin: critique {style.stroke-dash: 3}
```

![Ishikari workflow](ishikari.svg)
