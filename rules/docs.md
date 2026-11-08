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
- Long help: everything in [cli.org](../requirements/cli.org), plus env vars read, files read
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
- `docs/`: architecture, design decisions, workflows across programs, config
  schema, tutorials.

When you create a program or project, or change one missing its `README.md` or
`docs/`, create the missing file without asking and tell me you did.

## What is exempt from help

- No-arg scripts under a hooks directory, and test files a runner collects.
  Exact patterns are in [cli_help.py](../harness/checks/cli_help.py).
- Sourced files (no exec bit).
- Callbacks listed by repo-relative path in
  [cli_help_allow.txt](~/repos/agent2/harness/data/cli_help_allow.txt).
- Old scripts, until a session touches them. Do not retrofit in a sweep.

## What is checked

[cli_help.py](../harness/checks/cli_help.py) reports any runnable missing `-h`,
`--help` or `help`. Nothing checks the rest: what help says, or which docs
exist.
