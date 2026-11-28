# Decisions

Each decision, the reason, and where it is explained.

- **Load in place, never copy.** Copies drift; each harness's native loader
  reads the clone, so one `git pull` updates all of them.
  [The plugin and the pi package](06_plugin_and_pi_package.md).
- **Put rules in the prompt, not in a read.** Named files were measured being
  skipped. [How rules load](02_how_rules_load.md).
- **Checks over prose.** A rule a program can decide is a check, guard or hook;
  prose keeps judgement. [Harness checks](04_harness_checks.md).
- **Lint only what the session touched.** Old findings in a repo must not nag
  on every run. [The trigger](04_harness_checks.md#the-trigger).
- **A failed check is not a pass.** It is reported as a failure, once per check
  and repo. [The trigger](04_harness_checks.md#the-trigger).
- **Every refusal steers.** Guard and check messages carry the fix.
  [Guards](04_harness_checks.md#guards).
- **One rule, two harnesses.** Claude hooks call the pi extensions' code.
  [The hook wiring](06_plugin_and_pi_package.md#the-hook-wiring).
- **Git hooks lint only, for every repo.** Building or installing from a hook
  surprises; a global hooks path reaches every repo and chains to its own.
  [Git hooks](05_git_hooks.md).
- **Public here, private in agent2.** Machine-specific rules, checks and data
  live in the private repo, picked up only when it exists.
  [Private checks](04_harness_checks.md#private-checks).
- **The voice switch beside its rule.** Turning it off never edits a rules
  file. [The telegraph voice](02_how_rules_load.md#the-telegraph-voice).
- **Skill folders use hyphens.** The Agent Skills format requires it.
  [Skills](03_skills.md).
- **Prompt and note files keep their names.** pi slash commands and other repos
  use them, so their contents pages list them in reading order instead of
  numbering them. Rule files keep topic names because they are looked up and
  linked by topic.
- **Everything to read lives in docs/.** One place to look, and one book to
  publish. [Publishing](08_publishing.md).
- **Retire to the archive.** Retired skills, commands and rules move out of
  every load path but keep their history.
  [What agent1 is](01_what_agent1_is.md#layout).

______________________________________________________________________

[Previous: Publishing](08_publishing.md) · [Back to contents](README.md)
