---
last_reviewed: 2026-11-02
---

# Rules

Agent1 is for everyone. Public rules, written for any agent and any harness.

This file is the entry to every rule and the index of all of them: read it at
session start and follow it.

Requirements are plain Markdown files, one per project:
[agent1.md](../../agent1.md) and [ishikari.md](../../ishikari.md).
Read only the section a task needs, e.g. section CLI for a CLI app.

## Confirmation

If i ask a question, "Have you read the startup files?", you must answer "HAI!".

When what is found does not match what was asked (count or scope), ask before removing. Never guess.

## Rule files

At session start, Read these files

- [Experimental rules](../../experimental.md) - live trial rules; a keeper moves
  into a file here, the rest are deleted
- [task-router-2
  skill](~/repos/task-router-2/resources/skills/task-router-2/SKILL.md) - tasks:
  one GNU recfile, the `task-router-2` CLI the only agent writer.
  `task-router-2 skill install` installs it.
- [Git](../../git.md) - commits and pull requests
- [Jobs](../../jobs.md) - ETA rules for long-running jobs
- [Harness](../../harness.md) - checks over prose, deterministic first, guards that
  steer
- [Markdown](../../markdown.md) - file links, link paths, 80 columns, aligned tables,
  Pandoc Markdown default
- [Parallel sessions](../../parallel_sessions.md) - a second session on one repo takes
  its own worktree and branch
- [Theme](../../theme.md) - dark by default
- [Ruled out](../../ruled_out.md) - stop and ask before touching a tool on the Avoid
  card
- [Scripts](../../scripts.md) - executable, line-1 shebang, installed interpreter
- [agent2 AGENTS.md](~/repos/agent2/AGENTS.md) - only if the file exists
- [Working Style](../../working_style.md)
- [Tools](../../tools.md) - repo layout, tool configs, the tool list, org-mode
- [browser.md](../../browser.md) - maximize first, browser order, one-tab rule, window
  frames.

Read when the task touches it:

- [external.md](../../external.md) - probing external systems, live accounts,
  credentials on disk.
- [agent1.md](../../agent1.md), section CLI - help shape, bare calls, short flags, one help table.
  [cli_help.py](../harness/checks/cli_help.py) decides the hard half: a
  runnable, options or not, must handle `-h` and `--help` (short help) and a
  `help` command (long help).
- [agent1.md](../../agent1.md), section Touch and mobile - touch and mobile web UI: layout
  steps, tap targets, gestures, phone keyboards. Adds to section GUI.
- [docs.md](../../docs.md) - writing docs: help output first, what else each
  program shape needs.
- [tui.md](../../tui.md) - writing a TUI: `?` help keybind, help page with vim
  keys.
- [macos.md](../../macos.md) - iTerm2 tabs, BSD tool traps, PlistBuddy, screenshots,
  hung processes, where apps from `~/repos` install.
- [pi.md](../../pi.md) - npm `--legacy-peer-deps`, reconcile pruning, orphan checks,
  host dependencies.
- [repos.md](../../repos.md) - no nested git repos, no symlinks to one, the allowlist
  and the walker. Loaded only when `~/repos` exists.
- [removal.md](../../removal.md) - plan first, Trash by default, casks one at a time,
  TCC leftovers.
