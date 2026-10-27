---
name: learn-from-failure
description: Quick failures-only pass over the current Pi session - scan failed tool calls, report what failed, why, and the fix, apply approved fixes and verify them, optionally land durable rules. Deep analysis (root-cause chains, cross-failure patterns, web research on the exact error string) only when the user says "deep". Use when the user says learn from failure, /learn-from-failure, what failed, why did that fail, fix that failure, or after repeated tool errors. Asks before writing anything.
argument-hint: "[deep]"
---

# Learn from failure

Lean sibling of learn-from-session: hard errors only, this session only, fix
now. A hard error is a tool result pi marked `isError` - non-zero bash exit,
tool rejection, guard block, edit mismatch. No judgment calls in detection.
Recovered failures count and are marked `already fixed`. Deep analysis runs
only when the user says "deep".

## 1. Scan

```
python3 scripts/scan_failures.py
```

It reads `$PI_SESSION_FILE` by default; `--path FILE` reads another
transcript, `--json` emits structured output. Read the whole output. If it
finds zero failures, say so and stop - there is no report to invent.

## 2. Report

Numbered list in chat, no files. One entry per failure:

```
1. bash - grep -rn "pattern" ~/repos
   failed: Blocked - recursive grep (command_guard)
   why: used grep -r; the guard demands rg with a bounded path
   fix: rerun as rg -n "pattern" ~/repos
   status: open
```

- what failed: tool, exact arguments, exact error, quoted from the scan.
- why: one line, the cause. Inferred only from the error text and the
  surrounding transcript; when the cause is not visible, say "cause not
  visible" instead of guessing.
- fix: the concrete replacement call or edit.
- status: `open`, or `already fixed` with how the session recovered.

Bash error text can be plain stdout when a command exits non-zero at the
end, for example a final `grep` with no match; check the trailing exit-code
line before calling it a failure.

## 3. Approve, fix, verify

Wait for the user to name numbers: "fix 1, 3". Then:

1. Apply each named fix.
2. Verify each: rerun the failed action or its check and show the result.
3. A fix that fails verification is reported as failed, never marked done.

## 4. Durable, rule-shaped fixes

After applying fixes, offer the durable landing per rule "shape decides":

- Decidable after the work: a check in that repo's harness checks, wired
  into its lint runner.
- Needs judgment: one line in that repo's AGENTS.md.

Ask before each write, show the diff, commit as built. Never two homes for
one rule.

## 5. Deep mode

Only when the user says "deep" in the invocation. Then, on top of the report:

- Root-cause chains: why the wrong assumption entered, not only the error.
- Cross-failure patterns across the session.
- Web and docs research on the exact error string.

No second model, no subagents. Deep mode changes the analysis, never the
approval flow: fixes are still applied only on named numbers.
