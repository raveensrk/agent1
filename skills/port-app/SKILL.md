---
name: port-app
metadata:
  scope: global
description: Plan a port of an existing app to a new language or UI toolkit by asking the user very simple, clear questions, one decision each, then writing the port plan. Use when the user says port this app, move it off a language or toolkit, rewrite it in another stack, or runs /port-app. Asks before it writes; changes no code until the plan is approved.
argument-hint: "[target, e.g. tauri]"
---

# Port an app

Find out what the user wants with questions they can answer at a glance.
Then write the plan. Write no code until the plan is approved.

## 1. Look first

Read before asking, so no question asks what the repo already says:

- The repo's `AGENTS.md` or `CLAUDE.md`, and its requirements file.
- Every agent1 requirement the port touches, such as
  [agent1.md](../../rules/agent1.md) sections GUI and Architecture.
- What exists: languages, line counts, apps, CLI, data format, tests, hooks.
- Earlier attempts at a port, such as a sibling repo.

## 2. Ask simple questions

Every question follows these rules:

- One decision per question. Never two in one.
- One short sentence, in plain words. No jargon the user did not use first.
- It stands alone: it names the thing it asks about.
- Two to four answers, each a few words, plus a one-line why.
- The recommended answer comes first, marked `(Recommended)`.
- Yes or no when that is enough.
- Ask at most four at once. Ask the next round once those are answered.
- Never ask what the user already answered, in this session or in an
  argument such as `/port-app tauri`.

Use the harness's question tool when it has one (Claude Code:
`AskUserQuestion`). Otherwise print numbered questions with lettered answers,
so the reply can be `1a 2b`.

Cover these, skipping any the repo or the user already settled:

1. Target: which language or toolkit for the UI?
2. Scope: port everything, or the UI only?
3. Core language: which language for the core and the CLI?
4. Place: the same repo, or a new one?
5. Rules: if agent1's rules name another stack, waive them for this repo, or
   change them for every app?
6. Old code: remove it at the end, or keep it?
7. Pace: stop after each step for a look, or run to the end?

## 3. Write the plan

Once every answer is in, reply with:

- The answers, one line each.
- What does not change, such as the data format.
- The steps, in order. Each ends in something the user can check.
- Each requirement to add or edit, drafted, waiting for `:APPROVED:`.
- Risks, each in one line, with what the plan does about it.

Then ask one yes-or-no question: start step 1?

## Rules

- Change no file until the user says yes to the plan.
- The old app's behavior is the spec. Port tests first, so both versions can
  be checked against the same data.
- Removing the old code is its own step, with its own confirmation.
