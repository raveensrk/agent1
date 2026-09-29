---
name: todo
metadata:
  scope: global
description: Create, read, update, rename, complete, archive and delete tasks in any repo's org board, capture to inbox, and optionally run the claim/submit/approve review loop. Carries the format rules and a tested helper for the org CLI. Use when the user asks to add, edit, finish, archive or list todos, or when an agent claims and completes board work.
argument-hint: "[create|read|update|archive|delete|capture|claim] [repo or dir]"
---

# Todo

Board work goes through the `org` CLI. This file carries the format rules;
`scripts/todo_agent.py` wraps `org` for the fragile parts - the state word,
`:ID:`, `:CREATED:`, revision hashes, claim ids. Main_Quest keeps the full spec
for the app; agents work from this file.

## 1. The rules

**States.** `TODO`, `IN_PROGRESS`, `OPTIONAL`, `LATER`, `DONE`, `OBSOLETE`. The
legal ones are in the file's own `#+TODO:` line. Life cycle: `TODO` ->
`IN_PROGRESS` -> `DONE`; `OPTIONAL` and `LATER` are parked; anything can become
`OBSOLETE` to keep the record. A task's kind is a tag, not a state (`:bug:`).

**Task line.** A `*` at column 0, a state, a non-empty title:
`** TODO Pay rent :finance:`. A heading with no state is a container. A task may
never contain a task - break a big job into peer tasks sharing a tag. A task
title may start `TODO:`; a *container* may not.

**Tags.** Lowercase, colon-delimited: `:finance:home:`. The charset is
`[[:alnum:]_@#%]+`, so a hyphen is not a tag character (`:tax_2026:`, not
`:tax-2026:`). Tags inherit from a container and `#+FILETAGS:`. A title ending
in `:word:` becomes a tag.

**Priority.** `[#A]`, `[#B]` or `[#C]`, between the state and the title.
Optional, and never invented.

**Planning line.** Directly under the heading. `DEADLINE:` first, then `CLOSED:`
when both appear. There is no `SCHEDULED:`.

**Properties.** `:ID:` is a UUID written by `org`; `:CREATED:` is `YYYY-MM-DD`.
Other keys are allowed, but never invent one close to `:ID:` or `:CREATED:`.

**Notes.** Everything between the heading and the next heading is the note.
`- [ ]` checklists are steps, not tasks. An indented example task is not a task:
a `*` not at column 0 is never a heading.

**Dates.** `org` takes a bare `2026-11-05` and fills the day name itself. It
rejects a time, angle brackets and a hand-written day name; `:CREATED:` is a
date, never a time.

**Recurring.** The format allows a repeater in `DEADLINE:` (`+1m` from the
deadline, `.+3w` from completion), but `org` cannot write one and
`org deadline` **deletes** an existing one. Never run `deadline` on a recurring
task; recurrence is the human's.

**Hand writes.** `org` has no rename or delete verb, so `rename` and `delete`
are the skill's two hand writes: each rewrites only what it must - one heading
line, or one subtree - refuses if the board changed underneath, and verifies
through `org` afterwards. Never hand-edit anything else in a task entry.

**Delete is delete.** `delete` removes the subtree, body and all. Git keeps
history when the board is tracked; outside git it is unrecoverable. Use
`obsolete` only when the record is worth keeping.

**Enforcement.** `org` validates almost nothing. The linter catches a missing
`:ID:`, an empty title, and a malformed timestamp. It does **not** catch bad
tags, a `TODO:` or near-miss container, a `:CREATD:`-style property, or an
unknown state keyword - that heading silently stops being a task. Everything
else here is on you.

**Reporting.** ⏳ open (`TODO`, `IN_PROGRESS`, `OPTIONAL`, `LATER`), ✅ `DONE`,
🗑️ `OBSOLETE`, and ⚠️ replaces the state emoji when an open task is past its
`DEADLINE:`.

## 2. The helper

`scripts/todo_agent.py` (stdlib only). It reads the config and calls `org`, and
it resolves the board from the cwd: the git root's `<root>/todo.org`; outside a
repo, the nearest `todo.org` above; else `<cwd>/todo.org` (scaffolded on the
first create). Run it with `python3`.

```bash
python3 scripts/todo_agent.py resolve                        # board file and dir
python3 scripts/todo_agent.py read [--state TODO] [--tag x]  # config dirs + this board
python3 scripts/todo_agent.py create "Pay rent" --deadline 2026-11-05 --tag finance --priority A
python3 scripts/todo_agent.py set-state id:<uuid> IN_PROGRESS
python3 scripts/todo_agent.py set-deadline id:<uuid> 2026-12-01
python3 scripts/todo_agent.py add-tag id:<uuid> home
python3 scripts/todo_agent.py remove-tag id:<uuid> home
python3 scripts/todo_agent.py rename id:<uuid> "New title"
python3 scripts/todo_agent.py append id:<uuid> "extra context"
python3 scripts/todo_agent.py archive id:<uuid>
python3 scripts/todo_agent.py obsolete id:<uuid>
python3 scripts/todo_agent.py delete id:<uuid>
python3 scripts/todo_agent.py complete id:<uuid> [--evidence "what changed"]
python3 scripts/todo_agent.py capture "Look into OpenRouter routing"
```

Config, `~/dot_local/config/todo_skill.toml`:

```toml
default_dirs = ["~/dot", "~/repos"]     # read when no --dir is given
ignore = ["node_modules", "repos/notes"]  # dropped from reads
review_actor = "human"                  # who approves; must differ from ORG_ACTOR
```

Overrides: `TODO_SKILL_CONFIG` (config path), `ORG_BIN` (org binary),
`ORG_ACTOR` (the agent's actor). Tests: `python3 tests/run_tests.py`.

## 3. Capture vs board

Use `capture` when the user says "remember", "remind me", "note this", "save it
for later", or unshaped "create a task": one plain `*` heading in the nearest
`inbox.org`, no state, `:ID:`, deadline or tags. If the title starts with a
state word (`Later`, `Done`, `todo:`), reword it or the reader reads it as a
task. Durable knowledge goes to `docs/`; a single-command triviality just gets
done. Shaped work with acceptance criteria goes to the board.

## 4. Completing work

`complete` finishes a task with no reviewer: it releases the agent's own claim
first, records `--evidence` in the body, then sets `DONE`. `org` writes
`CLOSED:` because the file declares `#+STARTUP: logdone`. It refuses a task
claimed by another actor.

```bash
python3 scripts/todo_agent.py complete id:<uuid> [--evidence "what changed"]
```

**Optional review loop.** When the user wants a second actor to sign off,
claim, submit, and approve instead. Claim keeps the keyword at `TODO` and
stores the lock in `:TASK_CLAIM_*:`; approve writes `DONE` and `CLOSED:`.

```bash
python3 scripts/todo_agent.py claim id:<uuid>          # prints claim_id; reuse it
python3 scripts/todo_agent.py submit id:<uuid> --claim-id <cid> --evidence "what changed"
python3 scripts/todo_agent.py review                   # what awaits approval
python3 scripts/todo_agent.py approve id:<uuid> --evidence "reviewed"
python3 scripts/todo_agent.py release id:<uuid> --claim-id <cid> --evidence "handoff"
python3 scripts/todo_agent.py renew id:<uuid> --claim-id <cid>
```

- Pick order: `[#A]`, `[#B]`, `[#C]`, then unprioritised; oldest `:CREATED:`
  first, and a task without one sorts last.
- Renew before the lease ends (30 minutes by default). Release when the work
  cannot continue; do not submit.
- `submit` and `approve` both require evidence. Self-approval is rejected;
  approve writes `DONE` and `CLOSED:`.
- A task without `:ID:` cannot be claimed. `org add` always writes one; a
  hand-written task needs the human.
- After a claim the task leaves `task ready` (status `working`). Keep the claim
  id in-process; never message it to another agent.
- On a `conflict`, fetch again and retry once - never with the old hash.

## 5. Raw org

Everything the helper does is these calls. Use **absolute paths**: `<file>`
resolves against the cwd, not against `-d`.

```bash
D=<dir>; F=<absolute board path>; R="id:<uuid>"

# read
org -d "$D" -f json todo list
org -d "$D" -f json read "$F" "$R"
org -d "$D" -f json task show "$R"

# create (org never writes :CREATED:, and never creates a file or a container)
org -d "$D" add "$F" "<title>" --todo <state> --under Tasks --deadline 2026-11-05 --tag finance
org -d "$D" property set "$F" "$R" CREATED "$(date +%F)"

# update
org -d "$D" todo set "$F" "$R" IN_PROGRESS
org -d "$D" deadline "$F" "$R" 2026-12-01
org -d "$D" priority "$F" "$R" A
org -d "$D" tag add "$F" "$R" home
org -d "$D" property set "$F" "$R" KEY value
org -d "$D" append "$F" "$R" "extra context"

# archive, obsolete, delete
org -d "$D" archive "$F" "$R"              # -> <file>.org_archive
org -d "$D" todo set "$F" "$R" OBSOLETE   # keeps the record
# delete: helper only - org has no delete verb

# loop
org -d "$D" task ready|show|claim|renew|release|submit|review|approve ...
```

`rename` and `delete` have no org equivalent; the helper is the only path, and
they are the two hand writes the skill makes. The plain verbs accept and
ignore `--expected-revision`: a wrong hash is accepted. Read immediately before
writing. The `task` verbs enforce it.

## 6. Traps

- A bare `org add` without `--under` lands at the root, and `--under Tasks`
  fails with `Headline not found: Tasks` when the container is missing.
- Never `org task create`: it writes `tasks.org`, not the board.
- `org` writes properties at column 0 even in a hand-indented file. Lint
  clean; do not "fix" it by hand.
- Adoption by the loop appends a second `:ID:` line when the drawer is indented
  by hand; on a column-0 drawer it merges. Harmless, lints clean.
- `append` adds to the body: any line starting with `*` at column 0 becomes a
  heading, so indent it.
- Archiving is optional. `org archive` creates the archive without the
  `#    -*- mode: org -*-` line and without a `#+TODO:` line - add both once, by
  hand, copying `#+TODO:` from the source.
- Lock files (`*.org-lock`, `.org-tasks.lock`) and `.org-index.db` are
  byproducts. Never commit them; keep them gitignored.
- Do not pass `--scheduled`; this schema has no `SCHEDULED:`.
