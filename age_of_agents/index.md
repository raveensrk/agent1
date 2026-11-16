# Index

Design documentation and design bible for Ishikari, a workflow where AI
agents ("ants") work in parallel to complete a task.

## Goal

Take any task from the user and finish it with many ants working in
parallel. The user is asked only at fixed gates: task review, requirement
approval, final review and escalation. Everything between runs on its own.

Ishikari is a higher-order workflow: it can take other workflows as
arguments and run them inside itself. A workflow given this way becomes an
worker ant's job: the worker runs it as its plan.

## Flow

1. **Task in.** The workflow receives a task. It can be anything.

2. **Task Review Ant** reviews and critiques the task, then asks
   the user for feedback with the `/ask-simple` skill. It also reads the
   critiques board: each critique that matters for this task becomes one
   question for the user. Once the user answers, the add requirement ant
   removes that critique from the board, so no question is asked twice.

3. **Add Requirement Ant** runs once the task is approved. It
   writes a requirement with the `/add-requirement` skill, asks the user for
   feedback, and commits the requirement after approval.

4. **Plan.** The add requirement ant writes a plan for each worker ant in
   a temporary area. Workers cannot ask questions, so the plan must be
   complete and correct. A plan that edits files another plan creates lists
   that plan in `after`; it waits for it and builds on its branch.

5. **Worker Ant** builds its plan in its own git worktree, in parallel
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
   and a worker ant builds the fix. When the worker has built it, the build
   script sends the branch back to the same task's inspector, and the bounty
   status is updated. After 3 failed tries on a bug it escalates to the user.
   Each new round sees every earlier round's cause, fix plan and outcome, so
   the detective never repeats an idea that failed.

9. **Merger ant** runs after the user approves a task on the bulletin
   board. It merges the worker's branch into main and sets the status to
   `done`. If the merge breaks main, it posts a bug to the bug bounty
   board, and the detective ant handles it like any other bug. One merger
   ant merges every approved task in order, then removes each merged task's
   worktree and branch.

## Upkeep ants

- **Janitor ant** finds mess in the codebase after each task is done. It
  writes a cleanup plan, which goes into the next build run for a worker ant.
- **Librarian ant** updates the docs after the merge.
- **Philosopher ant** questions and critiques all the merged work together,
  once per run. It only comments, in
  [`boards/critiques.md`](boards/critiques.md), and never blocks. On the
  next task, the task review ant turns the critiques that matter into
  questions for the user.

## Rules

- All ants work in parallel without blocking each other.
- Only the task review ant and the add requirement ant ask the user
  questions, plus the detective on escalation. Workers never ask.
- The boards are plain files every ant can read and write:
  [`boards/bulletin.md`](boards/bulletin.md),
  [`boards/bounty.md`](boards/bounty.md) and
  [`boards/critiques.md`](boards/critiques.md).
- Only worker ants write code or build. Every other ant reads, plans,
  reviews or posts to a board.
- At most 5 worker ants run at the same time, fix workers included.
  Upkeep ants do not count toward this limit.
- Only the workflow script writes the boards. It keeps their rows while a
  stage runs and writes them once when the stage ends, so no task ever waits
  on a board and no update is lost.
- One workflow script, kept next to this file, starts and connects all
  the ants.

## Running Ishikari

A running workflow cannot stop to ask the user, so Ishikari is three
workflows. The user answers between them, at the same points the flow above
asks.

| Workflow                                          | Stages            | Ends with                   |
| ------------------------------------------------- | ----------------- | --------------------------- |
| [`ishikari-plan`](workflows/ishikari-plan.js)     | Plan              | review, requirement, plans  |
| [`ishikari-build`](workflows/ishikari-build.js)   | Build, Check, Fix | tasks for final review      |
| [`ishikari-finish`](workflows/ishikari-finish.js) | Finish, upkeep    | merges, new bugs, critiques |

1. Run `ishikari-plan` with the task. If the review has questions, ask them
   with `/ask-simple` and run it again with the answers. Then the user
   approves the requirement and the plans, and the main session commits the
   requirement.
2. Run `ishikari-build` with the approved plans. The user does the final
   review and handles any escalated tasks.
3. Run `ishikari-finish` with the approved tasks. Bugs from a broken merge go
   into the next `ishikari-build` run.

The anti-monitor ant is the build script itself: when a worker ant finishes,
the script starts that task's inspector ant at once. The script also keeps
the boards and the 5-worker limit.

## Diagram

Stages run left to right: plan, build, check, fix, finish. Each board
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

direction: right

user: User (me) {
  shape: person
  width: 80
  height: 80
  style: {fill: "#FDE68A"; stroke: "#B45309"; font-color: ${text}}
}

plan: 1. Plan {
  left: 0
  top: 0
  direction: down
  style: {fill: ${plan-fill}; stroke: ${plan-line}; font-color: ${plan-line}; stroke-width: 2}
  task: Task {shape: oval; class: node; style.stroke: ${plan-line}}
  arta: Task Review Ant {class: node; style.stroke: ${plan-line}}
  aara: Add Requirement Ant {class: node; style.stroke: ${plan-line}}
  plans: Worker plans\n(temporary area) {shape: page; class: node; style.stroke: ${plan-line}}
  task -> arta: review {class: flow}
  arta -> aara: approved {class: ok}
  aara -> plans: commit requirement,\nwrite plans {class: flow}
}

build: 2. Build {
  left: 560
  top: 0
  style: {fill: ${build-fill}; stroke: ${build-line}; font-color: ${build-line}; stroke-width: 2}
  aw: Worker Ants\none worktree each, max 5 {style.multiple: true; class: node; style.stroke: ${build-line}}
  bulletin: Bulletin board {shape: cylinder; class: node; style.stroke: ${build-line}}
  aw -> bulletin: post "built" {class: flow}
}

check: 3. Check {
  left: 1440
  top: 0
  direction: down
  style: {fill: ${check-fill}; stroke: ${check-line}; font-color: ${check-line}; stroke-width: 2}
  monitor: Anti-monitor ant\n(the build script) {class: node; style.stroke: ${check-line}}
  inspector: Inspector ant {class: node; style.stroke: ${check-line}}
  monitor -> inspector: spawn per built\ntask or fix {class: flow}
}

fix: 4. Fix {
  left: 2100
  top: 0
  direction: down
  style: {fill: ${fix-fill}; stroke: ${fix-line}; font-color: ${fix-line}; stroke-width: 2}
  bounty: Bug bounty board {shape: cylinder; class: node; style.stroke: ${fix-line}}
  detective: Detective ant\nplans fixes, writes no code {class: node; style.stroke: ${fix-line}}
  bounty -> detective: spawn {class: bug}
}

finish: 5. Finish {
  left: 2700
  top: 0
  style: {fill: ${finish-fill}; stroke: ${finish-line}; font-color: ${finish-line}; stroke-width: 2}
  merger: Merger ant\nmerges all in order,\ncleans up {class: node; style.stroke: ${finish-line}}
}

always_on: Upkeep ants (after merge) {
  left: 1700
  top: 700
  style: {fill: ${always-fill}; stroke: ${always-line}; font-color: ${always-line}; stroke-width: 2}
  janitor: Janitor ant\nwrites a cleanup plan {class: node; style.stroke: ${always-line}}
  librarian: Librarian ant\nupdates docs {class: node; style.stroke: ${always-line}}
  philosopher: Philosopher ant\ncritiques all merged work {class: node; style.stroke: ${always-line}}
  philosopher -> critiques: critique {class: flow; style.stroke-dash: 3}
  critiques: Critiques board {shape: cylinder; class: node; style.stroke: ${always-line}}
}

plan.arta <-> user: critique, /ask-simple {class: flow}
plan.aara <-> user: approve requirement {class: ok}
plan.plans -> build.aw: start in parallel {class: flow}
check.monitor -> build.bulletin: watch, writes\nboards once per stage {class: flow; style.stroke-dash: 3}
check.inspector -> build.bulletin: no bugs {class: ok}
check.inspector -> fix.bounty: bugs found {class: bug}
fix.detective -> build.aw: fix plan {class: flow}
build.aw -> check.monitor: fix built,\nre-inspect {class: flow}
fix.detective -> user: escalate after 3 tries {class: bug}
build.bulletin -> user: final review {class: ok}
build.aw -> fix.bounty: stuck {class: bug}
user -> finish.merger: approved {class: ok}
finish.merger -> build.bulletin: merge, set "done" {class: ok}
finish.merger -> fix.bounty: merge broke main {class: bug}
finish.merger -> always_on: then {class: flow}
always_on.janitor -> plan.plans: cleanup plan for\nnext build {class: flow; style.stroke-dash: 3}

legend: Legend {
  left: 2700
  top: 700
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
always_on.critiques -> plan.arta: turned into questions\nfor the next task {class: flow; style.stroke-dash: 3}
```

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="ishikari-dark.svg">
  <img alt="Ishikari workflow" src="ishikari.svg">
</picture>

Animated version, one stage every 6 seconds:
[`ishikari-animated.svg`](ishikari-animated.svg), from
[`ishikari-animated.d2`](ishikari-animated.d2).

Car tour, one task driven slowly along the exact path it takes:
[`ishikari-flow.svg`](ishikari-flow.svg), built by [`flow.py`](flow.py).
Open it in a browser; it needs its script to run. It drives two routes: a
bug fixed on the first try, and a stuck worker escalated after 3 tries. The
−, pause and + buttons, or the keys `+`, `-` and space, change speed live.
Click a block to see only its arrows and the blocks they join; click it
again, click empty space or press Esc to go back to the tour.
