# Install and uninstall

Install registers the clone with every harness installed on the machine;
uninstall reverses it. Both are dry runs by default and print the plan; an
apply flag writes it, and a check flag exits 1 when the harnesses drifted from
the repo.

## What install does

For each harness, in order:

- **pi.** Skipped when pi's home folder is missing, or the repo has no `pi` key.
  Otherwise the clone's path, written with `~`, is added to `packages` in pi's
  settings if no entry already resolves to it.
- **Claude Code.** Skipped when Claude's home folder is missing, or the repo has
  no marketplace manifest. Otherwise the marketplace is added (or re-added when
  it points elsewhere) with the Claude CLI, and each plugin is installed at user
  scope, or enabled if installed but off. State is read from Claude's plugin
  files, so a dry run and the check need no CLI.
- **Codex.** Skipped with a note: not wired yet.

Then links that the older symlink installer made into this repo, from the
harnesses' skill and command folders, are moved to the Trash.

## Rules it keeps

- Idempotent: a second run changes nothing.
- Touches only the keys this repo owns; every other key, including what a
  harness writes at runtime, is left alone.
- Never writes through a settings file that is still a symlink: that file
  belongs to the dotfiles installer, which must run first. Such a file is a
  conflict, and install exits 1.
- A `git pull` in the clone updates every harness at its next start.
- After an apply that changed something it says to restart pi and Claude Code.

## Shared with other repos

The mechanics are one library that every repo shipping skills calls from its own
small install entry point, passing its repo path and arguments. Uninstall is the
same call with an uninstall flag.

## What install does not do

It does not set the global git hooks path ([Git hooks](05_git_hooks.md)), and it
does not add the rules import to a project's instruction file. Both are one-time
steps in the [manual](../manual/01_install.md).

______________________________________________________________________

[Previous: The plugin and the pi package](06_plugin_and_pi_package.md) · [Next: Publishing](08_publishing.md)
