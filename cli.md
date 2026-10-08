# CLI apps

Split from [common.md](common.md); routed by [rules_context.ts](harness/extensions/rules_context.ts).

A CLI I write tells me how to use it - the author six months later is the
caller. The worked example is Waypoint's CLI,
[src/cli.ts](~/repos/waypoint/src/cli.ts), help table and all.

- `-h` and `--help` are a hard rule: every CLI app has both, on the main command
  and on every subcommand. Usage line, what the app does, every option, one
  runnable example. Exit 0, and nothing else runs - a help call never writes,
  never starts a daemon, never asks a question. argparse's default `add_help`
  gives both, and gives them per subcommand; a script that parses options by
  hand has to handle the pair itself.
- A bare call prints the main help too, unless a bare call is itself a real
  command (`bookmark` with no arguments lists).
- Short flags are the optional half. The long flag is the default spelling, and
  a short alias goes in when a free letter exists: `--due|-d`, `--priority|-p`.
  A letter already taken in that app goes to the next free one; when none fits,
  the long flag stands alone.
- One table drives the main help and every subcommand's help, and a test asserts
  every verb has an entry, so the two cannot drift (see `VERB` in
  [src/cli.ts](~/repos/waypoint/src/cli.ts) and its help test).

`harness/checks/cli_help.py` decides the hard half: a runnable - options or
not, per [experimental.md](experimental.md) - must mention both `-h` and
`--help`, and the finding names the one that is missing. Which letter a short
flag takes, and how a subcommand's help reads, stay prose: this file.

## Designing a new command

- A new command's default human-readable output: ask the shape first, with one MCQ that shows a concrete example of each. The renderer is the expensive part to redo.
