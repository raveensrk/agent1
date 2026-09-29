---
name: todo
metadata:
  scope: global
description: Create, read, update, archive and delete tasks in any repo's org board, capture to inbox, and run the agent claim/submit/approve loop. Carries the task format rules and works on boards anywhere under ~/. Use when the user asks to add, edit, finish, archive or list todos, or when an agent claims and completes board work.
argument-hint: "[create|read|update|archive|delete|capture|claim] [repo or dir]"
---

# Todo

Board work goes through the `org` CLI. This skill is the agent-facing rulebook
and command sheet. Main_Quest keeps the full spec for the app; agents work from
this file. Read section 2 before a write you have not done before.

## 1. The binary

`org` 2.0.0, from [dcprevere/org-cli](https://github.com/DCPRevere/org-cli). Agent
shells often lack `~/.local/bin` on PATH, so resolve it first:

```bash
ORG=$(command -v org || echo "$HOME/.local/bin/org")
"$ORG" --version 2>/dev/null | grep -q '^org 2\.' || { echo "org CLI 2.x not found"; exit 1; }
```

`org` is the only writer of task entries. Never substitute a hand edit for it.

## 2. The rules

**States.** `TODO`, `IN_PROGRESS`, `OPTIONAL`, `LATER`, `DONE`, `OBSOLETE`.
Life cycle: `TODO` -> `IN_PROGRESS` -> `DONE`; `OPTIONAL` and `LATER` are parked
and can be promoted or dropped; anything can become `OBSOLETE` to keep the
record. A task's kind is a tag, not a state (`:bug:`, `:fixme:`). The legal
states are the ones in the file's own `#+TODO:` line.

**Task line.** A `*` at column 0, a state, a non-empty title:
`** TODO Pay rent :finance:`. A heading with no state is a container. A task may
never contain a task - break a big job into peer tasks sharing a tag. The reader
rejects a heading whose first word near-misses a state (`* done x`), an empty
title, and a container starting `TODO:`.

**Tags.** Lowercase, colon-delimited: `:finance:home:`. The charset is
`[[:alnum:]_@#%]+` - a hyphen is not a tag character, so convert `tax-2026` to
`:tax_2026:` or ask. Tags inherit from a parent container and `#+FILETAGS:`.
The reader rejects uppercase. A title ending in `:word:` is read as a tag.

**Priority.** `[#A]`, `[#B]` or `[#C]`, between the state and the title.
Optional, and never invented.

**Planning line.** Directly under the heading. `DEADLINE:` first, then `CLOSED:`
when both appear. There is no `SCHEDULED:`.

**Properties.** The drawer follows the planning line, or the heading when there
is none. `:ID:` is a UUID written by `org`; `:CREATED:` is `YYYY-MM-DD`. Other
keys are allowed, but never invent one close to `:ID:` or `:CREATED:` - the
reader rejects or warns on near-misses.

**Notes.** Everything between the heading and the next heading is the note.
`- [ ]` checklists are steps in a procedure, not tasks. An indented example task
is not a task: a `*` not at column 0 is never a heading.

**Dates.** `org` takes a bare `2026-11-05` and fills the day name itself. It
rejects a time, angle brackets and a hand-written day name - measured
2026-09-29. `:CREATED:` is a date, never a time.

**Recurring.** The format allows a repeater inside `DEADLINE:` (`+1m` counts
from the deadline, `.+3w` from completion), but `org` cannot write one and
`org deadline` **deletes** an existing one. Never run `deadline` on a recurring
task. Recurrence is the human's; leave those deadlines alone.

**Reporting.** ⏳ open (`TODO`, `IN_PROGRESS`, `OPTIONAL`, `LATER`), ✅ `DONE`,
🗑️ `OBSOLETE`, and ⚠️ replaces the state emoji when an open task is past its
`DEADLINE:`.

## 3. What to read

A directory the user named wins: that directory and everything under it.
Otherwise read the `default_dirs` in `~/dot_local/config/todo_skill.toml`, one
at a time, minus its `ignore` rules; if that file is missing, read the current
directory.

```toml
# ~/dot_local/config/todo_skill.toml
default_dirs = ["~/dot", "~/repos"]
ignore = ["node_modules", "repos/notes", ...]
```

`org` has no ignore flag, so drop any result whose file path matches an
`ignore` entry, and never write inside an ignored path. For a big tree, build an
explicit `--files` list instead of scanning everything.

```bash
"$ORG" -d <dir> -f json todo list                 # filters: --state --tag --priority --sort
"$ORG" -d <dir> -f json read <file> "id:<uuid>"   # one subtree, notes and all
"$ORG" -d <dir> -f json task show id:<uuid>       # one coordination task, with its revision
```

`todo list` reads every `*.org` and `*.org_archive` under `<dir>`, so raw
recursion also returns fixtures and specs that hold example tasks; say so when
the count looks wrong.

## 4. Where to write

Walk up from the cwd to the git root: `git rev-parse --show-toplevel`. The board
is `<root>/todo.org`; never create a second board inside a repo. Outside a repo,
walk up to the nearest `todo.org`; if none, use `<cwd>/todo.org` and write this
scaffold first - the header and container are not task entries, so a hand write
is allowed:

```org
#+TITLE: TODO
#+TODO: TODO IN_PROGRESS OPTIONAL LATER | DONE OBSOLETE
#+STARTUP: logdone

* Tasks
```

`org add` never creates a file, and `--under Tasks` fails with
`Headline not found: Tasks` when the container is missing. If `* Tasks` is
missing, add it; if the file has several containers, ask which one.

After creating a task, keep its `:ID:` and address it as `id:<uuid>` from then
on. Titles repeat, and quotes or colons in a title make a bad ref.

## 5. Capture (inbox)

When the user says "remember", "remind me", "note this", "save it for later",
or unshaped "create a task", append one plain heading to the nearest `inbox.org`
and nothing else:

```org
* Look into OpenRouter routing
```

If no `inbox.org` exists, create it with only `#+TITLE: INBOX`. Append, never
reformat. No state, no `:ID:`, no deadline, no tags; a title starting with a
state word (`Later`, `Done`, `todo:`) is read as a task, so reword it.

Durable knowledge goes to `docs/`. A single-command triviality just gets done.
Shaped work with clear acceptance criteria goes to the board as a task.

## 6. The verbs

### Create

Two commands: `org add`, then the `:CREATED:` property. Use absolute paths.

```bash
F=/abs/path/todo.org; D=/abs/path; T="Pay rent"
STATE=$(sed -n 's/^#+TODO: \([A-Z_]*\).*/\1/p' "$F" | head -1)
[ -n "$STATE" ] || { echo "no #+TODO: in $F"; exit 1; }

ID=$("$ORG" -d "$D" -f json add "$F" "$T" --todo "$STATE" --under Tasks \
    --deadline 2026-11-05 --tag finance | python3 -c "import json,sys;print(json.load(sys.stdin)['data']['id'])")
"$ORG" -d "$D" -f json property set "$F" "id:$ID" CREATED "$(date +%F)"
"$ORG" -d "$D" -f json read "$F" "id:$ID" | head -c 300   # read it back
```

- `org` never writes `:CREATED:`. The second command adds it, with or without `--under`.
- The state word comes from the file's own `#+TODO:`; its first keyword is the default.
- Tags are lowercase, no hyphen. Priority is `--priority A`, `B` or `C`.
- `--deadline` takes a bare `2026-11-05` and nothing else; `org` fills the day name.
- Never `org add` without `--under`: it lands at the root.
- Never `org task create`: measured 2026-09-29, it writes `tasks.org`, not the board.
- If the board's repo ships a linter, run it on the file, for example `./scripts/lint_board.sh <file>`.

### Read

Same commands as section 3.

### Update

```bash
"$ORG" -d "$D" -f json todo set "$F" "id:$ID" IN_PROGRESS   # human status, not a claim
"$ORG" -d "$D" -f json deadline "$F" "id:$ID" 2026-12-01
"$ORG" -d "$D" -f json priority "$F" "id:$ID" A
"$ORG" -d "$D" -f json tag add "$F" "id:$ID" home
"$ORG" -d "$D" -f json tag remove "$F" "id:$ID" home
"$ORG" -d "$D" -f json property set "$F" "id:$ID" KEY value
"$ORG" -d "$D" -f json append "$F" "id:$ID" "extra context"   # subtree body
```

- These plain verbs accept and ignore `--expected-revision`: measured 2026-09-29, a wrong hash is accepted. Read immediately before writing. The `task` verbs do enforce it.
- Never run `todo set ... DONE`. Completion is the loop in section 7. `IN_PROGRESS` is a human status, not a claim; set it only when asked.
- `append` adds to the subtree body. Any line starting with `*` at column 0 becomes a heading, so indent it.
- Never touch a file while a claim is live on it. `task show` reports `working` while a claim holds.
- Titles cannot be edited; no verb rewrites a heading. Append a note, or ask the human.

### Archive

```bash
"$ORG" -d "$D" -f json archive "$F" "id:$ID"   # subtree -> <file>.org_archive
```

Archiving is optional housekeeping; `DONE` may stay on the board. `org archive`
creates the archive without the `#    -*- mode: org -*-` first line, and without
a `#+TODO:` line. Add both once, by hand, after the first archive from a file -
copy the `#+TODO:` line from the source. Without it a reader accepts only `TODO`
and `DONE`, so archived `IN_PROGRESS` and `OBSOLETE` items are rejected.

### Delete

No delete verb exists. `OBSOLETE` keeps the record; report what you did as
"marked OBSOLETE, not deleted". A true delete is the human's, by hand.

```bash
"$ORG" -d "$D" -f json todo set "$F" "id:$ID" OBSOLETE
```

## 7. The coordination loop

Agents never set `DONE` directly. Claim the task, verify the work against the
acceptance text, submit, and a different actor approves. With one agent, the
human is the approving actor.

```bash
D=<board dir>
export ORG_ACTOR=pi            # if unset, ask; never invent one

"$ORG" -d "$D" -f json task ready            # candidates, in pick order
ID=<uuid>
REV=$("$ORG" -d "$D" -f json task show id:$ID | python3 -c "import json,sys;print(json.load(sys.stdin)['data']['revision'])")
CLAIM_ID=$(uuidgen)
"$ORG" -d "$D" -f json task claim id:$ID --actor "$ORG_ACTOR" --claim-id "$CLAIM_ID" --expected-revision "$REV"
```

Read the acceptance text in the `task show` body before you start, and verify
against it before you submit. Refresh `REV` from `task show` before every later
step, and reuse `$CLAIM_ID`:

```bash
"$ORG" -d "$D" -f json task renew   id:$ID --actor "$ORG_ACTOR" --claim-id "$CLAIM_ID" --expected-revision <fresh>
"$ORG" -d "$D" -f json task release id:$ID --actor "$ORG_ACTOR" --claim-id "$CLAIM_ID" --expected-revision <fresh> --evidence "<handoff>"
"$ORG" -d "$D" -f json task submit  id:$ID --actor "$ORG_ACTOR" --claim-id "$CLAIM_ID" --expected-revision <fresh> --evidence "<what changed>"
"$ORG" -d "$D" -f json task review                # what awaits approval
"$ORG" -d "$D" -f json task approve id:$ID --actor <other> --expected-revision <fresh> --evidence "<review>"
```

- Pick order: `[#A]`, then `[#B]`, then `[#C]`, then unprioritised; oldest `:CREATED:` first, and a task without one sorts last.
- Renew before the lease ends - 30 minutes by default.
- Release when the work cannot continue. Do not submit.
- `submit` and `approve` both require evidence. Self-approval is rejected; approve writes `DONE` and `CLOSED:`. Never fake the reviewer's actor name - ask the human.
- A task with no `:ID:` cannot be claimed, and the reader rejects the file. `org add` always writes one; a hand-written task needs the human to add it.
- After a claim the task leaves `task ready` (status `working`); read it with `task show`. Keep `$CLAIM_ID` in this process and never message it to another agent.
- On a `conflict`, fetch again and retry once - never with the old hash.

## 8. Traps

- `org` accepts a title starting `TODO:`, an empty title, an uppercase or hyphenated tag. The reader rejects all of them; the board then fails to read.
- `org` pads properties to column 0 even in a hand-indented file. That lints clean; do not "fix" it by hand.
- Adoption by the loop appends a second `:ID:` line when the drawer is indented by hand; on a column-0 drawer it merges. Harmless, lints clean.
- Lock files (`*.org-lock`, `.org-tasks.lock`) and `.org-index.db` are byproducts. Never commit them; keep them out of the repo or gitignored.
- Do not pass `--scheduled`; this schema has no `SCHEDULED:`.
