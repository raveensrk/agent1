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
| `code_style.md` | How to write code |
| `common.md` | Session start, working style, output style |
| `emoji_legend.md` | Status emoji vocabulary for agent reports |
| `git.md` | Commits and pull requests |
| `install.py` | Installs skills and commands into Claude Code, Codex and pi |
| `jobs.md` | ETA rules for long-running jobs |
| `prompts.md` | Personal paste-bin of chat prompts |
| `skills/` | Installable agent skills (see [Skills](#skills)) |
| `terminologies.md` | Personal prompt-vocab notes |
| `use_case.md` | Personal notes: what I use agents for |

## Skills

`skills/` holds skills in the open [Agent Skills](https://agentskills.io)
format: one directory per skill, with a `SKILL.md` and its `scripts/`. Skill
directories use hyphens (`git-report`) because the format requires the
directory name to match the skill `name`.

| Skill | What it does |
|---|---|
| `agent-usage-report` | HTML report of every model used across agent harnesses (pi, Claude Code, Codex, opencode): tokens, cost, and the most intelligent and most efficient model |
| `git-report` | Your commits across all your repos, local and remote, for any time window |
| `migrate-todo` | Converts line-schema todos to the lisp schema, one repo at a time |
| `model-price-report` | Dark HTML report of subscription plans, first-party API prices, and Artificial Analysis scores |
| `privacy-scan` | Scans files or a diff for PII, privacy and security issues |

### Install

`install.py` symlinks every skill and command into each harness that is
installed on the machine. Each item is a link back to this clone, so a
`git pull` updates every harness at once.

```bash
~/repos/agent1/install.py --dry-run
```

```bash
~/repos/agent1/install.py
```

| Item | Claude Code | Codex | pi |
|---|---|---|---|
| `skills/*` | `~/.claude/skills/` | `~/.codex/skills/` | settings.json (global skills only, via `~/dot/script/,agent_config.py`) |
| `commands/*.md` (none yet) | `~/.claude/commands/` | not supported | `~/.pi/agent/prompts/` |

- Idempotent: run it again after every `git pull`. It adds new items and
  removes links to items that were deleted or renamed here.
- Never deletes or overwrites a real file or directory. It reports a
  conflict and exits 1 instead.
- `--force` replaces symlinks that point somewhere else (for example an
  older clone). `--uninstall` removes every link into this clone.
- A harness whose home directory (`~/.claude`, `~/.codex`, `~/.pi`) is
  missing is skipped.
- Older versions linked skills into `~/.agents/skills/`. Pi now loads global
  skills from its settings and Codex uses `~/.codex/skills/`, so `install.py`
  prunes any links left there.
- Needs Python 3.8+ on macOS or Linux.
- Claude Code: use `install.py` or the plugin, not both, or each skill
  loads twice.
- Any other harness: paste the skill's `SKILL.md` as the prompt and give the
  agent the script path.

To support a new harness or item type, add a line to `HARNESSES` or
`TARGETS` at the top of `install.py`.

Verify: start a new session and ask "what git work did I do in the last 24
hours?". The agent should run `scripts/git_report.py`.
