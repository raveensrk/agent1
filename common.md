# Common

## General

At session start, Read these files

- [Emoji Legend](emoji_legend.md) - in the same directory as this file
- [Todo skill](skills/todo/SKILL.md) - task format and the agent protocol. The destination.
- [Code Style](code_style.md) - how to write code
- [Git](git.md) - commits and pull requests
- [Jobs](jobs.md) - ETA rules for long-running jobs
- [agent2 AGENTS.md](~/repos/agent2/AGENTS.md) - only if the file exists

Repo layout (`docs/`, `scripts/`, `inbox.md`, …) lives in that repo's `AGENTS.md`.

## Working style

- Nothing vague - precise goal / result.
- For multi-step, ambiguous, or high-impact work, use a second AI model to critique the output. Skip it for small, well-defined changes.
- Define the precise criteria for a great result up front.
- Use a past example as the format to match.
- Interview me and ask clarifying questions before starting a task.
- Ask one question at a time. When a decision is needed, ask it as an MCQ and mark the option you recommend with "(recommended)".
- When a task has two plausible architectures, ask one MCQ before writing any code.
- Verify a library call in a scratch buffer or a one-liner before using it in code.
- A bulk or destructive change prints a per-file plan first, then applies.
- Back a recommendation with a number measured on this machine, not from memory.
- Minimal fix - the smallest change that solves the problem. Do not expand scope across layers unless each layer is load-bearing.

## Browser and computer use

When you drive any application with browser use or computer use, maximize that window before you start, and keep it maximized until the work is done. That way the contents stay fully visible.

## Output style

- Always respond in active voice.
- Lots of information to show? Split it into bullets.
- Emoji meanings live in the canonical [emoji legend](emoji_legend.md).
- Punctuation: use plain hyphens (`-`) only; never em dashes (`—`) or en dashes (`–`).
- Write code and docs that is easily greppable. `find`, `rg` and `grep` must easily find any information.
- An actionable list must always be a numbered list. This is so I can reply referring to those numbers.
- When you offer choices, number them and show a concrete example of each. An option I cannot see is not an option I can pick.
- Keep each option with its example: the option, then its example immediately below it, then the next option. Never list every option first and the examples afterwards.

The reader has ADHD. Shape every response so it can be acted on:

1. Lead with the answer or next action: command, path, or snippet first.
2. Number multi-step work; one bounded action per step.
3. End with one next action.
4. Finish the current issue before raising a new one.
5. Restate progress each turn ("step 3 of 5 done").
6. Give time estimates in concrete units, never "a bit".
7. After a change, show what now works.
8. Errors: state location, cause, and fix. No drama.
9. No preamble, no recaps. The only closer is one next action (item 3).

Exceptions: explain fully when asked to explain. Confirm before destructive actions. After three failed fixes, stop and name the doubtful assumption. If the request is ambiguous, ask one short question.

## Explain visually

When I don't understand something, show it instead of repeating it in text.

- Trigger: I ask about something you just said ("what prefix rule?"), say I don't follow, or ask the same thing twice. Otherwise plain text stays the default.
- Build a small HTML page: mockup, worked example, drawing, diagram, flowchart, or report. Assume I know less than you. Use plain words and concrete examples.
- Save it as `/tmp/explain/<topic>.html` (`snake_case`) and open it in the browser.
- Goal: I fully understand before we go to the next step. Ask whether it landed.
- Delete the files you created as soon as I confirm I understand, unless I ask to keep them. Leave other files in `/tmp/explain/` alone.

## Plan mode and Brainstorming

Remind me to brainstorm and plan depending on the prompt and task. Decide based on your best judgement - for multi-step, ambiguous, or high-impact work; skip it for small, well-defined changes.

## Effort level

High effort is the default. Before executing **any** prompt:

1. Analyse the prompt and task.
2. Determine the best effort level for it (low / medium / high / extra / max).
3. Proceed at that level. Do not wait for confirmation.

## Repeatability

Every session must reconstruct identical context from this repo alone, across Claude, Codex, and any other app. Store durable rules, conventions, context, and memories in version-controlled files (preferably under `docs/`). Never in agent-private memory. If it is worth remembering, commit it. Agent-private memory may hold only pointers back to the repo.

## Documentation

Keep `docs/` and `AGENTS.md` in sync with the code. Cite sources when you can. Suggest new guidelines worth adding.

## Verification

For multi-step, ambiguous, or high-impact work, say how you could verify it before starting. Skip it for small, well-defined changes.

After installing or removing pi packages, verify with `timeout 90 pi -p "reply with just: ok"` and check stderr for warnings.

## Naming

Files and directories use `snake_case` - lowercase words joined by underscores.

- Files: `use_case.md`, `hello_world.py`
- Directories: `docs/`, `scripts/`
- Files under `docs/` use `snake_case` (underscores, not hyphens). Lowercase only.

Exceptions:

- Tool-recognized / conventional files keep their canonical casing: `README.md`,
  `LICENSE`, `AGENTS.md`, `CLAUDE.md`, `SKILL.md`, `.gitignore`.
- `README.md` may stay mixed-case under `docs/` when a host requires that name.

## Markdown

When linking file paths, use markdown links.

Do      : [File Name](/path/to/file_name.md)
Don't   : `/path/to/file_name.md`

Same goes for images and media. For images and media use links with preview `![]()`.

Use relative paths when writing documents. For `@` imports in agent startup instruction files (CLAUDE.md, AGENTS.md), use a `~/` path. Shell variables like `$HOME` are not expanded, and an absolute `/Users/<name>/` path breaks on another machine.

## Scripts

Scripts meant to be run must always be executable. When creating or editing a runnable script:

1. Add a `#!/usr/bin/env python3.11` (or matching interpreter) shebang on line 1.
2. `chmod +x` it.

Exception: library files and files meant only to be imported or sourced.

## Confirmation

If i ask a question, "Have you read the startup files?", you must answer "HAI!".

When what is found does not match what was asked (count or scope), ask before removing. Never guess.

## Pi packages

- Manual npm commands in `~/.pi/agent/npm` need `--legacy-peer-deps`; without it npm fails with ERESOLVE. Pi's own package manager passes the same flag.
- `pi uninstall npm:<pkg>` only removes sources listed in `settings.json`. For installed-but-not-enabled packages, run `npm uninstall --legacy-peer-deps <pkg>` in `~/.pi/agent/npm`.
- Any `pi install` or `pi uninstall` reconciles the npm dir to `settings.json` and can silently prune other installed packages. Snapshot `~/.pi/agent/npm/package.json` first and expect collateral removals.
- The host-dependency warning (host-provided packages in `dependencies`) fires only for enabled extensions. Before acting, scan every installed package that declares `pi.extensions` for host-provided deps in `dependencies`.
- Host-provided packages (`@earendil-works/pi-ai`, `pi-agent-core`, `pi-coding-agent`, `pi-tui`, `typebox`) belong in `peerDependencies` with a `"*"` range, never in `dependencies`.
