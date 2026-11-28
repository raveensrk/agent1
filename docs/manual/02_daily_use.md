# Daily use

Once installed, agent1 mostly works without being asked. This chapter says what
you see and what you can type.

## Sessions

Every new session starts with the rules already in its prompt: the rules entry
page, the list of topic files with when to read each, and the trial rules. You
do not need to tell the agent to read them. When you edit a rule, start a new
session to see it (pi picks it up on its next request).

While you work:

- A command that is known to hang (a recursive grep, an unbounded
  `curl | sh`) is refused, with the command to use instead.
- An edit whose old text is not in the file exactly once is refused, with the
  nearest text shown.
- Two failed tool calls in a row bring one line offering to learn from the
  failure.
- When the agent stops, the files it edited are linted, and new findings send
  it back to fix them, at most three times a session.

## Slash commands

In pi:

| Command                           | What it does                                                     |
| --------------------------------- | ---------------------------------------------------------------- |
| `/telegraph on`, `off`            | Turn the short telegraph voice on or off                         |
| `/voice-score`, `/voice-score -0` | Score the last run's (or every run's) voice and tokens           |
| `/voice-score on`, `off`          | Score every run automatically                                    |
| `/call-score`, `on`, `off`        | Score the last run's tool calls, or every run's                  |
| `/<prompt name>`                  | Paste a prompt template from [the prompts](../prompts/README.md) |

In Claude Code the telegraph switch is a shell command, shared with pi:

```bash
node --experimental-strip-types ~/repos/agent1/harness/hook.ts telegraph on
```

## Skills

Skills load on demand when a task matches their description, or by name: in
Claude Code as `/agents:<skill>` (for example `/agents:next`), in pi as
`/skill:<skill>`. The list is in [skills/index.md](../../skills/index.md).

## The self-improvement line

agent1 calls itself Optimus Prime. When a task ends it looks back for one way to
improve agent1, and if it finds one it ends its reply with a line like:

```
Optimus Prime: add a check for X, in harness/checks/
```

The same line is logged, dated, in
[self_improvement.md](../notes/self_improvement.md). Nothing changes until you
say yes.

______________________________________________________________________

[Previous: Install](01_install.md) · [Next: Add a rule](03_add_a_rule.md)
