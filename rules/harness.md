---
last_reviewed: 2026-11-02
---

# Harness

The harness is everything around the model that turns a rule into a signal:
checks, generators, hooks and guards. Prose is the fallback, not the default.
The grid, the commands and the check contract live in
[harness/README.md](../harness/README.md).

- A rule a check can decide belongs in a check, not in prose. Write it in
  [harness/checks](../harness/checks), run by [lint.py](../harness/lint.py), and
  keep the prose rule only if it says something the check cannot.
- Deterministic first, and pick the shape the rule needs: decidable after the
  work, a check; a falsifier pinned to a tool, like `mdformat --check` (the
  pinned pair lives in
  [mdformat_check.py](../harness/checks/mdformat_check.py)); judgement stays
  prose, never faked with a regex, and Jev only when the answer is a label or a
  score with a threshold. Convert with the
  [determinize](../skills/determinize/SKILL.md) skill.
- A skill is discovered by its frontmatter, so a sweep that eats it is silent:
  [skill_frontmatter.py](../harness/checks/skill_frontmatter.py) wants `name`
  and `description` in every `SKILL.md`, and the directory name to match it.
- After you create or edit an `.svg`, lint it before you call it done:
  `python3 ~/repos/agent1/harness/lint.py FILE.svg` (xmllint, svglint, then
  Prettier `--check`; run the `--write` command a finding prints).
  [svg_lint.py](../harness/checks/svg_lint.py) also runs on every SVG the
  session touched when the run stops; render it with `rsvg-convert` too when how
  it looks matters.
- Instruction files stay thin: decisions and routing, nothing else. The file
  names the decision and the program that decides it; the detail lives in an
  on-demand doc or inside the check.
- A check that walks the filesystem confirms its root is a repo root first: the
  dispatcher falls back to the working directory when the edited files are in no
  repo, and a check that walked it found a file in Trash.
- The deterministic layer is harness-agnostic: one check command, one guard
  contract, committed in the repo. Only the wiring is per harness.
- A mistake that happened twice means a signal is missing, not that a rule was
  too quiet. Ask "how could this be the last time?" and name the check,
  generator or hook that will catch it next time, before you touch rule text.
- A refusal, block or guard always prints the exact replacement command with its
  syntax. Never block without steering; the next attempt must be the right one.
- When code needs a semantic decision (is this a refund request, is this line
  relevant), call Jev for a typed, threshold-able answer instead of asking an
  LLM for JSON. See [typesafe-ai](~/.agents/skills/typesafe-ai/SKILL.md).
