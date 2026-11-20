---
name: judge-ant
metadata:
  scope: global
description: Score code 0-10 against a spec of behaviours and invariants, id by id, and list each gap as a concrete fix and each real bug apart. Read only - never changes anything. Run by hand it scores the current branch against a spec file or task text and answers in the session. Run by Ishikari's judge or juror ant it scores a whole run or one task and replies in the ant's JSON. Use when the user says judge this, score this branch, does this meet the spec, or runs /judge-ant.
argument-hint: "[spec file or task text]"
---

# Judge

Score what the code does against what the spec says it must do.
Never change anything.

## What is scored

- **Behaviours** (`B1`, `B2`...): does the code behave as each one says?
- **Invariants** (`I1`, `I2`...): does each one hold?
- Behaviour the code adds that the spec does not have counts against it.
- How it was built is not scored: tech specs, plans and style are not the spec.

A spec with no ids (a task or issue text): split it into behaviours and
invariants first, number them, and show that list with the score.

## Score

- 0 to 10, one number for the whole scope.
- 10: every behaviour delivered, every invariant holds, nothing extra added.
- It is a judgement, never an average of the ids.

## Gaps and bugs

- **Gap**: anything short of 10. Write each as a short, concrete fix a worker
  can build without questions: the id, what is missing or wrong, and the file.
- **Bug**: a gap where the code itself behaves wrongly. Repeat it word for word
  in bugs. A missing or weak test is a gap, never a bug.

## Scope

- **Whole**: every id in the spec, across all the code. Check how the parts fit.
- **One task**: only the ids that task covers. With reports from several
  one-task judges, weigh them, check how the tasks fit, then decide the whole
  score yourself. A task with no report: judge it yourself.

## Run by hand

1. Spec: the file or task text given; none given, ask for it.
2. Code: the current branch, against `main`.
3. Reply in the session: the score, a table of each id with holds or fails and
   why, then the gaps and the bugs.

## Ishikari mode

Loaded by Ishikari's judge ant (whole scope) or a juror ant (one task). Never
ask. The ant names the spec, the code folder and the task; reply only in its
JSON: `score`, `gaps`, and `bugs` for the judge.
