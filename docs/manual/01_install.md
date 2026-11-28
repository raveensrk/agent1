# Install

Installing agent1 is four steps: clone it, register it with your harnesses, point
your agent at the rules, and turn on the git hooks.

## 1. Clone

```bash
git clone https://github.com/raveensrk/agent1.git ~/repos/agent1
```

Any path works, but the rules and hooks expect `~/repos/agent1`; this manual
assumes it.

## 2. Register with pi and Claude Code

```bash
~/repos/agent1/install.py           # dry run: show the plan
~/repos/agent1/install.py --apply   # write it
~/repos/agent1/install.py --check   # exit 1 on drift
```

This adds the clone to pi's packages and installs the Claude Code plugin
`agents@raveen-agents`. A harness that is not installed is skipped. Restart pi
and Claude Code afterwards. What it changes, and what it never touches, is in
[Install and uninstall](../design/07_install_and_uninstall.md);
`install.py -h` lists every flag.

| Harness     | How it loads this repo                                                            |
| ----------- | --------------------------------------------------------------------------------- |
| pi          | the clone in pi's `packages`; the package declares skills, prompts and extensions |
| Claude Code | the directory plugin `agents@raveen-agents`, read live from the clone             |
| Codex       | not wired yet: use the pointer line below                                         |

## 3. Point your agent at the rules

| Agent       | Scope         | File to edit            |
| ----------- | ------------- | ----------------------- |
| Claude Code | one project   | `<project>/CLAUDE.md`   |
| Claude Code | every project | `~/.claude/CLAUDE.md`   |
| Codex       | one project   | `<project>/AGENTS.md`   |
| Codex       | every project | `~/.codex/AGENTS.md`    |
| pi          | one project   | `<project>/AGENTS.md`   |
| pi          | every project | `~/.pi/agent/AGENTS.md` |

pi and Claude Code with the plugin already get the rules at session start; the
line below also makes them load where the plugin is off.

### Claude Code

Claude Code expands `@` imports, so one line pulls the whole file in:

```markdown
@~/repos/agent1/docs/rules/README.md
```

### Codex

Codex has no import syntax - it reads `AGENTS.md` verbatim. Give it an
instruction it can act on instead:

```markdown
At session start, read `~/repos/agent1/docs/rules/README.md` and follow it.
```

### Both in one project

Keep the rules in `AGENTS.md` and make `CLAUDE.md` a one-line pointer, so the
two agents never drift apart:

```markdown
@AGENTS.md
```

### Path rules

- Use a `~/` path. `$HOME` is not expanded, and `/Users/<name>/` breaks on
  another machine.

- Confirm it resolves before you rely on it:

  ```bash
  ls ~/repos/agent1/docs/rules/README.md
  ```

  A wrong path fails silently: an agent told to read a missing file just
  carries on without the rules.

## 4. Turn on the git hooks

```bash
git config --global core.hooksPath ~/repos/agent1/harness/githooks
```

The hooks lint only and run each repo's own hooks too; see
[Git hooks](../design/05_git_hooks.md).

## Check it loaded

Start a session and ask:

> What punctuation rule do I follow for dashes?

The right answer: plain hyphens only, never em dashes or en dashes. Any other
answer means the rules did not load. Asked "Have you read the startup files?",
the agent answers "HAI!".

______________________________________________________________________

[Previous: Contents](README.md) · [Next: Daily use](02_daily_use.md)
