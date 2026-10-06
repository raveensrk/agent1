---
name: todo
metadata:
  scope: global
description: Create, read, update, rename, complete and delete tasks in a repo's org board, and capture into it. Also picks the one task to do now. The CLI is Emacs Lisp on org-mode, the only writer; concurrent calls are safe. Use when the user asks to add, edit, finish, archive or list todos, or asks for the one top-priority item, the next task, the main quest, or what to do now - no need to paste this file.
argument-hint: "[create|read|update|delete|capture] [repo or dir]"
---

# Todo

Board work goes through `scripts/todo`, an Emacs Lisp program using org-mode.
It is the only writer. No locks: each write replaces the file in one rename and
retries with fresh content when another process wrote it first, so any number
of processes can CRUD at once.

## 1. The rules

**Org's spec.** The board is org, and org decides its semantics: states are
org's TODO keywords, a deadline is an org timestamp, archiving is org's own
arrangement, and a repeater is org's `+Nx`, `++Nx` or `.+Nx`. The CLI writes org
and never a dialect of its own, and it does no repeat arithmetic - a completion
hands the shift to org. Anywhere the CLI offers a shorthand, the shorthand
resolves to an org form.

**Emacs and org first.** The CLI is Emacs Lisp, so before writing a helper,
find the one that exists: org's parser (`org-parse-time-string`,
`org-time-string-to-absolute`), org's regexps (`org-ts-regexp3`,
`org-repeat-re`) and org's own accessors (`org-entry-get`, `org-deadline`,
`org-get-repeat`) for anything about a board; Emacs's calendar (`time-to-days`,
`decode-time`, `calendar-day-name`, `calendar-date-is-valid-p`,
`date-days-in-month`) for anything about a date. A helper that stays is one no
library answers - `todo--month-shift`, because Emacs has no month arithmetic for
a numbered date, and the block scanner, because `org-element` cannot see a block
once a column-0 `*` sits inside it. Write the measurement that justifies a
keep next to the code, not in a commit message.

**CLI only.** Every read and every write of a board goes through `scripts/todo`.
Never open a `todo.org` with `read`, `grep`, `sed`, `write` or any other tool,
not even to look at one line. If the CLI has no verb for the operation you need,
stop and ask the user whether to implement it - do not hand-edit the board.

**Board first.** A board path (file or dir) in the request is the board: pass
it as `--file` (writes) or `--dir` (reads). No path given: ask the user which
repo or `todo.org` before writing - never guess the cwd or the config dirs. Do
not write the same task to a board and move it later.

**States.** `TODO`, `IN_PROGRESS`, `OPTIONAL`, `LATER`, `DONE`, `OBSOLETE`.
They live in `scripts/todo.el`, not in the file. Life cycle: `TODO` ->
`IN_PROGRESS` -> `DONE`; `OPTIONAL` and `LATER` are deferred; anything can become
`OBSOLETE` to keep the record. A task's kind is a tag, not a state (`:bug:`).

**Task line.** A `*` at column 0, a state, a non-empty title:
`** TODO Pay rent :finance:`. A heading with no state is a container. A task may
never contain a task - break a big job into peer tasks sharing a tag. `set-state`
is the one verb that reaches a state-less heading: it promotes a container (a
`capture` line) into a task. The Archive container is never promoted - `refs`
ever look for tasks there.

**Tags.** Lowercase, colon-delimited: `:finance:home:`. The charset is
`[[:alnum:]_@#%]+`, so a hyphen is not a tag character (`:tax_2026:`, not
`:tax-2026:`). Tags inherit from a container.

**Priority.** `[#A]`, `[#B]`, `[#C]` or `[#D]`, between the state and the
title. D is the lowest level - `org-lowest-priority` is D, so org refuses
nothing the CLI writes. Optional and never invented: ask Raveen which one
before you assign it, and ask at create time rather than adding it later.
`create --priority B` or `set-priority` writes it, anything else is refused.

Raveen's rule: a recurring task is always priority B. A deadline with a repeater
makes the task recurring, so `create` and `set-deadline` apply B themselves and
refuse any other priority with a repeater.

**Planning line.** Directly under the heading. `DEADLINE:` first, then `CLOSED:`
when both appear. There is no `SCHEDULED:`.

**Properties.** None are required. The schema has no `:ID:` and no `:CREATED:`;
org's own drawers are fine when a file already has them. `:Effort:` is the one
the CLI writes itself, H:MM, by `set-effort` or `create --effort 0:30`;
org-columns, org-agenda and org-clock read it.

**Notes.** Everything between the heading and the next heading is the note.
`- [ ]` checklists are steps, not tasks. `append` adds a line to it; `set-note`
replaces it and keeps the planning line and drawers, so a `DEADLINE:`, an
`:Effort:` or a `:LOGBOOK:` survives. Long text reaches the CLI through
`--note-file F`, never through a shell heredoc: backticks inside one run as
commands, and a note that expands to nothing lands empty. The CLI refuses an
empty `--note`, an empty or unreadable file, and `--note` together with
`--note-file`.

**Examples.** A heading inside a `#+BEGIN_*` ... `#+END_*` block (src, example,
quote, ...) is documentation, not a task. `read` and refs ignore it, even when
the `*` sits at column 0. Org does not: to org and the agenda that line is a real
task, so every write refuses a file holding one and names the line - indent it by
one space, then retry.

**Archive.** Retired tasks leave the board for its own archive file, org's
default arrangement: `<board>.org_archive`, so `todo.org` archives to
`todo.org_archive`. `complete` does this itself for any task without a repeater.
A routine stays on the board: it repeats, and archiving it would retire it for
good. `archive` moves a board's old inline `* Archive` container there too.
Archives are history: no read, ref or scan ever looks inside one (they do not
match `*.org` either), and `--file <board>.org_archive` is the way to name one
on purpose. `read --overdue --recurring` on the board will not show a task that
was archived.

**Dates.** A deadline is one of three forms: `2026-11-05`, `2026-11-05 20:30`,
or a full org timestamp `<2026-11-05 Thu 20:30 +1w>` - the last is the only one
that keeps a repeater. Org fills the day name itself for the first two. Anything
else is refused: prose (`next friday`), an impossible date (`2026-13-45`), an
impossible time (`2026-11-05 25:00`) and an unwrapped repeater
(`2026-11-05 +1w`) all exit non-zero, because org would otherwise absorb them
silently (`garbage` becomes today, `2026-13-45` becomes `2027-02-14`, `25:00`
becomes the next day at 01:00).

**Postpone.** `postpone` moves a deadline instead of naming one: `+1h`, `+1d`,
`+1w`, `+1m` or `+1y` moves it by that interval, and `today` or `tomorrow` names
the day itself. A day interval keeps the time of day and counts from the later
of the deadline and today; an hour interval moves the clock and counts from the
later of the deadline's moment and now. Either way a lapsed task lands ahead
rather than staying late. The repeater is kept, and a repeater forces B - the
repeat's anchor moves, so its later instances move with it.

**Repeat cookies.** The repeater is org's, so org's three forms mean three
things. `+Nx` moves the date one interval from its anchor, so a lapse stays
overdue - three missed months stay three months late. `++Nx` moves it at least
one interval and as many as it takes to clear today, keeping the weekday and the
day of month. `.+Nx` moves it from today, or from now for hours. x is `h`, `d`,
`w`, `m` or `y`; an hour repeater needs a time of day. The CLI writes `++` for a
repeating deadline it creates or edits, while `++` and `.+` pass through as
given, and `org-auto-repeat-maybe` does the shift on DONE - so a routine
completed late lands on its next slot instead of staying overdue.

**Delete is delete.** `delete` removes the subtree, body and all. Git keeps
history; outside git it is unrecoverable. Use `obsolete` only when the record is
worth keeping.

**Enforcement.** The CLI refuses an unknown state, an unknown or ambiguous
title, and a missing container. It does not catch bad tags or a near-miss state
keyword - a heading whose first word is not a known state silently becomes a
container. Everything else here is on you.

## 2. The CLI

`todo <verb> [args]` - the CLI is on `PATH` (the skill's `scripts/` dir is
exported in `~/dot/config/bashrc`), so it runs from any directory;
`scripts/todo <verb> [args]` also works from the skill directory. Emacs is the
only dependency.

```bash
scripts/todo --help                         # main help: every verb, one line each
scripts/todo create --help                  # that verb: usage, options, note, example
scripts/todo resolve                        # board file and dir
scripts/todo read [--state TODO] [--tag x] [-d|--due] [-p A|B|C|D] [-n 1] [--file F] [--recurring] [--records]  # config dirs + this board, or just F
scripts/todo read --due -p A -n 1                # the most urgent overdue A task
scripts/todo brief                              # due or late + undated, then the easiest pick
scripts/todo doing [--file F]                   # one due TODO or IN_PROGRESS, as one record
scripts/todo doing --priority A [--file F]      # one open A task, due or not
scripts/todo --warm read [--records]            # same verb, Emacs stays up
scripts/todo create "Pay rent" --deadline 2026-11-05 --tag finance --priority A --effort 0:30
scripts/todo create "Pay rent" --note-file ~/tmp/rent.md      # long note, no heredoc
scripts/todo set-note "Inbox" --note-file ~/tmp/triage.txt     # replace the note from a file
scripts/todo set-state "Pay rent" IN_PROGRESS
scripts/todo set-priority "Pay rent" B
scripts/todo set-state "An idea captured earlier" TODO   # promotes a plain heading
scripts/todo set-deadline "Pay rent" 2026-12-01
scripts/todo set-deadline "Pay rent" "2026-12-01 20:30"   # with a time of day
scripts/todo postpone "Cut nails" +1d             # +1h +1d +1w +1m +1y, + optional
scripts/todo postpone "Trim crotch" +2h           # hours count from the later of the deadline and now
scripts/todo postpone "Clean bike" tomorrow       # today or tomorrow: the day itself
scripts/todo set-effort "Pay rent" 0:30
scripts/todo add-tag "Pay rent" home
scripts/todo remove-tag "Pay rent" home
scripts/todo append "Pay rent" "extra context"
scripts/todo set-note "Inbox" "$(cat triage.txt)"    # replace the note, meta data stays
scripts/todo rename "Pay rent" "Pay the rent"
scripts/todo complete "Pay rent" [--evidence "what changed"]   # DONE, then archived
scripts/todo archive                           # inline `* Archive' -> <board>.org_archive
scripts/todo obsolete "Pay rent"
scripts/todo delete "Pay rent"
scripts/todo capture "Look into OpenRouter routing"
scripts/todo status
scripts/todo edit "Pay rent" --file todo.org       # vim, at that heading line
scripts/todo edit-vim "Pay rent" --file todo.org
scripts/todo edit-emacs "Pay rent" --file todo.org   # Emacs, at that heading line
scripts/todo config
```

- A ref is an exact title. Two tasks with the same title make the ref ambiguous
  and the CLI refuses it. Every verb matches tasks; only `set-state` and
  `set-note` also match a state-less heading (a container or a `capture` line), and
  neither matches the Archive container.
- `-h` or `--help` prints help and exits 0 without writing: on its own, the main
  help - every verb with a one-line summary; after a verb, that verb's usage,
  options, note and example. A bare `scripts/todo` prints the main help too. The
  text lives in `todo.el` (`todo-help`), so help and the verbs cannot drift.
- The board is `todo.org` in the cwd; `--file F` overrides. When the user names a
  board, always pass `--file`/`--dir` - the cwd default is a fallback for when the
  board is known, not a licence to pick one.
- `--file F` means that exact board for every verb, read and write alike, and it
  wins when `--dir` is also given. `--dir D` makes a read scan D's `*.org` files
  instead of the configured dirs; it does nothing for a write.
- `--due` and `--overdue` are two names for one window: the deadline day is
  today or earlier in IST, repeaters included. `--due` and `-d` are the short
  spelling. It keeps open work only - `TODO` and `IN_PROGRESS` - unless
  `--state S` names another one, which wins outright: `read --due --state LATER`
  shows the late LATER tasks. A lapsed deadline on a deferred task stays out of
  the plain `read --due` list. The list comes out most urgent first - most days
  late, then A before D, then title, then path: the same comparator `doing` picks
  with, so `doing` is the head of that list. The order is the flag's default,
  not an option; board order is a plain `read` away. `--recurring` keeps the
  routines, a deadline carrying a repeater. A routine that is late: `read --due --recurring`. They read the same clock and the same repeater maths as `doing`,
  over every match instead of the one pick.
- `read -p A|B|C|D` keeps only the tasks at that priority; `read -n N` cuts the
  filtered list to its first N - urgency order under `--due`, board order
  otherwise, the order a plain `read` prints. So `read --due -p A -n 1` is the
  most urgent overdue A task. `-n` takes a positive count and `-p` one of A, B,
  C, D - anything else exits non-zero.
- `brief` is the review: one read that answers what is late and what is
  unscheduled. Two groups - the `--due` window, then every open task with no
  deadline - each in urgency order, under `due (N):` and `undated (N):` headers,
  then one `easiest:` line. The pick is the smallest `:Effort:` in the list,
  ties by urgency; with none recorded it prints `easiest: none (no :Effort: recorded)`. Default open work only, TODO and IN_PROGRESS; `--state S` names
  another state and wins, the rule `--due` uses. `--records` drops the headers
  and the pick: one plain record list, due first.
- `read` prints `STATE  Title  (path)` - no deadline, so overdue is not visible
  in a plain listing. Use `--due`/`--recurring` rather than re-parsing the
  list line.
- `create` appends at the root; `--container NAME` nests under an existing
  heading. A new file starts straight at the task, no frontmatter.
- `capture` appends a plain `*` heading (no state, no properties).
- Lists print `STATE  Title  (path)`; single results print `key: value`. `read --records` prints one plain record per task, records separated by a blank
  line: `title:`, `state:`, `deadline:`, `priority:`, `effort:`, `tags:`
  (space-joined), `path:`, then the note as lines indented four spaces (empty
  note lines too, so the blank line stays a record break). A missing deadline,
  priority or effort is an empty value. There is no JSON: the board is org, the
  CLI is Emacs, and both consumers parse this text.
- `doing` prints the main quest: `TODO` or `IN_PROGRESS`, due today or overdue in IST. Org reads the deadline, including a repeater. Most late wins, then priority A before D, then title, then path - the head of the list `read --due` prints. The pick prints as one record, or `none`. `emacs.el` draws that pick as one agenda line (`agenda2`). `agenda2.sh` is the shell alias.
- `doing --priority A|B|C|D` picks the priority-only way instead: any open task at
  that priority, due or not, title then path. No match prints `none`, as `doing`
  does. An unknown value is refused.
- `--warm` runs the same verb in one background Emacs named `todo-skill`. The plain command still starts a fresh Emacs and quits. The window uses `--warm` and starts the worker if it is down. Quit it with `emacsclient -s todo-skill --eval '(kill-emacs)'`. `edit` and `edit-vim` open vim at the heading line. With no terminal they open as `mvim -f`. `edit-emacs` opens Emacs at that same line.

Config, `~/dot_local/config/todo_skill.toml`:

```toml
default_dirs = ["~/dot", "~/repos"]       # read when no --dir is given
ignore = ["node_modules"]                 # dropped from reads
```

Overrides: `TODO_SKILL_CONFIG` (config path). Tests: `scripts/test` - bounded at
180s, prints the failures and the log tail, `scripts/test <selector>` for one test.
A bound matters: an unbounded run of this suite once hung on a daemon waiting for
a keypress and burned 300s, while the healthy suite takes 5s.

## 3. Capture vs board

Use `create` when the user says "remind me" or "remind me later": a `TODO`,
not a plain heading. Use `capture` when the user says "remember", "note this",
"save it for later", or an unshaped "create a task": one plain heading at the
end of the board, no state, no properties. Durable knowledge goes to `docs/`; a
single-command triviality just gets done. Shaped work with acceptance criteria
goes to the board with `create`.

## 4. Completing work

Verify against the acceptance criteria in the note first. `complete` appends
`--evidence` to the body, sets `DONE` and writes `CLOSED:`, then moves the task
to the board's archive file - unless its deadline carries a repeater, in which
case it stays on the board and org shifts the date by that cookie's own rule: a
`++` routine lands on its next slot after today, a lone `+` one interval past its
anchor, so it can stay overdue. The print names where it landed. The archive copy is org's
own shape: the header, and an `:ARCHIVE_TIME:`/`:ARCHIVE_FILE:`/`:ARCHIVE_CATEGORY:`/
`:ARCHIVE_TODO:` drawer, per `org-archive-save-context-info`. Print shows which
happened: `archived: <file>` or `routine: yes`. There is no review loop and no
claim: an agent finishes its own work.

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
  that starts with a star - the write itself refuses a file whose block holds
  such a line, naming the file and the line. `set-note` refuses a star at column
  0 in its TEXT outright, before the file is touched.
- A long note goes in a file, through `--note-file F`. A heredoc built into a
  command line is the trap: backticks in the body run as commands, and the task
  lands with an empty note. An empty note is refused, so the damage stops at the
  call instead of reaching the board.
- A routine's date is org's to shift, and org shifts by the cookie it is given:
  a `+1w` routine left for three weeks is still two weeks late after a completion.
  Rewrite it as `++1w` (`todo set-deadline "<%date%> ++1w"`) and a completion lands
  it on its next slot. A routine written by an older CLI, or edited by hand in
  Emacs, can carry a lone `+`.
- Org asks, once ten repeat intervals are not enough to clear today, whether to
  keep shifting. A batch call has nobody to answer, so the CLI answers yes and the
  routine catches up however far it is behind. The question is org's, not the
  CLI's: it appears only when the same board is completed in interactive Emacs.
- `set-deadline` on a `DONE` task drops `CLOSED:` (org behaviour). Reopen
  before setting a deadline if the closed time matters.
- The CLI writes no frontmatter, no extra properties, and creates an archive
  file only through `complete` (and `archive`). It never creates `inbox.org`.
- Two writes, archive first: `complete` appends to `<board>.org_archive` and then
  cuts the task out of the board. A crash between the two leaves the task in
  both files, never in neither - re-run `complete` after deleting the archive
  copy, or cut it by hand.
- `read` skips hidden directories and anything matching `ignore`, and scans
  `*.org` under the configured dirs. It does not descend into `.git`.
