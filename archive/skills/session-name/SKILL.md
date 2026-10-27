---
name: session-name
description: Name the current Pi session from its goal - a short lowercase label, 4 words, max 32 characters. Use when the user says name this session, rename this session, session name, suggest a session name, or asks to name this session.
---

# Session name

The Pi extension owns the picker. This skill does not invent a name and does not call `/name`.

## 1. Stop if this is not Pi

If the `session_name` tool and `/session-name` are both missing, say this skill runs on Pi only and stop. Other harnesses are not wired yet.

## 2. Open the picker

Call the `session_name` tool only when the user is asking to name this session.

Do not call it when session names are part of another task. `put the session name on the left` is a task, not a naming request. `can you name this session` is a naming request.

If you cannot call the tool, tell the user to run `/session-name`.

Do not propose names. Do not call `/name`.

## 3. What gets stored

The picker shows 3 different wordings of the current goal, plus `Keep current` (or `Leave unnamed`), plus `Type my own`. Nothing is stored until the user chooses.

A stored name is lowercase words, spaces, no punctuation, max 4 words, max 32 characters. Overflow is rejected, not clipped.

Example:

- User: `fix the login bug`
- Chosen: `fix login bug`
- `/session` shows `Name: fix login bug`

## 4. Verify

Run `/session`. The Name line is the chosen label, or absent if the user left it unnamed.

The powerline shows that label leftmost on the main bar, and hides the slot while unnamed.
