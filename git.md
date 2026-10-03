# Git

Commits and pull requests. Loaded from [common.md](common.md) at session start.

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

## Pull Requests

PR descriptions should explain what changed, why the change is needed, and the intent or constraints a reviewer cannot infer from the diff alone. Keep simple PRs brief, but give non-trivial changes enough context to stand on their own. Skip file-by-file inventories, test result summaries, and anything obvious from the code itself.
