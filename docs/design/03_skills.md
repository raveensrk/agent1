# Skills

A skill is a task's instructions packaged so any harness can load it on demand.
agent1's skills use the open [Agent Skills](https://agentskills.io) format: one
folder per skill, holding a skill file with a name and a description in its
front matter, plus any scripts, references and tests it needs.

Skill folders use hyphens (`git-report`), not the snake_case the rest of the
repo uses, because the format requires the folder name to match the skill's
`name`. A check confirms that pair; the file-naming check exempts skill
folders for the same reason.

## The index

The skills folder has one index page listing every skill with one line on what
it does, in name order. It also lists skills that live in other repos
(task-router-2, tutor), with the command that installs each. The pi package
leaves the index out of its skill paths, so it is never loaded as a skill.

The current skills and what each does are on that index page,
[skills/index.md](../../skills/index.md); this book does not repeat the list.

## Install

Skills are not copied anywhere. Each harness loads the skills folder from the
clone: pi through the package manifest, Claude Code through the plugin. A
`git pull` updates every harness at its next start. The details are in
[The plugin and the pi package](06_plugin_and_pi_package.md).

A skill that is retired moves to the archive, outside every load path, so it
stops loading but keeps its history.

______________________________________________________________________

[Previous: How rules load](02_how_rules_load.md) · [Next: Harness checks](04_harness_checks.md)
