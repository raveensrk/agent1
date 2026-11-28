# Git hooks

agent1 ships git hooks for every repo on the machine, not just its own. They are
enabled once, globally:

```
git config --global core.hooksPath ~/repos/agent1/harness/githooks
```

## Lint only

Hooks only lint: they never build, install or test
([git.md](../rules/git.md), Git hooks lint only). A hook that refuses is a real
problem to fix, never one to skip with `--no-verify`. Apps are installed by
hand, not from a hook.

Two hooks have rules of their own:

- **commit-msg** refuses a message with an AI co-author trailer: a
  `Co-authored-by:` line naming an AI tool (Claude, Codex, Copilot, Gemini and
  others). A human co-author passes, and comment lines are ignored. Claude Code's
  own attribution is off, but other harnesses can still write one, so git itself
  refuses it.
- **pre-push** keeps a private repo off any remote not allowed for it. A repo
  opts in with `git config repo.private true` and one
  `git config --add repo.allowRemote <url>` per allowed remote. A push to any
  other URL is refused. A GitHub URL must also be a private repo, checked with
  the GitHub CLI; when that cannot answer, the push is refused, because an
  unchecked push of private data cannot be undone. A repo without the flag is
  never touched.

## Chaining

A global hooks path hides each repo's own `.git/hooks`. So every hook here -
pre-commit, commit-msg, post-commit, post-merge, post-rewrite and pre-push -
runs the repo's own hook of the same name when one exists and is executable,
with the same arguments and input: after its own check for commit-msg and
pre-push, and as its only job for the rest. A hook never runs itself.

A repo that wants its own hooks instead can set a local `core.hooksPath`; the
[auto-install git hook prompt](../prompts/auto_install_git_hook.md) does that.

______________________________________________________________________

[Previous: Harness checks](04_harness_checks.md) · [Next: The plugin and the pi package](06_plugin_and_pi_package.md)
