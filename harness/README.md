# harness

The deterministic half of the harness: one command that runs every check, plus
the pi trigger that hands the findings back to the agent.

The idea comes from Joël Quenneville's Rails World 2026 talk "Harness
Engineering on Rails" ([slides](https://speakerdeck.com/joelq/harness-engineering-on-rails)):
an agent is a reactive system, and it reacts to signals. Rubocop is the shape
to copy - one command, every rule, language-agnostic here. The talk's grid:

| | computational | inferential |
| --- | --- | --- |
| **feedback** (after the work) | linters, tests, this directory | agentic review, the learn-from-session skill |
| **feedforward** (before the work) | generators, templates, guards | `AGENTS.md` prose, a `SKILL.md` |

The rule that makes it pay: anything in `AGENTS.md` that a check can decide
belongs in a check. Prose is for what only judgement can decide.

## Commands

```
python3 harness/lint.py                 # this repo: tracked + untracked files
python3 harness/lint.py --changed       # only changes against HEAD, plus untracked
python3 harness/lint.py FILE...         # only those files
python3 harness/lint.py --repos         # every git repo under ~/repos
python3 harness/lint.py --list          # the checks, their quadrant and scope
python3 harness/lint.py --json          # for scripts and the trigger
python3 harness/tests/test_lint.py      # the checks' own tests
```

Exit 0 clean, 1 findings, 2 a check failed to run. A failing check is reported
as a failure, never as a finding.

## Adding a check

Drop a file in `checks/`. Nothing else changes: the dispatcher discovers it,
reads its header and decides which files it sees.

```python
#!/usr/bin/env python3
# harness-check: {"id": "my_check", "applies": ["*.py", "!**/vendor/**"],
#                 "quadrant": "feedback/computational"}
```

- `applies` are fnmatch globs against the repo-relative path or the basename;
  a leading `!` drops a path. No `applies` means every file.
- The dispatcher passes the candidate file paths on stdin, one per line, and
  runs the check with the repo root as the working directory.
- Print findings as `path:line: message` and exit 0. Nothing on stdout means
  clean. A nonzero exit means the check itself is broken.
- End the message with the fix, as a command when there is one. A signal that
  does not steer sends the next attempt down the same dead end.

Check the same mistake by hand first: a rule in `common.md` plus a violation
that exists today. A check nobody has seen fire is a guess.

## Trigger

`extensions/harness_lint.ts` is installed into `~/.pi/agent/extensions/` by
[install.py](../install.py). After a run it lints the files this session
edited, and when something is found it appends one message and continues the
agent once, so the agent fixes its own output before you see it. It stops after
three nudges, skips findings it already reported, and never looks at files the
session did not touch - a repo full of old findings must not nag every run.

## Private checks

Checks that encode machine-specific rules belong in `~/repos/agent2/harness/checks/`
(private repo), not here. The dispatcher picks that directory up only when it
exists, the same conditional rule `common.md` uses for `agent2/AGENTS.md`.
