---
name: migrate-todo
metadata:
  scope: global
description: 'Convert line-schema todos (- TODO: ...) to the org schema, one repo at a time. Dry run by default. Use when the user asks to migrate, convert or upgrade todos to the org format.'
argument-hint: "[dir ...] [--apply]"
allowed-tools: Read, Glob, Grep, Bash(python3:*), Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git -C:*)
disable-model-invocation: false
---

# Migrate todos to the org schema

## Target

The directories the user named. Default to `~/repos ~/dot` when none are
given.

## What this does

Consolidates each repo's boards into repo-root org files per
[Todo Schema (Org)](../../todo_schema.org):

```org
#+TITLE: TODO
#+TODO: TODO IN_PROGRESS OPTIONAL LATER | DONE OBSOLETE
#+STARTUP: logdone

* Tasks
** TODO Pay rent :finance:home:
   DEADLINE: <2026-08-05 Wed>
   :PROPERTIES:
   :ID: 7f3c1e2a-...
   :CREATED: 2026-08-01
   :END:
```

A board is a `.md` file named `todo`, `inbox` or `archive`
(case-insensitive) that holds line-schema items. Every git repo under the
roots gets the full schema file set — `todo.org`, `todo.org_archive`,
`inbox.org`, `inbox.org_archive` — with headers, empty where there is nothing
to fill:

| Source                          | Destination                        |
|---------------------------------+------------------------------------|
| `todo.md` / `TODO.md` items     | `todo.org` at repo root            |
| `inbox.md` items                | `todo.org` (they are shaped tasks) |
| `archive.md` items              | `todo.org_archive` / `inbox.org_archive`, paired with the board in its directory |
| any other `.md` with items      | not converted; named in the report |
| nothing to fill                 | empty file with its header — that is fine |

The conversion is done by `scripts/migrate_todo.py` in this skill's directory
(`<skill_dir>` below is the directory holding this file). Run the script. Do
not convert lines yourself: a deterministic pass over thousands of lines is
the point, and an agent editing them by hand is slower, costlier and less
repeatable.

## Steps

1. Generate the visual report first, always. It writes only the report file.

   ```bash
   python3 <skill_dir>/scripts/migrate_todo.py --report ~/Downloads/migration_report.html \
       ~/repos ~/dot
   ```

2. Open the report for me and summarize: totals, per-repo destinations, dirty
   repos, skipped files. The report shows every source board next to its
   converted output in a dark-themed HTML page.

3. Stop for my approval. A repo I did not expect, a count far off, any failed
   file - raise it before writing. Nothing is committed until I say go.

4. On my go-ahead, apply. Each repo is converted and committed on its own, and
   a repo with a dirty tree is skipped rather than mixed into my work. The
   script writes the org files, `git rm`s the source boards and commits.

   ```bash
   python3 <skill_dir>/scripts/migrate_todo.py --apply ~/repos ~/dot
   ```

5. Report what landed: the commit in each repo, and which repos were skipped
   for being dirty so I can come back to them.

## Rules

- Never pass `--apply` on your own. It is mine to authorise, every run.
- Never edit the script to get a file through. A file the script refuses is a
  schema question, not a script bug - tell me what it choked on.
- Do not touch any doc that teaches an old format (the line schema, the lisp
  schema). Their examples are documentation, and the script already skips
  fenced blocks.
- Do not convert test fixtures. The script skips `tests/` and `fixtures/`
  because code asserts on those exact strings.
- Prose inside a board is preserved as body text, never dropped. Frontmatter
  is dropped (git keeps it); the report counts the lines.

## What the script guarantees

| Guarantee | How |
|---|---|
| Report first, approval before anything | `--report` writes only the HTML report; `--apply` is never run without the user's go-ahead |
| A revert undoes one repo | One commit per repo, dirty trees refused |
| No invalid org file | Every generated file reparsed by a reader per the schema before anything is written |
| Full file set in every repo | `todo.org`, `todo.org_archive`, `inbox.org`, `inbox.org_archive` exist after apply, empty with headers where there is nothing to fill |
| Examples survive | Fenced blocks skipped |
| Tests survive | `tests/`, `fixtures/`, `target/`, `node_modules/` skipped |
| A symlinked file converts once | Paths resolved across all roots before conversion |
| No invented ids except UUIDs | Existing `[T<n>]` kept as a body note; `:ID:` is a fresh UUID per task |
| Tags fold to lowercase | Org tags are case-sensitive; the schema rejects uppercase |
| Task depth is uniform per repo | No task can nest inside a task when boards merge |
| Markdown headings never become tasks | A heading starting with a state-like word becomes a container named `Board — ...` |

## Report format

```
9795 items into 16 org files

  Main_Quest (dirty, would skip)
    todo.org                   46 items  <- 2 board(s)
    todo.org_archive         9635 items  <- 1 board(s)
  work
    todo.org                    1 items  <- 1 board(s)
    inbox.org_archive          12 items  <- 1 board(s)
  skipped <file>: reason

Dry run. Nothing written.
```

Lead with the totals, then the per-repo table, then skipped files. No preamble.
