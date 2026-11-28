# What agent1 is

agent1 is one person's reusable set of AI agent instructions, kept in one git
repo and loaded in place by every agent harness on the machine: pi, Claude Code
and, by a pointer line, Codex. Projects import it instead of copying the rules
and letting the copies drift.

It holds four kinds of thing:

- **Rules.** Plain Markdown that every session reads: how to work, how to
  commit, how to write Markdown, macOS traps, and more. One entry page indexes
  them all.
- **Skills.** Packaged task instructions in the open Agent Skills format, each a
  folder with a skill file and its scripts.
- **The harness.** Code that makes the rules hold without relying on the model
  to remember them: deterministic checks, guards that refuse a tool call,
  a lint that runs when the agent stops, and git hooks for every repo.
- **Docs.** The rules, prompt templates, notes, this design book and the manual,
  all under one docs folder and published together as one HTML book.

The guiding idea, from Joel Quenneville's Rails World 2026 talk "Harness
Engineering on Rails"
([slides](https://speakerdeck.com/joelq/harness-engineering-on-rails)), is that
an agent is a reactive system: it reacts to signals. Anything a rule says that a
program can decide belongs in a program - a check, a guard or a hook - and the
prose keeps only what needs judgement. The four quadrants this splits into are
in [Harness checks](04_harness_checks.md).

agent1 is public and written for any agent. Rules that hold only for this one
machine live in a separate private repo, agent2, which agent1 picks up only when
it exists.

## Layout

Everything meant to be read lives under `docs/`: `rules/` (with `examples/`, the
cljfx and web demos the rules point at), `prompts/`, `notes/`, `design/` and
`manual/`. The root holds code and configuration: the skills, the harness and
its git hooks, the Claude Code plugin manifest and hook wiring, the pi package
manifest, a shell snippet under `config/`, the publishing scripts under
`scripts/`, the install and uninstall entry points, and `archive/`, where
retired skills, commands, personas, prompts and rules are kept out of every load
path.

______________________________________________________________________

[Previous: Contents](README.md) · [Next: How rules load](02_how_rules_load.md)
