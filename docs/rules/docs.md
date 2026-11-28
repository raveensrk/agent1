---
last_reviewed: 2026-11-02
---

# Docs

Put a program's documentation in its help output. Write a separate doc only for
what help cannot hold.

## Every runnable has help

Every runnable handles these three calls, even if it takes no options. Each call
prints help, exits 0 and does nothing else.

| Call       | Prints     |
| ---------- | ---------- |
| `x -h`     | Short help |
| `x --help` | Short help |
| `x help`   | Long help  |

- Short help: usage line, one line on what it does, the options.
- Long help: everything in [agent1.md](agent1.md) section CLI, plus env vars read, files read
  and written, exit codes.

Usage is written only in help. Docs link to `x --help` and never copy options or
a usage line. Instruction files (`AGENTS.md`, `SKILL.md`, these rules) are not
docs, so they may show the command a step runs.

## What else to write

Pick the row that matches what you are building.

| You have | Write                       | Do not write     |
| -------- | --------------------------- | ---------------- |
| Script   | Header comment or docstring | Any separate doc |
| Program  | `README.md`                 | Usage            |
| Project  | `README.md` and `docs/`     | Usage            |

What each one means:

- Script: one file.
- Program: several files, one tool, subcommands allowed.
- Project: two or more programs, a service, a library other programs import, or
  parts that talk to each other (daemon, data store, plugin interface).

What each doc holds:

- Header comment or docstring: why it exists, how it works. Help can print it:
  first paragraph for `-h`, all of it for `help` (`__doc__` in Python, `sed`
  over the comment block in shell).
- Program `README.md`: install, then "run `x --help`".
- Project `README.md`: what it is, install, list of programs.
- The bible: see below.

When you create a program or project, or change one missing its `README.md` or
`docs/`, create the missing file without asking and tell me you did.

## The bible, the manual and the notes

Every app repo has the same three folders of Markdown:

- `docs/design/`, the bible: the design document. Entry page
  `docs/design/README.md`; a big project splits it into chapters.
- `docs/manual/`, the user manual: how a person installs and uses the app,
  every screen and command. Entry page `docs/manual/README.md`.
- `docs/notes/`, the notes: research, history, plans, measurements and other
  working notes that are neither design nor manual. Entry page
  `docs/notes/README.md` lists them.

agent1 itself has two more: `docs/rules/` (the rules every session loads;
`README.md` is the entry, and rule files keep topic names such as `git.md`, not
numbers, because they are looked up and linked by topic) and `docs/prompts/`
(the prompt templates pi loads).

No `<repo>.md` at the root, no `design_docs/`. `README.md` stays short: what it
is, install, and links to all three.

Write `docs/` like a book, all three folders:

- Each folder's `README.md` is its title page and table of contents, in
  reading order.

- Chapters are numbered files (`01_install.md`, `02_the_app.md`) and read
  front to back: each starts from what the ones before it said.

- Every chapter ends with previous and next links; the first links back to the
  table of contents.

- Prose first, in plain words: a chapter explains, then lists. One fact lives
  in one place; other chapters link to it.

[publish_books](../../scripts/publish_books) publishes every repo's `docs/` as an
HTML book in the GNU manual style, into `agent1/books/` (git ignored).

What goes where:

- From the bible alone, any AI agent can rebuild the project from scratch.

- It is language agnostic: what the project does, its rules, data, behaviour,
  screens, commands and design decisions. No source paths, line numbers,
  test names, function names or language-specific build steps.

- The manual is for people; it may show how to run a command, but usage itself
  stays in `--help`, and the manual links to it.

- `AGENTS.md` holds the code details: layout, build and test commands, test
  names and which rule each checks, evidence with file and line.

## What is exempt from help

- No-arg scripts under a hooks directory, and test files a runner collects.
  Exact patterns are in [cli_help.py](../../harness/checks/cli_help.py).
- Sourced files (no exec bit).
- Callbacks listed by repo-relative path in
  [cli_help_allow.txt](~/repos/agent2/harness/data/cli_help_allow.txt).
- Old scripts, until a session touches them. Do not retrofit in a sweep.

## What is checked

[cli_help.py](../../harness/checks/cli_help.py) reports any runnable missing `-h`,
`--help` or `help`. Nothing checks the rest: what help says, or which docs
exist.
