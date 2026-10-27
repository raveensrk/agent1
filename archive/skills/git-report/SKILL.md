---
name: git-report
metadata:
  scope: global
description: Report the git commits a person made across all their repos, local and remote, all branches, for any time window (default the last 24 hours, configurable). Use when the user asks what they worked on, for a work log, standup notes, a daily or weekly report, or "my commits since X". Also sets up or edits its config (~/.local/git_report.toml), suggesting values from this machine.
argument-hint: "[0d | -1d | -Nd | -N | -Nw]"
---

# Git report

Report the git work I did in a time window. The bundled script collects the
data; you only choose the window and write the report.

## Requirements

- git 2.31+ and python 3.11+.

- A config at `~/.local/git_report.toml`. Each person keeps their own:

  ```toml
  # Directories scanned recursively; every git repo below each one is included.
  dirs = [
    "~/repos",
  ]

  # Single repos: a local path or a remote URL.
  # Remote URLs are mirror-cloned into ~/.cache/git_report/ on first use.
  repos = []

  # Author emails that count as mine (case-insensitive).
  emails = [
    "me@company.com",
  ]

  # Optional. Set EITHER default_hours OR start/end, never both.

  # The last N hours up to now. Any number above 0 (168 = one week).
  # Defaults to 24.
  default_hours = 24

  # A fixed window, in local time. Either key may be left out:
  # no end means now; no start means 24 hours before the end.
  # Any --start or --end flag replaces both keys.
  # start = "2026-09-22 11:00"
  # end = "2026-09-23 04:00"
  ```

## What the script counts

- **Repos:** Every git repo under `dirs`, plus each entry in `repos`. Submodules and nested repos are included. Worktrees and duplicates are counted once.
- **Commits:** Local and remote commits on all branches. Merge commits are skipped.
- **Authors:** Only commits whose author email is in `emails`.
- **Time:** The author date must fall inside the window. A rebased or amended copy of the same commit is listed once.
- **Safety:** Read-only. The script only runs `git fetch` and, for remote URLs, `git clone --mirror` into `~/.cache/git_report/`. Fetch never prompts for a password, and each fetch times out after 180s.

## Hard rules

- Run `scripts/git_report.py` from this skill's directory, unchanged. Do not
  replace it with your own git commands.
- Read-only. Never pull, checkout, reset, stash, commit, push, or change git
  config in any repo.
- Report only what the script outputs. Never invent, merge, or drop commits,
  and never add authors that are not in the config.
- If the script prints a line starting with `ERROR:`, stop. Show that line
  and how to fix it. If the config is missing, offer to set it up (see
  Setup).

## Setup - write or edit the config

Use this when the config is missing, when the user asks to set up or change
it, or when `--check` reports a problem.

1. Gather suggestions. This reads only and writes nothing:

   ```bash
   python3 <skill_dir>/scripts/git_report.py --suggest
   ```

   - `dirs`: top-level folders under home that hold git repos, with a repo
     count.
   - `emails`: emails from git config (global, per repo, current directory),
     with how many commits each authored. Never from other people's commits.
   - `config_exists`: whether a config is already there.

2. Add what this session already knows: emails, folders or remote repos the
   user mentioned, and the current working directory.

3. Propose the values as a numbered list, each with a one-line reason, and
   flag doubtful ones instead of dropping them silently:

   - `dirs`: prefer project folders (like `~/repos`). Flag scratch or
     download folders (`~/Downloads`, `~/tmp`) and let the user choose.
   - `emails`: flag test or placeholder addresses (`example.com`,
     `localhost`) and emails with very few commits.
   - `repos`: only remote URLs or paths the user named.
   - Window: `default_hours = 24` unless the user wants otherwise.

4. Wait for the user to confirm or edit the list.

5. Write the file with the template in Requirements. If a config already
   exists, show the exact diff first, get a yes, and copy the old file to
   `~/.local/git_report.toml.bak` before writing.

6. Validate. It reads the config and finds repos without fetching:

   ```bash
   python3 <skill_dir>/scripts/git_report.py --check
   ```

   Show `repos_found`, `emails` and any `skipped` entries. `config_ok` is
   false when an entry is skipped or no repo is found. Fix and rerun until it
   is true.

## Step 1 - Window

Window shortcuts, passed as the first argument (the user may type them as
skill arguments, like `/git-report -1d`):

| Shortcut | Window |
|---|---|
| `0d` | today, midnight to now |
| `-1d` | yesterday only, midnight to midnight |
| `-Nd` | that one day, N days ago |
| `-N` | last N days, today included, ending now |
| `-Nw`, `-N week` | last N weeks (7N days), today included, ending now |

Map plain words to a shortcut: "today" is `0d`, "yesterday" is `-1d`, "last 3
days" is `-3`, "past week" is `-1w`.

1. If the user gave a shortcut or words that map to one, pass it and no
   flags: `git_report.py -1d`.
2. If the user gave no window, pass no flags. The script uses the config's
   `start` and `end` if set, otherwise the last `default_hours` (24 if
   unset) ending now.
3. If the user gave any other window, convert it to local time in the form
   `YYYY-MM-DD HH:MM` (or `YYYY-MM-DD` for midnight). Work out relative
   phrases ("yesterday 11am to 4am today", "since Monday") from the current
   local date and time (run `date`). Pass `--start` and `--end`. With only a
   start, omit `--end` (it defaults to now). With only an end, omit
   `--start` (it defaults to `default_hours` before the end).
4. If the window is ambiguous, ask one question before running anything.

Window precedence: a shortcut or flags (never both), then config
`start`/`end` or `default_hours` (the config may set only one of these).
The command line replaces the config window as a whole.

## Step 2 - Run

Run from any directory, with `<skill_dir>` being the directory holding this
file. It can take a few minutes, because it fetches every repo first.

```bash
python3 <skill_dir>/scripts/git_report.py -1d
python3 <skill_dir>/scripts/git_report.py --start "YYYY-MM-DD HH:MM" --end "YYYY-MM-DD HH:MM"
```

The output is JSON:

- `window`: the start and end that were used, and `source` (`shortcut ...`,
  `flags`, `config` or `default_hours`)
- `repos_scanned`: the number of unique repos
- `repos_with_commits`: for each repo, its commits with `time`, `hash`,
  `author`, `subject`, `body`, `stat`, `branches`, and `pushed`
  (false = local-only)
- `skipped`: config entries that do not exist or failed to clone
- `fetch_failed`: repos whose fetch failed (their remote data may be stale)

## Step 3 - Report

Write the report as plain text in chat. Do not create a file.

1. Header line: the window (start to end, with the timezone), the total
   number of commits, and the number of repos with commits. If
   `window.source` is `config`, say the window came from the config file,
   since a fixed window there goes stale.
2. Group commits by repo (use the repo folder name), in time order.
3. One line per commit: time (`HH:MM`, with the date when the window spans
   several days), short hash, branch, pushed or local-only, a plain-language
   summary drawn from the subject and body (not the raw subject line), size
   (+/- lines when notable), and author email.
4. "Themes": 3 bullets that group the work by topic.
5. "Skipped" and "Fetch failed": list each entry with its reason. Leave a
   section out if it is empty.
6. If there are no commits, say so plainly and still show item 5.
7. "Summary for others", last: one paragraph of 3 to 5 sentences that a
   non-engineer (a manager or teammate) can read, ready to paste into a
   standup or status update.
   - First person ("I ..."), plain words, past tense.
   - Say what was worked on and what it achieved, grouped by topic, biggest
     first.
   - No hashes, branch names, file paths, line counts, emails, or tool
     jargon. Explain a technical term in a few words or leave it out.
   - Only claim what the commits show. Do not guess at impact.
   - With no commits, write one sentence saying no commits were made in
     the window.
