# Git

Commits and pull requests.

## Commits and PR Titles

Never add an AI co-author trailer.

### Commit Conventions

Use Conventional Commits for messages and PR titles: `type(scope): summary`. Omit scope when spanning multiple scopes.

See: https://www.conventionalcommits.org/en/v1.0.0/

Types are feat, fix, docs, style, refactor, perf, test, build, ci, chore, and revert.

Scopes are optional; use the affected package or area when helpful, e.g. core, web, tui, app, design, verif, desktop, etc.

### Example

- fix(tui): simplify thinking toggle styling
- docs: update contributing guide
- chore(verif): rename variables

## Landing a Branch

Never suggest opening a PR. In every repo, once work is committed on a branch other than main, suggest landing it locally as one step and wait for a yes:

1. Check the main checkout is on main and clean. If it is not, stop and say what is in the way; never stash, switch branches or touch that work.
2. If main has moved, rebase the branch onto main.
3. Fast-forward main to the branch from the main checkout: `git merge --ff-only <branch>`. No merge commits, no squash.
4. Remove the worktree if there is one: `git worktree remove <path>`.
5. Delete the branch: `git branch -d <branch>`.

Run steps 3 to 5 from the main checkout, not from inside the worktree being removed. Do not push; pushing is a separate request.

## Pull Requests

Open a PR only when asked. PR descriptions should explain what changed, why the change is needed, and the intent or constraints a reviewer cannot infer from the diff alone. Keep simple PRs brief, but give non-trivial changes enough context to stand on their own. Skip file-by-file inventories, test result summaries, and anything obvious from the code itself.

## Command gotchas

- For Git operations, use Git CLI and preserve unrelated staged and unstaged changes.
- `git mv` needs its destination directory to exist. `mkdir -p` the parent first, or the move fails and a `set -e` batch stops there.
