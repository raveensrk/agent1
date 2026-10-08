# agent1

Reusable AI agent instructions. Import them into your own project instead of
copying and drifting.

## 1. Clone

```bash
git clone https://github.com/raveensrk/agent1.git ~/repos/agent1
```

Any path works. The rest of this file assumes `~/repos/agent1`.

## 2. Point your agent at it

| Agent | Scope | File to edit |
|---|---|---|
| Claude Code | one project | `<project>/CLAUDE.md` |
| Claude Code | every project | `~/.claude/CLAUDE.md` |
| Codex | one project | `<project>/AGENTS.md` |
| Codex | every project | `~/.codex/AGENTS.md` |
| pi | one project | `<project>/AGENTS.md` |
| pi | every project | `~/.pi/agent/AGENTS.md` |

### Claude Code

Claude Code expands `@` imports, so one line pulls the whole file in:

```markdown
@~/repos/agent1/common.md
```

### Codex

Codex has no import syntax - it reads `AGENTS.md` verbatim. Give it an
instruction it can act on instead:

```markdown
At session start, read `~/repos/agent1/common.md` and follow it.
```

### Both in one project

Keep the rules in `AGENTS.md` and make `CLAUDE.md` a one-line pointer, so the
two agents never drift apart:

```markdown
@AGENTS.md
```

## Path rules

- Use a `~/` path. `$HOME` is not expanded, and `/Users/<name>/` breaks on
  another machine.

- Confirm it resolves before you rely on it:

  ```bash
  ls ~/repos/agent1/common.md
  ```

  A wrong path fails silently. The agent told to read a missing file just
  carries on without the rules.

## 3. Verify it loaded

Start a session and ask:

> What punctuation rule do I follow for dashes?

Correct answer: plain hyphens only, never em dashes or en dashes. Any other
answer means the import did not load.

## Files

| File | What it covers |
|---|---|
| `browser.md` | Browser and computer use rules |
| `cli.md` | CLI app conventions: help, flags, one help table |
| `code_style.md` | How to write code |
| `common.md` | Session start, working style, output style, and the pointer hub for topic rules |
| `emoji_legend.md` | Status emoji vocabulary for agent reports |
| `external.md` | Probes, live external accounts, credentials |
| `git.md` | Commits and pull requests |
| `harness/` | Deterministic checks, one command to run them, and the pi trigger that reacts to findings (see [harness/README.md](./harness/README.md)) |
| `install.py` | Registers this repo with pi (package) and Claude Code (plugin) so both load it in place |
| `Makefile` | Builds the shareable one-page HTML export |
| `jobs.md` | ETA rules for long-running jobs |
| `macos.md` | macOS command traps |
| [`index.md`](./index.md) | Index of model reviews, harness reviews, and usage records |
| [`model.org`](./model.org) | Personal model recommendations and reviews |
| [`harness.org`](./harness.org) | Dated harness reviews and ratings |
| [`model_usage_history.md`](./model_usage_history.md) | Historical model usage across agent harnesses |
| `pi.md` | pi package management |
| `prompts.md` | Personal paste-bin of chat prompts |
| `prompts/` | Reusable Pi slash commands loaded from the local package |
| [`quesion_types.yaml`](./quesion_types.yaml) | Question formats grouped into AI and non-AI categories for vibe coding |
| `removal.md` | Removing apps, packages and harnesses |
| `repos.md` | Nested git repo policy for `~/repos` |
| `skills/` | Installable agent skills (see [Skills](#skills)) |
| `terminologies.md` | Personal prompt-vocab notes |
| `use_case.md` | Personal notes: what I use agents for |

## Shareable HTML

Requires Emacs with Org Mode. Run `make html` to build `dist/agent1.html`.
The export includes model and harness reviews; it excludes model usage history.

## Skills

`skills/` holds skills in the open [Agent Skills](https://agentskills.io)
format: one directory per skill, with a `SKILL.md` and its `scripts/`. Skill
directories use hyphens (`git-report`) because the format requires the
directory name to match the skill `name`.

| Skill | What it does |
|---|---|
| `agent-usage-report` | HTML report of every model used across agent harnesses (pi, Claude Code, Codex, opencode): tokens, cost, and the most intelligent and most efficient model |
| `determinize` | Scans a directory's agent instructions, turns every decidable rule into a check, a guard or a git hook, and thins the prose to decisions and routing |
| `git-report` | Your commits across all your repos, local and remote, for any time window |
| `model-price-report` | Dark HTML report of subscription plans, first-party API prices, and Artificial Analysis scores |
| `privacy-scan` | Scans files or a diff for PII, privacy and security issues |

### Install

`install.py` registers this clone with every harness installed on the
machine. Nothing is copied or linked: each harness loads the repo in place, so
a `git pull` updates every harness on its next start.

```bash
~/repos/agent1/install.py           # dry-run: show the plan
~/repos/agent1/install.py --apply   # write it
~/repos/agent1/install.py --check   # exit 1 on drift
~/repos/agent1/uninstall.py --apply # unregister
```

| Harness | How it loads this repo |
|---|---|
| pi | `~/repos/agent1` in `~/.pi/agent/settings.json` `packages`; `package.json` `pi` declares `skills/`, `prompts/` and `harness/extensions/` |
| Claude Code | plugin `agents@raveen-agents` from the directory marketplace in `.claude-plugin/`, read live from the clone; registered with `claude plugin marketplace add` and `claude plugin install`, so the `claude` CLI must be on `PATH` (or set `CLAUDE_BIN`) |
| Codex | not wired yet |

- Idempotent, and touches only the keys this repo owns in each settings file.
- A harness whose home directory (`~/.pi`, `~/.claude`, `~/.codex`) is missing
  is skipped.
- Links that the older symlink installer made into this clone are moved to
  the Trash.
- Other repos that ship skills use the same code: their `install.py` calls
  [harness/install_lib.py](./harness/install_lib.py).

Verify: start a new session and ask "what git work did I do in the last 24
hours?". The agent should run `scripts/git_report.py`.
