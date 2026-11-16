# Index

Design documentation and design bible for Ishikari, a workflow where AI
agents ("ants") work in parallel to complete a task.

## Goal

Take any task from the user and finish it with many ants working in
parallel. The user is asked only at fixed gates: task review, requirement
approval, final review and escalation. Everything between runs on its own.

Ishikari is a higher-order workflow: it can take other workflows as
arguments and run them inside itself. A workflow given this way becomes an
ant worker's job: the worker runs it as its plan.

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
   When done it posts its status to the bulletin board. A worker that gets
   stuck posts a bug to the bug bounty board, and the detective plans the
   rest.
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
  Always-on ants do not count toward this limit.
- Ants take turns writing a board: one ant holds the board's lock while it
  writes, and others wait until it lets go. No update is lost.
- One workflow script, kept next to this file, starts and connects all
  the ants.

## Diagram

Stages run top to bottom: plan, build, check, fix, finish. Each board
sits in the stage that first writes to it.
D2 source: [`ishikari.d2`](ishikari.d2), rendered with the TALA
layout by [`render.sh`](render.sh) to a light and a dark SVG.

Colors: each stage has its own color. Green arrows are approvals, red
arrows are bugs, gray arrows are normal flow. Dashed arrows only watch or
comment. The legend in the diagram shows the arrow colors.

```d2
# Colors live in vars. render.sh swaps them for the dark version.
vars: {
  plan-fill: "#DBEAFE"
  plan-line: "#2563EB"
  build-fill: "#DCFCE7"
  build-line: "#16A34A"
  check-fill: "#FEF3C7"
  check-line: "#D97706"
  fix-fill: "#FFE4E6"
  fix-line: "#E11D48"
  finish-fill: "#EDE9FE"
  finish-line: "#7C3AED"
  always-fill: "#F1F5F9"
  always-line: "#64748B"
  node-fill: "#FFFFFF"
  text: "#0F172A"
  bug: "#DC2626"
  ok: "#16A34A"
  flow: "#475569"
}

classes: {
  node: {style: {fill: ${node-fill}; font-color: ${text}; stroke-width: 2}}
  bug: {style: {stroke: ${bug}; font-color: ${bug}; stroke-width: 2}}
  ok: {style: {stroke: ${ok}; font-color: ${ok}; stroke-width: 2}}
  flow: {style: {stroke: ${flow}; font-color: ${flow}}}
}

direction: down

user: User (me) {
  shape: person
  width: 80
  height: 80
  style: {fill: "#FDE68A"; stroke: "#B45309"; font-color: ${text}}
}

plan: 1. Plan {
  left: 0
  top: 0
  direction: right
  style: {fill: ${plan-fill}; stroke: ${plan-line}; font-color: ${plan-line}; stroke-width: 2}
  task: Task {shape: oval; class: node; style.stroke: ${plan-line}}
  arta: ARTA\nAnt-Review-Task-Agent {class: node; style.stroke: ${plan-line}}
  aara: AARA\nAnt-Add-Requirement-Agent {class: node; style.stroke: ${plan-line}}
  plans: Worker plans\n(temporary area) {shape: page; class: node; style.stroke: ${plan-line}}
  task -> arta: review {class: flow}
  arta -> aara: approved {class: ok}
  aara -> plans: commit requirement,\nwrite plans {class: flow}
}

build: 2. Build {
  left: 0
  top: 560
  style: {fill: ${build-fill}; stroke: ${build-line}; font-color: ${build-line}; stroke-width: 2}
  aw: Ant Workers (AW)\none worktree each, max 5 {style.multiple: true; class: node; style.stroke: ${build-line}}
  bulletin: Bulletin board {shape: cylinder; class: node; style.stroke: ${build-line}}
  aw -> bulletin: post "built" {class: flow}
}

check: 3. Check {
  left: 0
  top: 1060
  direction: right
  style: {fill: ${check-fill}; stroke: ${check-line}; font-color: ${check-line}; stroke-width: 2}
  monitor: Anti-monitor ant {class: node; style.stroke: ${check-line}}
  inspector: Inspector ant {class: node; style.stroke: ${check-line}}
  monitor -> inspector: spawn per\ncompleted task {class: flow}
}

fix: 4. Fix {
  left: 0
  top: 1320
  direction: right
  style: {fill: ${fix-fill}; stroke: ${fix-line}; font-color: ${fix-line}; stroke-width: 2}
  bounty: Bug bounty board {shape: cylinder; class: node; style.stroke: ${fix-line}}
  detective: Detective ant\nplans fixes, writes no code {class: node; style.stroke: ${fix-line}}
  bounty -> detective: spawn {class: bug}
}

finish: 5. Finish {
  left: 0
  top: 1660
  style: {fill: ${finish-fill}; stroke: ${finish-line}; font-color: ${finish-line}; stroke-width: 2}
  merger: Merger ant {class: node; style.stroke: ${finish-line}}
}

always_on: Always-on ants {
  style: {fill: ${always-fill}; stroke: ${always-line}; font-color: ${always-line}; stroke-width: 2}
  janitor: Janitor ant\ncleans code after each task {class: node; style.stroke: ${always-line}}
  librarian: Librarian ant\nupdates docs after each task {class: node; style.stroke: ${always-line}}
  philosopher: Philosopher ant\ncritiques, never blocks {class: node; style.stroke: ${always-line}}
  critiques: Critiques board {shape: cylinder; class: node; style.stroke: ${always-line}}
  philosopher -> critiques: critique {class: flow; style.stroke-dash: 3}
}

plan.arta <-> user: critique, /ask-simple {class: flow}
plan.aara <-> user: approve requirement {class: ok}
plan.plans -> build.aw: start in parallel {class: flow}
check.monitor -> build.bulletin: watch {class: flow; style.stroke-dash: 3}
check.inspector -> build.bulletin: no bugs {class: ok}
check.inspector -> fix.bounty: bugs found {class: bug}
fix.detective -> build.aw: fix plan {class: flow}
fix.detective -> check.inspector: re-inspect {class: flow}
fix.detective -> user: escalate after 3 tries {class: bug}
build.bulletin -> user: final review {class: ok}
build.aw -> fix.bounty: stuck {class: bug}
user -> finish.merger: approved {class: ok}
finish.merger -> build.bulletin: merge, set "done" {class: ok}
finish.merger -> fix.bounty: merge broke main {class: bug}

legend: Legend {
  left: 1000
  top: 760
  grid-columns: 1
  grid-gap: 0
  style: {fill: ${always-fill}; stroke: ${always-line}; font-color: ${always-line}; stroke-width: 2}
  r1: "" {
    direction: right
    style: {fill: transparent; stroke: transparent}
    s: "" {shape: circle; width: 12; height: 12; style: {fill: ${ok}; stroke: ${ok}}}
    t: approval {shape: text; style.font-color: ${text}}
    s -> t {class: ok}
  }
  r2: "" {
    direction: right
    style: {fill: transparent; stroke: transparent}
    s: "" {shape: circle; width: 12; height: 12; style: {fill: ${bug}; stroke: ${bug}}}
    t: bug {shape: text; style.font-color: ${text}}
    s -> t {class: bug}
  }
  r3: "" {
    direction: right
    style: {fill: transparent; stroke: transparent}
    s: "" {shape: circle; width: 12; height: 12; style: {fill: ${flow}; stroke: ${flow}}}
    t: normal flow {shape: text; style.font-color: ${text}}
    s -> t {class: flow}
  }
  r4: "" {
    direction: right
    style: {fill: transparent; stroke: transparent}
    s: "" {shape: circle; width: 12; height: 12; style: {fill: ${flow}; stroke: ${flow}}}
    t: watch or comment {shape: text; style.font-color: ${text}}
    s -> t {class: flow; style.stroke-dash: 3}
  }
}
```

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="ishikari-dark.svg">
  <img alt="Ishikari workflow" src="ishikari.svg">
</picture>
