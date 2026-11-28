# agent1

Reusable AI agent instructions: rules, skills, and a harness of checks, guards
and git hooks that make the rules hold. pi, Claude Code and Codex load it in
place from this clone, so projects import it instead of copying it and drifting.

## Install

```bash
git clone https://github.com/raveensrk/agent1.git ~/repos/agent1
~/repos/agent1/install.py --apply
git config --global core.hooksPath ~/repos/agent1/harness/githooks
```

Then point your agent at the rules: the
[install chapter](docs/manual/01_install.md) has the line for each agent and
how to check that it loaded.

## Docs

- [Manual](docs/manual/README.md) - install, daily use, adding rules, skills
  and checks, publishing, removal.
- [Design](docs/design/README.md) - the bible: how agent1 works and why.
- [Rules](docs/rules/README.md) - the rules every session loads.
- [Prompts](docs/prompts/README.md) - prompt templates, pi slash commands.
- [Notes](docs/notes/README.md) - research, reviews and usage records.
- [Skills](skills/index.md) - every skill and what it does.
