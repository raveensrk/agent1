# Harness checks

The harness is the deterministic half of agent1. Its model is a linter like
Rubocop: one command, every rule, here language agnostic. The rule that makes it
pay is the one from [What agent1 is](01_what_agent1_is.md): anything in the
prose that a check can decide belongs in a check.

## Quadrants

Every signal sits in one of four quadrants, from the same talk:

|                                   | computational                 | inferential                                |
| --------------------------------- | ----------------------------- | ------------------------------------------ |
| **feedback** (after the work)     | linters, tests, these checks  | agentic review, a learn-from-session skill |
| **feedforward** (before the work) | generators, templates, guards | instruction prose, a skill file            |

Each check declares its quadrant in its header, and the list command shows it.

## The lint command

One command runs every discovered check. A check is an executable script in a
checks folder. Its first lines carry one header comment:

```
# harness-check: {"id": "my_check", "applies": ["*.py", "!**/vendor/**"],
#                 "quadrant": "feedback/computational"}
```

The contract:

- `applies` are fnmatch globs against the repo-relative path or the basename;
  a leading `!` drops a path. No `applies`, or only `!` globs, means every file
  not dropped.
- The dispatcher passes the candidate file paths on stdin, one per line, and
  runs the check with the repo root as its working directory.
- A check prints findings as `path:line: message` and exits 0, with line 1 for
  a whole-file finding. Nothing on stdout means clean. A path may hold a colon,
  but never one followed by whitespace.
- A nonzero exit, or a stdout line in any other form, means the check itself is
  broken. It is reported as a check failure, never as a finding.
- A message ends with the fix, as a command when there is one. A signal that
  does not steer sends the next attempt down the same dead end.

Adding a check is dropping a file in the folder; nothing else changes. The
dispatcher looks in three places: agent1's own checks, the private agent2
repo's checks when that repo exists, and the checked repo's own checks folder.
It skips files over 1 MB.

It can check a whole repo (tracked plus untracked, not ignored files), only what
changed against HEAD, named files, or every git repo under `~/repos`. Exit 0 is
clean, 1 findings, 2 a check failed to run.

Before writing a check, find the same mistake by hand: a rule that says it, and
a violation that exists today. A check nobody has seen fire is a guess.

## Private checks

Checks for machine-specific rules belong in agent2, the private repo, not here.
The reverse split also happens: the nested-git-repo rule is general, so its
check is public here, while its allowlist of internet clones names this
machine's repos and lives in agent2. With the allowlist absent the check runs
with none.

## The trigger

After a run, the trigger lints only the files this session edited. When it finds
something it appends one message and continues the agent once, so the agent
fixes its own output before the user sees it. It stops after three nudges per
session, skips findings it already reported, and never looks at files the
session did not touch: a repo full of old findings must not nag on every run.
The full-population lint stays a deliberate act.

A check that failed to run comes back the same way, one line each in the form
`lint: check <id> failed in <root>: <error>`, because a failed check is not a
pass. It is reported once per check and repo, whatever its error says, so one
broken check cannot spend every nudge. A lint run that times out, crashes or
prints output that is not JSON comes back as a failure of the lint itself,
never as a clean run.

## Guards

A guard refuses a tool call before it runs, where the lint reacts after the
files are written. Two guards exist:

- **The command guard** refuses commands that hang, both measured. One
  recursive grep over `~/repos` ran 111 s of a 137 s session (17 GB, 169,203
  files) and was aborted, while ripgrep answered in 2.6 s. And the shell
  history held 9 `curl ... | sh` installs with no time limit, where a dead host
  blocks forever.
- **The edit guard** refuses an edit whose old text is not in the file exactly
  once. In one measured session 3 of 54 edits failed that way, one aborting a
  whole batch. The refusal prints the nearest text with line numbers, which is
  the read the rule asks for, so the next attempt is right. An edit that asks
  to replace every occurrence is exempt.

A guard message always carries the replacement command, for the same reason a
check message carries its fix. A guard can also be written once in any language
behind the common hook contract - event JSON on stdin, exit 2 blocks, stderr is
the reason - which Claude Code, Codex, Cursor and Gemini CLI all speak. The
exact wiring for each is in the determinize skill's
[harness wiring reference](../../skills/determinize/references/harness_wiring.md).

## The failure nudge

One hard tool error is noise; two in a row is a pattern. When the streak reaches
two, the user gets one line offering to learn from the failure. It stays quiet
until a success resets the streak, and it runs only in interactive sessions.

## Scores (pi only)

Two pi-only signals score the agent's own output with Jev, a TypeSafe
classifier ([docs](https://docs.typesafe.ai)). Both are display only: nothing is
corrected and nothing reaches the model's context.

- **Voice score** scores a run's thinking and reply for the telegraph voice,
  drawn as `voice think 2.8/3 reply 2.2/3`, and for token efficiency (Jev's 0-3
  times the probability nothing was missed), drawn as `tokens think 1.4/3 reply 2.6/3`. The expanded view shows the evidence: filler count, repeated spans,
  characters and estimated tokens. `/voice-score` scores the last run,
  `/voice-score -0` every run of the session; automatic scoring is off until
  `/voice-score on`. Runs come from the session branch, so a finished turn is
  still scoreable, and a turn nobody asks about costs nothing.
- **Call score** scores every tool call of a run for necessity times a result
  gate, drawn as `calls 1.5/3 2.8/3 0.4/3 +9`, with repeats, subsumed reads and
  oversized results measured from the transcript. Its bands are parked: the
  2026-10-04 calibration found no gap to set them in, so the numbers draw dim.
  `/call-score` scores the last run; automatic scoring is off until
  `/call-score on`.

Each scored block appends one row to a machine-local ledger under
`~/.local/share/voice_score/`, for recalibration from real turns. Each run asked
about costs one classifier call. The thresholds and their calibration are
documented in the extensions themselves.

## Other pi extensions

pi also gets a reminder when its own version changes (the first run only records
a baseline), and an optional model and thinking-level picker at session start,
which the package leaves out by default.

______________________________________________________________________

[Previous: Skills](03_skills.md) · [Next: Git hooks](05_git_hooks.md)
