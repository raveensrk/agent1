# Add a skill

1. Make a folder under `skills/` with a hyphenated name, the same as the skill's
   `name` (`git-report`).
2. Write its `SKILL.md`: front matter with `name` and a `description` that says
   what it does and when to use it, then the instructions. Put any scripts in
   `scripts/` inside the folder.
3. Add one line for it to [skills/index.md](../../skills/index.md), in name
   order.
4. Lint it: `python3 harness/lint.py skills/<name>/SKILL.md`.
5. Start a new session, or run `/reload-plugins` in Claude Code. No install
   step: both harnesses read the folder live.

To retire a skill, move its folder to `archive/skills/` and drop its index
line.

The format is in [Skills](../design/03_skills.md).

______________________________________________________________________

[Previous: Add a rule](03_add_a_rule.md) · [Next: Add a check](05_add_a_check.md)
