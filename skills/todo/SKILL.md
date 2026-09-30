---
name: todo
metadata:
  scope: global
description: Create, read, update, rename, complete and delete tasks in a repo's org board, and capture into it. The CLI is Emacs Lisp on org-mode, the only writer; concurrent calls are safe. Use when the user asks to add, edit, finish, archive or list todos.
argument-hint: "[create|read|update|delete|capture] [repo or dir]"
---

# Todo

Board work goes through `scripts/todo`, an Emacs Lisp program using org-mode.
It is the only writer. No locks: each write replaces the file in one rename and
retries with fresh content when another process wrote it first, so any number
of processes can CRUD at once.

## 1. The rules

**States.** `TODO`, `IN_PROGRESS`, `OPTIONAL`, `LATER`, `DONE`, `OBSOLETE`.
They live in `scripts/todo.el`, not in the file. Life cycle: `TODO` ->
`IN_PROGRESS` -> `DONE`; `OPTIONAL` and `LATER` are deferred; anything can become
`OBSOLETE` to keep the record. A task's kind is a tag, not a state (`:bug:`).

**Task line.** A `*` at column 0, a state, a non-empty title:
`** TODO Pay rent :finance:`. A heading with no state is a container. A task may
never contain a task - break a big job into peer tasks sharing a tag.

**Tags.** Lowercase, colon-delimited: `:finance:home:`. The charset is
`[[:alnum:]_@#%]+`, so a hyphen is not a tag character (`:tax_2026:`, not
`:tax-2026:`). Tags inherit from a container.

**Priority.** `[#A]`, `[#B]` or `[#C]`, between the state and the title.
Optional, and never invented.

**Planning line.** Directly under the heading. `DEADLINE:` first, then `CLOSED:`
when both appear. There is no `SCHEDULED:`.

**Properties.** None are required. The schema has no `:ID:` and no `:CREATED:`;
org's own drawers are fine when a file already has them.

**Notes.** Everything between the heading and the next heading is the note.
`- [ ]` checklists are steps, not tasks.

**Archive.** Retired tasks stay at the end of the board under a `* Archive`
container, after the live content and 40 blank lines. There is no separate
`_archive` file. `read` and refs skip the container: it is history.

**Dates.** The CLI takes a bare `2026-11-05` and org fills the day name itself.
It rejects a time, angle brackets and a hand-written day name.

**Delete is delete.** `delete` removes the subtree, body and all. Git keeps
history; outside git it is unrecoverable. Use `obsolete` only when the record is
worth keeping.

**Enforcement.** The CLI refuses an unknown state, an unknown or ambiguous
title, and a missing container. It does not catch bad tags or a near-miss state
keyword - a heading whose first word is not a known state silently becomes a
container. Everything else here is on you.

## 2. The CLI

`scripts/todo <verb> [args]` - run it from the skill directory, or give the
absolute path. Emacs is the only dependency.

```bash
scripts/todo resolve                        # board file and dir
scripts/todo read [--state TODO] [--tag x]  # config dirs + this board
scripts/todo create "Pay rent" --deadline 2026-11-05 --tag finance --priority A
scripts/todo set-state "Pay rent" IN_PROGRESS
scripts/todo set-deadline "Pay rent" 2026-12-01
scripts/todo add-tag "Pay rent" home
scripts/todo remove-tag "Pay rent" home
scripts/todo append "Pay rent" "extra context"
scripts/todo rename "Pay rent" "Pay the rent"
scripts/todo complete "Pay rent" [--evidence "what changed"]
scripts/todo obsolete "Pay rent"
scripts/todo delete "Pay rent"
scripts/todo capture "Look into OpenRouter routing"
scripts/todo status
scripts/todo edit [--editor "nvim"]
scripts/todo config
```

- A ref is an exact title. Two tasks with the same title make the ref ambiguous
  and the CLI refuses it.
- The board is `todo.org` in the cwd; `--file F` overrides.
- `create` appends at the root; `--container NAME` nests under an existing
  heading. A new file starts straight at the task, no frontmatter.
- `capture` appends a plain `*` heading (no state, no properties).
- Lists print `STATE  Title  (path)`; single results print `key: value`.

Config, `~/dot_local/config/todo_skill.toml`:

```toml
default_dirs = ["~/dot", "~/repos"]       # read when no --dir is given
ignore = ["node_modules"]                 # dropped from reads
```

Overrides: `TODO_SKILL_CONFIG` (config path). Tests:
`emacs -Q --batch -l tests/todo_tests.el -f ert-run-tests-batch-and-exit`.

## 3. Capture vs board

Use `capture` when the user says "remember", "remind me", "note this", "save it
for later", or an unshaped "create a task": one plain heading at the end of the
board, no state, no properties. Durable knowledge goes to `docs/`; a
single-command triviality just gets done. Shaped work with acceptance criteria
goes to the board with `create`.

## 4. Completing work

Verify against the acceptance criteria in the note first. `complete` appends
`--evidence` to the body, sets `DONE` and writes `CLOSED:`. There is no review
loop and no claim: an agent finishes its own work.

## 5. Concurrent writers

No lock and no waiting. Every write reads the file, edits it in memory and
replaces it in one rename; if another process wrote it in between, the CLI
retries with the fresh content (five tries, then it fails with a clear message).
Two writers on different tasks both land. Two writers on the same task: the
second read sees the first change and applies on top.

`edit` opens `$EDITOR` (default `mvim -f`) on the board with no lock - agents
may write while you edit, and the last save wins.

## 6. Traps

- Any line starting with `*` at column 0 is a heading, so indent `append` text
  that starts with a star.
- `set-deadline` on a `DONE` task drops `CLOSED:` (org behaviour). Reopen
  before setting a deadline if the closed time matters.
- The CLI writes no frontmatter, no properties, and no archive file. Do not
  create `todo.org_archive` or `inbox.org`; they are not used.
- `read` skips hidden directories and anything matching `ignore`, and scans
  `*.org` under the configured dirs. It does not descend into `.git`.
