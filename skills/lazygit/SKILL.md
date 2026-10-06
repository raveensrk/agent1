---
name: lazygit
description: Open lazygit for every repo this session wrote to that has uncommitted changes - a tab in iTerm, a window in Terminal.app - or for one repo the user names, clean or not. Use when the user says /lazygit, "open my dirty repos in lazygit", "show the repos I changed this session in lazygit", "which repos have uncommitted changes", "open lazygit for everything I touched", or "open lazygit in a tab for <repo>".
---

# lazygit

Read this session, find every git repo it wrote to whose worktree is dirty,
and open lazygit for each one in the terminal the session runs in.

## 1. Find the repos

```bash
~/repos/agent1/skills/lazygit/scripts/open_dirty_repos.py --dry-run
```

The script reads `$PI_SESSION_FILE` (or the newest session under
`/Users/raveen_kumar_personal/.pi/agent/sessions`), collects write targets -
`edit` and `write` tool calls, plus bash `>`, `>>` and `tee` destinations -
walks each up to its `.git` root, dedupes, and keeps roots whose
`git status --porcelain` is not empty. It prints one line per repo:

```
1 repos with uncommitted changes, dry run, nothing opened
  agent1  8 changed, 5 untracked  (main)
```

## 2. Open the tabs

```bash
~/repos/agent1/skills/lazygit/scripts/open_dirty_repos.py
```

Drops `--dry-run`, so it opens one lazygit per repo: a tab in the front iTerm
window, or a window in Terminal.app, which has no AppleScript tab creation at
all. Terminal.app gets printed `cd <repo> && exec lazygit` lines instead when an
idle shell prompt sits in its front window - the script never types into a shell
you already have open. iTerm when the session runs in iTerm, Terminal.app when
it runs in Terminal.app. Nothing steals focus - your current tab stays put. Each
iTerm tab is titled `lazygit: <repo>`, set a second after lazygit's own title
(lazygit overrides anything set earlier). `exec` replaces the shell, so the tab
ends when lazygit quits.

Other flags, only when the answers need them:

- `--repo <path>` - open that repo whether it is clean or not, skipping the
  session scan. Repeatable. Use it when the user names a repo: the scan answers
  "everything I touched", not "open this one".
- `--terminal iterm` or `--terminal terminal` - override the auto-detection.
- `--session-file <path.jsonl>` - read another session.

## 3. Report

Paste the script's own output, verbatim. When it prints
`No dirty repos found in this session.` say that - do not open an empty lazygit.

## 4. Verify

```bash
~/repos/agent1/skills/lazygit/scripts/open_dirty_repos.py --self-test
```

Builds a scratch repo in a temp dir and checks extraction, the repo-root walk
and the dirty counts. Must print `self-test ok`.

## Rules

- Never hand-roll the AppleScript, the tab loop, or the `git status` scan. The
  script is the only writer.
- Never stage, unstage, commit, or clean anything. lazygit is opened so the
  human decides what happens to the work.
- Repos the scan cannot see - a file changed by a command with no redirect, an
  edit made outside the recorded tool calls - do not open. Say which repos were
  found instead of guessing at extras.
