---
name: retrospective-ant
metadata:
  scope: global
description: Look back on how a piece of work went - not the code, the way it was done - and report ranked findings, costliest first, each with evidence, its cost and the change to make. Read only. In normal use it reviews this chat session and answers in it. Run by Ishikari's retrospective ant it reviews a run's logbook, results and git history and writes the one report file the ant names. Use when the user says retro, retrospective, how did that go, what went wrong, lessons learned, or runs /retrospective-ant.
argument-hint: "[what to review, default this session]"
---

# Retrospective

Judge how the work was done, not the code it made.
Read only: write nothing, except the one report file Ishikari names.

## Which mode

- **Ishikari mode** only when your prompt says you are an ant of the Ishikari
  workflow and tells you to follow this skill's Ishikari mode. Then follow
  [Ishikari mode](#ishikari-mode) and the ant's prompt, and nothing else.
- **Normal mode** every other time: the user runs the skill, it triggers in a
  normal session, or another skill or agent calls it. Then follow
  [Normal mode](#normal-mode) and ignore everything Ishikari-only: no Ishikari
  spec or plan files, no JSON reply, no Ishikari paths, never wait for an ant's
  inputs.

## Look for

- Bugs and errors in the way of working: wrong steps, wrong order.
- Waste: repeated or needless calls, retries, loops, long detours.
- Failures: tools, agents or commands that died or were refused.
- Misleads: a prompt, rule or plan that sent the work the wrong way.
- Weak checks: a check that was missing or let a mistake through.
- Rules that did not fit the task, and missing steps.

## Findings

- Every finding needs evidence from this work; never guess.
- Each one: category, title, evidence, impact (what it cost: calls, rounds,
  time, a wrong result), the change to make, and where (file and rule).
- Ranked costliest first. Nothing to improve: say so.
- Category is one of: bug, waste, failure, mislead, weak-check, misfit, gap,
  improvement. Ishikari's ant uses its own list.

## Normal mode

1. Source: this chat session. A path or range given: that instead.
2. Read the session's work: the asks, the tool calls, what failed, what was
   redone, what the user corrected.
3. Reply in the session: a two or three line summary, then the findings.
   Where: the skill, rule or file that should change.

## Ishikari mode

Loaded by Ishikari's retrospective ant. Never ask. The ant names what to read
(logbook, plans, stage results, git history, Ishikari's source), the digest to
take before and after, the one file to write and the categories. Follow it and
reply only in its JSON.
