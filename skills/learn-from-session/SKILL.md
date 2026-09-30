---
name: learn-from-session
description: Review the current Pi session as a coach - find patterns, errors, inefficiencies, gotchas, and improvements, research better approaches online, interview the user until the goal is clear, write a prioritized report, and merge durable rules into an AGENTS.md. Use when the user asks to learn from this session, review how the session went, improve the workflow, or update AGENTS.md. Asks before writing and shows diffs.
argument-hint: "[path to AGENTS.md]"
---

# Learn from session

A session review that trains future sessions. Read the transcript, interview
the user, research better approaches, rank findings by impact, write a report,
and merge the durable rules into an `AGENTS.md`. Nothing is written without
approval.

## 1. Read the transcript

Dump the current session (reads `$PI_SESSION_FILE`, else the newest jsonl for
cwd):

```
python3 scripts/session_text.py
```

It prints `[user]`, `[assistant]` and `[tool name]` lines. Read the whole
output. `--path FILE` reads a different transcript.

## 2. Interview, phase one - the goal

Ask questions until all four are clear: the goal of the session, what success
looked like, the constraints, and how the user wants the assistant to work.
One question at a time. Stop when the transcript plus answers leave no
ambiguity about what this session was supposed to achieve.

## 3. Analyze

Read the transcript for:

- Patterns: repeated mistakes, repeated user corrections, repeated phrasing.
- What failed: each failure, the root cause, and why it failed.
- What passed: each success, and why it worked, so it can be repeated.
- Inefficiencies: wasted steps, slow commands, redundant reads, retries.
- Gotchas: non-obvious environment, tool, or format traps.
- Conversation: unclear questions, buried answers, wrong assumptions, missing
  confirmation before risky steps.
- Dev flow: manual steps that could be scripted, missing defaults, bad aliases.
- Repetition: command sequences or manual steps that one small helper script
  would remove. Propose the script with its location, not just the idea.

Rank every finding by impact: time lost, error frequency, quality or speed
gain. Impact decides the order of the report.

## 4. Research

Proactively search when a better approach is suspected, even if the session
succeeded. Prefer official docs. Verify the suggestion applies to the installed
versions before proposing it, and cite the source link.

## 5. Report

Always write the report to `~/tmp/`. If the user declines a report, keep the
findings in chat and skip the file.

File: `~/tmp/session_review_<YYYY-MM-DD>.md`, appending `_2`, `_3` when taken. A
prioritized list, highest impact first, one line per finding:

```
- [high] <finding> - evidence: <quote or line from transcript> - fix: <action> - source: <link>
```

Include what worked, not only what failed. End with `Open questions` for
anything only the user can answer.

## 6. Interview, phase two - improvements

Ask about each proposed improvement before writing it anywhere: keep, drop, or
change. One question at a time. Keep only what the user confirms.

## 7. Pick the AGENTS.md target

If the user passed a path, use it. Otherwise list candidates and ask:

1. `AGENTS.md` in cwd, if it exists.
2. Every `AGENTS.md` from cwd up to `git rev-parse --show-toplevel` (or `/`).
3. `~/.pi/agent/AGENTS.md`.

Show each candidate with a one-line summary of what it already covers. Read
the chosen file fully before editing.

## 8. Merge

- Fit each durable rule into an existing section. Match the file's voice,
  heading depth, and punctuation. Plain hyphens only.
- Create a new section only when no existing section fits. Name it after the
  topic, not the session.
- Add or minimally amend. Never reword, reorder, or delete existing content.
- Durable rules only: corrections, conventions, commands, gotchas. Task-specific
  suggestions stay in the report.
- If the session produced no durable rules, say so and write nothing.

## 9. Approve, then write

Show a unified diff of the proposed edits (`diff -u` against a copy, or stage
and use `git diff`). Wait for an explicit yes. On approval, apply the edits,
re-read the changed sections, and report what changed with line numbers.
