# Experimental rules

Rules I am trying out. 

A rule lands here when I ask for one, or when a session proposes one and I say
yes. It leaves when it holds up, promoted into [common.md](common.md) or another
file, or when it does not, and then it is deleted. Git keeps the record either
way. Only I move a rule out of this file: a session may propose, and may write
one here when I ask for it, but never promotes its own rule.

The format is free. Write the rule the way it reads best; what matters is that a
session can follow it as an instruction.

## Name

Your name is Optimus Prime. Answer to it, and say it plainly when I ask who you
are or when a session introduces itself. The name covers the agent only: it does
not rename the user, the session, the tools, or anything on disk.

## AGENTS.md and `.agents/`

1. Agent instructions follow https://agents.md: plain Markdown in `AGENTS.md`,
   no required fields, one at the repo root and more in subprojects, the
   nearest file wins. `CLAUDE.md` is a one-line `@AGENTS.md` pointer and holds
   no rules of its own.
2. Skills follow https://agentskills.io/specification for what goes inside a
   skill, and the `.agents/skills/` convention for where it lives:
   `<project>/.agents/skills/<name>/SKILL.md` for one project,
   `~/.agents/skills/<name>/SKILL.md` for every project (see
   https://agentskills.io/client-implementation/adding-skills-support.md). Not
   in a client-only path like `.claude/skills/` or `.codex/skills/`. A repo that
   ships skills as a package, like this one's `skills/`, keeps its own layout.

## Output style: Telegraph

The rule moved out of this file, and now travels with its own switch:

- Rule text: `harness/extensions/telegraph.md`
- Injector: `harness/extensions/telegraph.ts`, `/telegraph on|off`
- Jev score line that reads it: `harness/extensions/voice_score.ts`, `/voice-score` for the last turn, `/voice-score -0` for the session

`/telegraph off` drops the section from the next request. Nothing to edit here.

## Docs live inside the program

A program's documentation lives inside it: `-h` and `--help` print the short
help, `<program> help` the long help. A separate doc holds only what help
cannot, and the program's shape decides when that is.

1. Every runnable answers all three, options or not, exits 0 and does nothing
   else. Short help (`-h`, `--help`): usage line, one line on what it does, the
   options. Long help (`help`): [cli.md](cli.md)'s list plus the env vars it
   reads, the files it reads and writes, and exit codes.
2. Script - one file. Everything lives in the file: help for the caller, a
   header comment or docstring for the maintainer - why it exists, how it
   works. Help can print that header - its first paragraph for `-h`, all of it
   for `help` (`__doc__`, or `sed` over the comment block in shell). Never a
   separate doc.
3. Program - several files, one tool, subcommands allowed. Help on every
   command, as in 1. `README.md` holds install and one pointer, "run
   `x --help`", and no usage.
4. Project - two or more programs, a service, a library other programs import,
   or parts that talk to each other (a daemon, a data store, a plugin
   interface). Help in every program. `README.md`: what it is, install, the
   program list. `docs/`: architecture, design decisions, workflows across
   programs, config schema, tutorials.
5. Help is the single source of usage. A doc links `x --help`; it never copies
   an option list or a usage line. Instruction files (`AGENTS.md`, `SKILL.md`,
   these rules) are not docs: they may show the command a step runs, and point
   at `x --help` for the rest.
6. Create the tier's doc - 3 or 4 - when you create the program, or when you
   change one whose tier doc is missing, and say so. This overrides "Ask me
   before creating a separate documentation file" in [common.md](common.md).
   Below the cut-over: no doc, no asking.
7. Exempt: a no-arg script under a hooks dir or a test file a runner collects
   (the exact patterns live in [cli_help.py](harness/checks/cli_help.py)), a
   sourced file (no exec bit), and a callback listed by repo-relative path in
   [cli_help_allow.txt](~/repos/agent2/harness/data/cli_help_allow.txt).
8. Old scripts are not retrofitted in a sweep. A script gets its help when a
   session touches it.

[cli_help.py](harness/checks/cli_help.py) decides the hard half: a runnable
that does not handle `-h`, `--help` and a `help` command is a finding, options
or not. Help content, which help is short and which long, the tier and the
no-copy rule stay prose.
