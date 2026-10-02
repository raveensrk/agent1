---
name: learn-from-session
description: Review the current Pi session as a coach - find patterns, errors, inefficiencies, gotchas and improvements; turn the repeatable ones into deterministic checks in the harness and build them; use Jev for the judgments code can threshold; research better approaches online; interview the user until the goal is clear; write a prioritized report and merge durable rules into an AGENTS.md. Use when the user asks to learn from this session, review how the session went, improve the workflow, update an AGENTS.md, or add a check for a mistake that keeps happening. Asks before writing and shows diffs.
argument-hint: "[path to AGENTS.md]"
---

# Learn from session

A session review that trains future sessions: read the transcript, interview the
user, find the missing signals, research better approaches, rank findings by
impact, write a report, and merge the durable rules into an `AGENTS.md`. The
point is not a prettier rule, it is a session that cannot repeat the mistake.
Nothing is written without approval.

## 1. Read the transcript

Dump the current session (reads `$PI_SESSION_FILE`, else the newest jsonl for
cwd):

```
python3 scripts/session_text.py
```

It prints `[user]`, `[assistant]` and `[tool name]` lines. Read the whole
output. `--path FILE` reads a different transcript.

Then time every call in it, so the cost of the session is a number and not an
impression:

```
python3 scripts/analyze_commands.py --session
```

The script pairs each tool call with its result and prints the wall clock, the
tool time, every call over five seconds, the aborted and failed ones, repeated
calls, and hang-prone command shapes with the fix. A call over five seconds is a
finding; a call over sixty, or one the user aborted, is the first row of the
report. It reads `$PI_SESSION_FILE` by default and exits 2 when a transcript
carries no timestamps.

## 2. Interview, phase one - the goal

Ask questions until all four are clear: the goal of the session, what success
looked like, the constraints, and how the user wants the assistant to work.
One question at a time. Stop when the transcript plus answers leave no
ambiguity about what this session was supposed to achieve.

Every confirmed answer is classified before the session ends: it becomes a rule
(section 10), it becomes a check (section 4), it is explicitly dropped, or it
goes to the report's Open questions because it cannot be made operational. There
is no third state.

## 3. Analyze

Read the transcript for:

- Patterns: repeated mistakes, repeated user corrections, repeated phrasing.
- What failed: each failure, the root cause, and why it failed.
- What passed: each success, and why it worked, so it can be repeated.
- Inefficiencies: wasted steps, slow commands, redundant reads, retries. Time
  them with the script in section 1 rather than judging them by feel.
- Gotchas: non-obvious environment, tool, or format traps.
- Conversation: unclear questions, buried answers, wrong assumptions, missing
  confirmation before risky steps.
- Dev flow: manual steps that could be scripted, missing defaults, bad aliases.
- Repetition: command sequences or manual steps that one small helper script
  would remove. Propose the script with its location, not just the idea.

The talk behind this skill ("Harness Engineering on Rails", Joël Quenneville,
[Rails World 2026](https://rubyonrails.org/world/2026/sessions/harness-engineering))
asks these of every session. Answer each one with a transcript line, not an
impression:

- Where did I have to intervene?
- What signals were missing?
- Was there anything I had to copy back and forth by hand?
- Is there anything in `AGENTS.md` that could be done deterministically instead?
- Did the conversation degrade?
- Could this have been split?
- Are there any mistakes that happened multiple times?

Rank every finding by impact: time lost, error frequency, quality or speed
gain. Impact decides the order of the report.

### Mine the command history

```
python3 scripts/analyze_commands.py --history      # ~/.bash_history by default
```

This one reads what the user typed, which is where the speed and accuracy wins
are. It ranks three things:

- repeated prefixes and exact repeats: the alias, script or prompt template that
  should exist. A prefix typed 181 times is a missing alias, not a habit. An
  exact repeat is also a suspicion that the first run failed; the file has no
  exit codes, so confirm it against the transcript before calling it a retry.
- long one-liners: script candidates.
- hang-prone shapes, each with its fix: recursive grep, an unbounded `find`,
  `curl` without `--max-time`, `tail -f`, `ssh` without `ConnectTimeout`, an
  interactive pager or editor, a server started in the foreground. The shape
  matters when a session replays it, which is what a guard is for.

History on this machine records no durations and no exit codes, so it ranks by
frequency; durations come from the transcript. Two ways to instrument the shell
for timing were probed and rejected: PS0 runs its command substitution in a
subshell, so the start time never reaches the parent, and a DEBUG trap that sets
it stops the prompt from being printed. A verified timing hook is its own task.

### Rule-quality gate

Run every proposed rule through these five checks before proposing it. A rule
that fails any check is reshaped or dropped, never written.

- Evidence: the session ran it and observed the result. No rule from imagination.
- Falsifiable: a command or read proves a violation.
- Scoped: it says where it applies (machine-wide, repo, tool-only).
- Non-conflicting: it agrees with existing rules. A conflict amends one side in
  the same change.
- Supersede-aware: replacing an older rule updates that rule too, and the commit
  message names it.

## 4. Find the missing signals

A finding that ends up as prose is a finding the next session has to remember.
Sort every finding into the talk's grid first, then act on that cell:

| | computational | inferential |
| --- | --- | --- |
| **feedback** (after the work) | lint, test, check - build it | agentic review, this skill |
| **feedforward** (before the work) | generator, template, guard | `AGENTS.md` prose, `SKILL.md` |

Anything a check can decide belongs in a check. Most findings land in one of
three shapes:

- **Lint-shaped**: there is a right answer a machine can compute (an exec bit,
  a bare path, an interpreter that does not exist). Build a check.
- **Guard-shaped**: it should not happen at all, and the tool call can be
  stopped before it does. Build a guard in a pi extension and refuse with the
  replacement command, never a bare "no". Worked example: one `grep -rn` over
  `~/repos` ran 111s of a 137s session and had to be aborted, so
  `harness/extensions/command_guard.ts` now refuses the recursive form and prints
  the `rg` line, with `harness/tests/test_command_guard.ts` as its one runnable
  check. The prose rule keeps only the pointer and the measurement.
- **Generator-shaped**: the file has a fixed shape and the agent hand-rolled it.
  Build a generator or template.
- **Judgement-shaped**: taste, structure, naming, prose quality. This stays a
  rule or a review step. Say so in the report instead of pretending it is
  checkable.

Then:

1. Look for the check or rule that already covers it. `python3 ~/repos/agent1/harness/lint.py --list`
   names every check and its quadrant; read the target file before claiming a
   rule is missing.
2. Decide the scope, which decides the home:
   - true for every repo here - [harness/checks](~/repos/agent1/harness/checks)
     in agent1 (public), see [harness/README.md](~/repos/agent1/harness/README.md)
   - true only on this machine or private - `~/repos/agent2/harness/checks/`
     (private); the dispatcher picks it up when the directory exists
   - true only inside one project - `<repo>/scripts/checks/`, which the
     dispatcher reads from the repo it is run in, and which may override a
     machine-wide check with the same id
   - automatic trigger needed - a pi extension in
     [harness/extensions](~/repos/agent1/harness/extensions), installed by
     [install.py](~/repos/agent1/install.py)
3. Write the check (header + `path:line: message`, see the README), make the
   message carry the fix as a command, then run it over the whole population:
   `python3 ~/repos/agent1/harness/lint.py --repos`. Its first full run must
   pass on every instance or it is reporting its own bugs, and it must find the
   case that motivated it. A check nobody has seen fire is a guess.
4. Report the first-run count in the review. A check that finds 40 old
   violations is a cleanup task, not a check to wire into a trigger; the trigger
   only ever lints the files a session edited.

### Audit the rules corpus

Whole-file, once per target: walk every rule in the target file and ask the
talk's question - could this be decided deterministically? Flag the ones that
are a stale command, a styleguide, or an unverifiable adjective, and propose the
check or generator that replaces them. Worked example, found by
`interpreter_resolves` in this very file: `common.md` pinned a Python version in
its shebang rule, that version is not installed here, and five observed runs died
on `command not found`:

```
#!/usr/bin/env python3.11
```

The check was three lines and the rule is now correct.

When a check takes over a rule, replace the prose with one pointer line naming
the check - do not leave both.

## 5. Signals from Jev

Use Jev for the judgements in this review that are typed: a label, a route, a
score. One batched request carries all four jobs; code owns the thresholds and
the counts.

- Label the transcript: choice per user turn (correction, praise, answer,
  new_goal, off_topic), noul per tool call that looks wasted or retried. Turn
  the talk's questions into numbers: how many interventions, which mistake
  repeated, did it degrade.
- Route each finding to its quadrant: choice over the four cells of the grid
  above, which decides lint, guard, generator or prose.
- Judge the proposed rules: nouls for falsifiable, scoped, evidence-backed, plus
  one choice over the existing rules of the target file to catch a duplicate.
- Score the findings for impact, so the report order comes from numbers.

Constraints, from the model's own docs: it reads literally, so write the exact
criterion in `instructions` and boundary cases in `criteria`; it cannot count,
so count in code and ask one question per item; accuracy falls with a large
state full of irrelevant detail, so send the turn or rule being judged, not the
whole transcript (32k tokens of state per request, $42 per billion input tokens).
A probability near 0.5 makes the judgement an Open question - do not average it
into a verdict.

The batched client lives beside this skill, so the questions are never retyped:

```
python3 scripts/jev_signals.py --session --rules ~/tmp/review/rules.json
```

It reads the transcript through `scripts/analyze_commands.py`, builds the state
and asks all four families in one request: a label per user turn, a waste noul
per slow, aborted, failed or waiting call, a quadrant and an impact per finding,
and four nouls per candidate rule. `--rules` is a JSON file of
`[{"id": "R1", "text": "..."}]`, one entry per rule the review proposes. Counts
come out of the code, never asked of the model. Two-word turns label at 0.36
confidence from bare text and 0.89 once annotated, so pass `--turns turns.json`
when precision matters; every answer under 0.6 confidence goes to the report's
Open questions. Answers below 0.6 are the ones to hold loosely.

It posts to the same systemone endpoint as
[jev.py](~/repos/agent2/fast-mac-use/scripts/jev.py) (private config). With no
`TYPESAFE_API_KEY` it says so rather than guessing: make the four judgements in
prose and record in the report that they were not machine-labeled.

## 6. Research

Proactively search when a better approach is suspected, even if the session
succeeded. Prefer official docs. Verify the suggestion applies to the installed
versions before proposing it, and cite the source link.

## 7. Report

Always write the report to `~/tmp/`. If the user declines a report, keep the
findings in chat and skip the file.

File: `~/tmp/session_review_<YYYY-MM-DD>.md`, appending `_2`, `_3` when taken. A
prioritized list, highest impact first, one line per finding:

```
- [high] <finding> - quadrant: <feedback|feedforward>/<computational|inferential> - evidence: <quote or line from transcript> - fix: <action> - source: <link>
```

Include what worked, not only what failed. Then a `Signals` section: the Jev
labels with their probabilities and the counts they produce. Then a `Checks`
section: every check this review built or proposed, its path, its first-run
count over the full population, and whether its trigger is wired. End with
`Open questions` for anything only the user can answer, including every
low-confidence Jev judgement.

## 8. Interview, phase two - improvements

Ask about each proposed improvement before writing it anywhere: keep, drop, or
change. One question at a time. Keep only what the user confirms. A proposed
check is asked separately from a proposed rule, because the check is code and
the rule is prose.

## 9. Pick the AGENTS.md target

If the user passed a path, use it. Otherwise list candidates and ask:

1. `~/repos/agent1/common.md` - canonical global rules, read every session.
2. `~/AGENTS.md`, if it exists - machine-wide, points at common.md.
3. `~/.pi/agent/AGENTS.md` - agent-dir scope, points at common.md.
4. `AGENTS.md` in cwd, if it exists - project scope.
5. Every `AGENTS.md` from cwd up to `git rev-parse --show-toplevel` (or `/`).

Show each candidate with a one-line summary of what it already covers. Read
the chosen file fully before editing. The chosen file's git history is the
decision log: the scope lives in the rule, the why lives in the commit message.

## 10. Merge

- Fit each durable rule into an existing section. Match the file's voice,
  heading depth, and punctuation. Plain hyphens only.
- Create a new section only when no existing section fits. Name it after the
  topic, not the session.
- Add or minimally amend. Never reword, reorder, or delete existing content
  unless a check has taken the rule over, and then leave the pointer line.
- Durable rules only: corrections, conventions, commands, gotchas. Task-specific
  suggestions stay in the report.
- If the session produced no durable rules, say so and write nothing.

## 11. Approve, then write

Produce the diff from a temp copy so the real file stays untouched until
approval:

```bash
cp <target> ~/tmp/review/<name>.new       # 1. copy the target
# 2. apply the intended edits to the copy
diff -u <target> ~/tmp/review/<name>.new  # 3. the approval artifact
```

Show that diff and wait for an explicit yes. On approval, apply the same edits
to the real file, re-read the changed sections, and report what changed with
line numbers. Inside a git repo `git diff` is an acceptable fallback. Checks are
code: show them, run their tests, and run them over the full population before
they count as approved.

## 12. Close follow-ups

Every item found mid-session that is not the main task gets an outcome before
the session ends: fix it now, record it in the report's Open questions, or drop
it with a reason. Nothing is left carried only in chat.
