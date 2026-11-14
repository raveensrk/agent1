---
name: next
metadata:
  scope: global
description: After a task ends, ask "What next?" about this session's work, list up to 5 next steps best first, each with why and size, let the user pick one in a question dialog, then do it. Use when the user says what next, what now, what is left, any follow-ups, or runs /next.
---

# What next?

Run only when the user types `/next`. Never on your own.

## 1. Look

- Source is this session only: the conversation and the work done in it.
- Read-only checks are fine: `git status`, `git diff`, quick file reads.
- Write nothing, run nothing that changes state.

## 2. Find items

Count these kinds, nothing else:

1. Unfinished - left half done, skipped, or not verified.
2. Risk - bug, edge case, missing test the work exposed.
3. Follow-up - natural next work the task turned up.
4. Ship - commit, push, open PR, update docs.

No fresh ideas unrelated to this session's work.

## 3. Rank

- Unfinished first, then risk, follow-up, ship.
- Inside a kind, most useful first.
- Up to 5 items. Fewer if fewer are real. Never pad.

## 4. Show

If nothing is left, say one line: `Nothing next - task complete.` Stop.

Otherwise ask with the question tool (Claude Code: `AskUserQuestion`).
Each option:

- label: one-line action, imperative.
- description: why it matters, then size - `small`, `medium` or `large`.

The tool holds 4 options. With 5 items, print the fifth above the dialog; the
user picks it through "Other".

## 5. Do

- Do the picked item in this session.
- When done, stop. Do not offer another list; the user runs `/next` again.
- A pick that changes something outside the repo (push, post, send) still
  follows the usual confirm rules.
