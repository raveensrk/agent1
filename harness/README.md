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
node --experimental-strip-types harness/tests/test_command_guard.ts
bash harness/self_check                 # every suite, then the full-population lint
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
- Print findings as `path:line: message` and exit 0, with line 1 for a
  whole-file finding. Nothing on stdout means clean. A nonzero exit, or a
  stdout line in any other form, means the check itself is broken.
- End the message with the fix, as a command when there is one. A signal that
  does not steer sends the next attempt down the same dead end.

Check the same mistake by hand first: a rule in `common.md` plus a violation
that exists today. A check nobody has seen fire is a guess.

## Trigger

`extensions/harness_lint.ts` ships with the rest of `harness/extensions/` - pi
loads it live from this repo via the local package declared in the dotfiles'
`settings.json` (see [harness_wiring.md](../skills/determinize/references/harness_wiring.md)).
After a run it lints the files this session
edited, and when something is found it appends one message and continues the
agent once, so the agent fixes its own output before you see it. It stops after
three nudges, skips findings it already reported, and never looks at files the
session did not touch - a repo full of old findings must not nag every run.

`extensions/telegraph.ts` carries the voice rule itself, so the rule and its
switch cannot drift apart. The rule text lives in `extensions/telegraph.md` - not
in `experimental.md`, where turning it off meant editing a rules file. When the
switch is on, the extension appends the rule to the prompt; `/telegraph off`
drops it from the next request, and off is persisted in
`~/.local/state/agent1/telegraph.json`, one switch for every harness.

`extensions/voice_score.ts` is the signal for that rule, asked for by hand and
never on its own. `/voice-score` sends the last run's thinking blocks and reply
to [Jev](https://docs.typesafe.ai); `/voice-score -0` walks every run of the
session in turn. Each scored run draws two lines at the end of the transcript:
`voice  think 2.8/3  reply 2.2/3` and `tokens think 1.4/3  reply 2.6/3`. Both
lines score 0 to 3 and draw the max with every number. The second is
the token-efficiency score - Jev's 0-3 for the block times the probability it
missed nothing - and the expanded view shows the measured evidence next to it:
filler count, repeated spans, chars and estimated tokens. One row per scored
block is appended to `~/.local/share/voice_score/scores.jsonl`, machine-local,
for recalibration from real turns. The runs come from the session branch, so a
turn that finished before the command was typed is scoreable, and a turn nobody
asks about costs nothing. Display only: nothing is corrected, the entry never
reaches the model's context, and each run asked about costs one classifier call.
Both threshold pairs, their measured gaps and the calibration behind them are
documented in the extension.

`extensions/call_score.ts` scores the other half of the bill: every tool call of
the run gets Jev's necessity score times a result gate, drawn as a third line,
`calls  1.5/3 2.8/3 0.4/3 +9`, with repeats, subsumed reads and oversized
results measured from the transcript and shown in the expanded view. Its bands
are parked: the 2026-10-04 calibration found no gap to sit them in, so the
numbers draw dim until the ledger says otherwise. `/call-score off` stops the
call; it shares the voice_score ledger and costs one classifier call per run.

## Claude Code

[hook.ts](hook.ts) runs the same exported functions as the pi extensions, once
per Claude hook event, wired by the plugin's [hooks/hooks.json](../hooks/hooks.json):

| Event | `hook.ts` | pi extension |
| --- | --- | --- |
| `SessionStart` | `rules` | `rules_context.ts` + `telegraph.ts` |
| `PreToolUse` Bash, Edit | `guard` | `command_guard.ts`, `edit_guard.ts` |
| `PostToolUse`, `PostToolUseFailure` | `nudge` | `failure_nudge.ts` |
| `Stop` | `lint` | `harness_lint.ts` |

The rule lives in the extension; `hook.ts` only translates the event. Change a
rule there and both harnesses enforce it. Each hook costs ~0.1 s of node
startup (measured 2026-10-08). Claude's `/telegraph` command
([commands/telegraph.md](../commands/telegraph.md)) flips the same switch as
pi's. Check: `node --experimental-strip-types harness/tests/test_hook.ts`.

## Guards

A guard refuses a tool call before it runs, where the lint reacts after the files
are written. There are two shapes here.

`extensions/command_guard.ts` refuses the commands that hang, both measured
directly. One recursive `grep -rn` over `~/repos` ran 111 s of a 137 s session
(17 GB, 169,203 files) and had to be aborted, while `rg -l` answered in 2.6 s.
And `~/.bash_history` holds 9 `curl ... | sh` installs with no `--max-time`,
where a dead host blocks forever. Its check is
`node --experimental-strip-types harness/tests/test_command_guard.ts`.

A second rule could decide in Python and be called from the harness hook
contract - hook JSON on stdin, exit 2 blocks, stderr is the reason. Claude Code,
Codex, Cursor and Gemini CLI all speak it, so one file serves all four. The exact
block for each is in
[references/harness_wiring.md](../skills/determinize/references/harness_wiring.md).

A guard message always carries the replacement command. Blocking without
steering sends the next attempt down the same dead end - the same rule applies
to a check's message, and to a guard's.

## Private checks

Checks that encode machine-specific rules belong in `~/repos/agent2/harness/checks/`
(private repo), not here. The dispatcher picks that directory up only when it
exists, the same conditional rule `common.md` uses for `agent2/AGENTS.md`.

The reverse split is `nested_git_repo.py`: the rule is general, so the check is
public here, while the allowlist of internet clones it reads names this
machine's repos and stays at
`~/repos/agent2/harness/data/nested_repo_allow.txt`. With that file absent the
check runs with no allowlist.
