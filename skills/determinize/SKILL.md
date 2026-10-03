---
name: determinize
metadata:
  scope: global
description: Scan a directory and its agent instruction files, turn every rule a program can decide into a check, a guard or a git hook, and thin the instructions to decisions and routing. Use when the user says determinize, make this rule deterministic, convert these rules to checks, add a linter or a hook for a rule, thin an AGENTS.md, or asks which rules could be code instead of prose. Prints the per-rule plan and waits for a yes before writing.
argument-hint: "[directory]"
---

# Determinize

A rule a program can decide is the program, not prose. This skill scans one
directory's instruction files, classifies every rule, builds what is missing,
and leaves the prose carrying only decisions and routing.

The rule itself lives in [common.md](../../common.md). The check and guard
contracts, and the wiring for every harness, live in
[harness/README.md](../../harness/README.md) and
[references/harness_wiring.md](references/harness_wiring.md).

## 1. Inventory

```
python3 scripts/inventory.py [DIR]
```

Read-only, defaults to the current directory. Prints the git root, the
instruction files (`AGENTS.md`, `CLAUDE.md` and the docs they read at session
start) with line counts, the checks that already exist, the guards and git hooks
already wired, and the harnesses installed.

Then read every instruction file **in full**. The classification is judgement;
the script only removes the hand-rolled discovery.

## 2. Classify every rule

For each rule, ask: can a program decide this?

| Shape | When | Home |
| --- | --- | --- |
| Check | decidable after the work | `scripts/checks/` in the repo, or agent1/agent2 `harness/checks/` |
| Guard | a prohibition that must never happen | a guard script, reached through the hook contract |
| Generator | a fixed file shape the agent hand-rolls | a small script or template |
| Jev | a semantic answer that is a label or a score, with a threshold | the typesafe-ai skill |
| Prose | taste, judgement, or no falsifier | stays, with a pointer line |

Hard rules:

- Pin the tool and the ruleset. "Follow the CommonMark spec" has no falsifier,
  every string is valid CommonMark; `mdformat --check` does. Say "this stays
  prose" instead of writing a check that cannot fail.
- Never fake a judgement rule with a regex or an LLM judge.
- Scope decides the home: true in every repo goes to `~/repos/agent1/harness/checks`,
  only on this machine to `~/repos/agent2/harness/checks`, only here to
  `<repo>/scripts/checks`. A repo-local check overrides a machine-wide one by id.
- A rule that already has a working check is a wiring fix, not a new check. Run
  `python3 ~/repos/agent1/harness/lint.py --list` before proposing anything.

## 3. Gate the plan

Run every proposed rule through the gate before offering it: it names a real
violation seen today, a command or read proves a violation, it says where it
applies, and it does not contradict an existing rule.

Then print the plan as a table - rule, shape, artifact path, what the prose
becomes - and wait for a yes. Nothing is written before the yes.

## 4. Build

- **Check**: a file in a `checks/` directory with a `# harness-check:` header
  ([harness/README.md](../../harness/README.md)). Findings print as
  `path:line: message`, the message ends with the fix as a command, the check
  exits 0. Run it over the whole population first: its first full run must pass
  on every instance or it is reporting its own bugs, and it must fire on the
  violation that motivated it. Paste that output in the report.
- **Guard**: a script that reads hook JSON on stdin, exits 2 to block, and
  prints the reason and the replacement on stderr. Test the payload shapes and
  the fail-closed parse error.
- **Wiring**: the exact block per harness is in
  [references/harness_wiring.md](references/harness_wiring.md). Write it for the
  harnesses installed on this machine, into the repo. For a harness that is not
  installed, emit the block in the report; write it only when asked with
  `--all-harnesses`.
- **The floor**: a repo-local git hook under `.githooks/` fires for every
  harness and for a human, so a prohibition that must hold everywhere gets one,
  chained to the same guard script.
- Leave one runnable check behind for every non-trivial script.

## 5. Thin the prose

Replace each converted rule with one pointer line: the decision, plus the path
of the program that decides it. Delete the detail, the examples, and the
restated rule - the check is the source of truth now. Keep the prose only for
what the check cannot say. Never leave both.

## 6. Prove it and report

Run, in the target: the new checks over the whole population, each new test, and
`python3 ~/repos/agent1/harness/self_check` when the target is one of my repos.
Report a table: rule, shape, artifact, proof (the command and its output), and
every rule that stayed prose with the reason. End with what a fresh session now
gets for free.

## Never

- Never write a check without watching it fire on a real violation.
- Never convert a judgement rule for the sake of coverage.
- Never grow an instruction file: a converted rule moves out, it does not move
  down.
- Never rewrite instruction files before the plan is approved.
