---
name: ux
metadata:
  scope: global
description: Plan or review a user interface - GUI (desktop or web), CLI or TUI - against the Laws of UX (https://lawsofux.com/) and the CLI Guidelines (https://clig.dev/). Plan mode interviews the user and writes a UX brief. Review mode reads the code, judges and critiques the UI, and reports ranked findings. Use when the user says plan the UI, plan the UX, review the UI, judge the UI, critique the UX, polish the UI, or runs /ux plan or /ux review. Reports only; never edits code.
argument-hint: "plan|review [path or area]"
---

# UX: plan or review a UI

Two modes, picked by the first argument:

- `plan` - help design the UI/UX before it is built.
- `review` (alias `judge`) - judge and critique the UI that exists.

No mode given: `review` if the target has UI code, `plan` otherwise. Say which
mode was picked in the first line.

This skill writes no code in either mode. To rebuild a desktop GUI from
scratch, use `redesign-gui` instead.

## Sources

- GUI and TUI: Laws of UX, https://lawsofux.com/ - Fitts, Hick, Jakob,
  Miller, Doherty threshold, Aesthetic-usability, Peak-end, Tesler,
  Von Restorff, proximity, similarity, common region, Postel, Zeigarnik.
- CLI: Command Line Interface Guidelines, https://clig.dev/ - help, output,
  errors, arguments and flags, interactivity, config, env vars, robustness,
  naming, future-proofing.
- The project's own rules (`rules/agent1.md`, section CLI, for CLIs in agent1) win over
  both.

Cite the exact law or guideline section on every finding and every plan choice.

## 1. Find the surface

- Name each UI surface in scope: GUI, CLI, TUI. Limit to the path argument.
- Read the README and requirements for who uses it and for what. Write the
  goal in one line. No goal written: ask one short question. Never guess.

## 2a. Plan mode

1. Interview: ask only what the code and docs do not answer - users, top 3
   tasks, platforms, input (mouse, keyboard-only, scripts), constraints.
   Ask in batches of at most 4 questions.
2. Write a brief, text only, no sketches:
   - Goal and users.
   - Top tasks, most frequent first, with the shortest path for each.
   - Per surface: structure (screens, or commands and flags), defaults,
     feedback and errors, help, keyboard, accessibility.
   - CLI: command names, flags, `--help`, `--json`, exit codes, stdout vs
     stderr, TTY detection, `NO_COLOR`, confirmation for destructive steps.
   - Each choice tagged with its law or guideline.
   - Open questions.
3. Show the brief. Write it to a file only when the user asks.

## 2b. Review mode

1. Read the UI code: views, layouts, styles, strings, help text, argument
   parsing, error paths, output formatting. Code only - do not launch the app.
2. Judge each surface against the sources. Look for:
   - Friction: steps, targets, choices beyond what the task needs.
   - Feedback: missing progress, silent failure, slow paths with no signal.
   - Consistency: names, spacing, colors, flags, verbs that differ for the
     same thing.
   - Errors: messages that do not say what went wrong and how to fix it.
   - CLI specifics: help, exit codes, stdout/stderr, machine output, TTY,
     color, destructive confirmation, signals.
   - Polish: alignment, copy, empty states, defaults.
3. The user may like the UI as it is. Flag only what earns a change. A clean
   surface gets "no findings", not invented nits.

## 3. Report (review mode)

Ranked worst first. Per finding:

- Severity: `high` (blocks or misleads), `medium` (friction), `low` (polish).
- Where: `path:line`.
- What is wrong, in one line.
- Rule broken: law or clig.dev section.
- Fix: the smallest change that solves it.

End with a one-line verdict per surface and what is already good. Stop there:
no edits, no offer to apply.
