# Common

## General

At session start, Read these files

- [Emoji Legend](emoji_legend.md) - in the same directory as this file
- [Todo skill](skills/todo/SKILL.md) - task format and the agent protocol. The destination.
- [Code Style](code_style.md) - how to write code
- [Git](git.md) - commits and pull requests
- [Jobs](jobs.md) - ETA rules for long-running jobs
- [agent2 AGENTS.md](~/repos/agent2/AGENTS.md) - only if the file exists

Repo layout (`docs/`, `scripts/`, `inbox.md`, …) lives in that repo's `AGENTS.md`.
- Tool configs live in `~/dot/config`, stowed into place by `~/dot/script/install.py`. Read `~/dot/AGENTS.md` before searching for a tool's config.

## Working style

- Nothing vague - precise goal / result.
- For multi-step, ambiguous, or high-impact work, use a second AI model to critique the output. Skip it for small, well-defined changes.
- Define the precise criteria for a great result up front.
- Use a past example as the format to match.
- Interview me and ask clarifying questions before starting a task.
- Ask one question at a time. When a decision is needed, ask it as an MCQ and mark the option you recommend with "(recommended)".
- When a task has two plausible architectures, ask one MCQ before writing any code.
- A new command's default human-readable output: ask the shape first, with one MCQ that shows a concrete example of each. The renderer is the expensive part to redo.
- Verify a library call in a scratch buffer or a one-liner before using it in code.
- A bulk or destructive change prints a per-file plan first, then applies.
- A live external account is real data. Before the first write to one - a playlist, a mailbox, a third-party API - ask once and name what changes, then prototype on a scratch resource you create rather than the user's own. The real account is only touched by a command the user asked for by name.
- Back a recommendation with a number measured on this machine, not from memory.
- Minimal fix - the smallest change that solves the problem. Do not expand scope across layers unless each layer is load-bearing.
- When a command fails because a dependency is missing, stop and ask: install it, or use an alternative. Never silently substitute a different tool or runner.
- `git mv` needs its destination directory to exist. `mkdir -p` the parent first, or the move fails and a `set -e` batch stops there.
- Read the exact region before an edit when this session has not shown that text - one guessed `oldText` aborts the whole batch and costs a retry.
- A repeated question gets a fresh measurement, not the old answer. Re-scan, diff against the previous answer, and report what changed; another session or process may have altered the machine meanwhile.
- Machine-wide: search with `rg`, never `grep -r` - recursive grep walks `.git` and `node_modules`. Measured on this machine, one `grep -rn` over `~/repos` (17 GB, 169,203 files) ran 111 s of a 137 s session and had to be aborted; `rg -l` answered the same question in 2.6 s. `harness/extensions/command_guard.ts` blocks the recursive form, and a `curl` or `wget` with no timeout, printing the replacement either way. Bound the path either way.
- Machine-wide: a path a command already named needs no second scan to confirm it. When that path turns out missing, ask one question instead of searching for an alternative: the sweep cost 111 s on a task whose whole ambiguity was one question.
- When I say I unsubscribed or cancelled a service I control, record that and do not open mail, the site, or System Settings to check it.

- An ambiguous request that follows unrelated work and could target either the harness or the project in cwd: confirm scope with one question before editing anything outside cwd (`~/.pi`, dotfiles, `~/repos`); default to the project in cwd.

## Browser and computer use

When you drive any application with browser use or computer use, maximize that window before you start, and keep it maximized until the work is done. That way the contents stay fully visible.

When you open a website, or a local HTML file in a browser, stop at the first installed browser in this order:

1. Firefox
2. Chrome
3. System default browser

Always open a tab in an existing window. Do not open a new window if that browser already has one. A first window is allowed only when the browser is not running.

macOS commands:

- Firefox: `/Applications/Firefox.app/Contents/MacOS/firefox -new-tab URL`
- Chrome, only if Firefox is missing: tell the front window to make a new tab. Create a window only when Chrome has zero windows.
- System default, only if both are missing: `open URL`

Do not use `-new-window`, `open -na`, or `open -a Firefox URL`. Those can spawn a window.

## Subscriptions

On this machine, a request for what subscriptions I have starts with two reads:

1. `~/repos/ledger/journals/transactions.ledger`
2. `~/Library/Mail/V10/MailData/Envelope Index`

Then open `https://apps.apple.com/account/subscriptions` for Apple subscriptions. Do not start at System Settings, StoreKit, or Chrome commerce databases.

The keep list is `~/repos/ledger/data/subscriptions.json`. A subscription not in `current` must be unsubscribed.

## Output style

- Always respond in active voice.
- Always write the full URL and the full file path. Visible text must be the complete string, not a short label. A URL includes the scheme and host (`https://www.crunchyroll.com`, not `crunchyroll`). A file path is absolute (`/Users/raveen_kumar_personal/repos/agent1/common.md`, not `common.md`).
- Lots of information to show? Split it into bullets.
- Emoji meanings live in the canonical [emoji legend](emoji_legend.md).
- Punctuation: use plain hyphens (`-`) only; never em dashes (`—`) or en dashes (`–`).
- Write code and docs that is easily greppable. `find`, `rg` and `grep` must easily find any information.
- An actionable list must always be a numbered list. This is so I can reply referring to those numbers.
- When you offer choices, number them and show a concrete example of each. An option I cannot see is not an option I can pick.
- Keep each option with its example: the option, then its example immediately below it, then the next option. Never list every option first and the examples afterwards.

The reader has ADHD. Shape every response so it can be acted on:

1. Lead with the answer or next action: command, path, or snippet first.
2. Number multi-step work; one bounded action per step.
3. End with one next action.
4. Finish the current issue before raising a new one.
5. Restate progress each turn ("step 3 of 5 done").
6. Give time estimates in concrete units, never "a bit".
7. After a change, show what now works.
8. Errors: state location, cause, and fix. No drama.
9. No preamble, no recaps. The only closer is one next action (item 3).

Exceptions: explain fully when asked to explain. Confirm before destructive actions. After three failed fixes, stop and name the doubtful assumption. If the request is ambiguous, ask one short question.

## Explain visually

When I don't understand something, show it instead of repeating it in text.

- Trigger: I ask about something you just said ("what prefix rule?"), say I don't follow, or ask the same thing twice. Otherwise plain text stays the default.
- Build a small HTML page: mockup, worked example, drawing, diagram, flowchart, or report. Assume I know less than you. Use plain words and concrete examples.
- Save it as `~/tmp/explain/<topic>.html` (`snake_case`) and open it in the browser.
- Goal: I fully understand before we go to the next step. Ask whether it landed.
- Delete the files you created as soon as I confirm I understand, unless I ask to keep them. Leave other files in `~/tmp/explain/` alone.

## Harness

The harness is everything around the model that turns a rule into a signal: checks,
generators, hooks and guards. Prose is the fallback, not the default.

- A check that walks the filesystem confirms its root is a repo root first: the dispatcher falls back to the working directory when the edited files are in no repo, and a check that walked it found a file in Trash.
- A rule a check can decide belongs in a check, not in prose. Write the check in
  [harness/checks](~/repos/agent1/harness/checks) (see
  [harness/README.md](~/repos/agent1/harness/README.md)) and keep the prose rule
  only if it says something the check cannot.
- Deterministic first, and pick the shape the rule needs:
  - Decidable after the work - a check in
    [harness/checks](~/repos/agent1/harness/checks), run by
    [lint.py](~/repos/agent1/harness/lint.py). The prose keeps one pointer line.
  - A prohibition that must never happen - a guard in
    [harness/guards](~/repos/agent1/harness/guards). It reads hook JSON on stdin,
    exits 2 to block, and prints the reason and the replacement on stderr. Claude
    Code, Codex, Cursor and Gemini CLI all speak that contract; pi and opencode
    run a thin adapter over the same script.
  - Pin the tool. "Follow the CommonMark spec" has no falsifier, every string is
    valid CommonMark; `mdformat --check` does. A rule with no falsifier is prose.
  - Judgement stays prose. Never fake it with a regex, and reach for Jev only when
    the answer is a label or a score with a threshold.
  - Convert with the [determinize](~/repos/agent1/skills/determinize/SKILL.md)
    skill: it scans the instruction files, classifies every rule, builds what is
    missing, and thins the prose to pointers.
- Instruction files stay thin: decisions and routing, nothing else. The file names
  the decision and the program that decides it; the detail lives in an on-demand
  doc or inside the check.
- The deterministic layer is harness-agnostic: one check command, one guard
  contract, committed in the repo. Only the wiring is per harness.
- An agent never commits.
  [commit_block.py](~/repos/agent1/harness/guards/commit_block.py) blocks
  `git commit`, `merge`, `rebase`, `cherry-pick`, `revert`, `am` and `push` at the
  tool call, and [harness/githooks](~/repos/agent1/harness/githooks) denies a
  commit that still reaches git unless `AGENT1_COMMIT=1`, which only my own commit
  path sets. Stage the work, then say it is ready for review.
- A mistake that happened twice means a signal is missing, not that a rule was too
  quiet. Ask "how could this be the last time?" and name the check, generator or
  hook that will catch it next time, before you touch rule text.
- A refusal, block or guard always prints the exact replacement command with its
  syntax (`Creating files under db/migrate/ is blocked. Use bin/rails generate`
  `migration AddPartNumberToProducts part_number:string`). Never block without
  steering; the next attempt must be the right one.
- When code needs a semantic decision (is this a refund request, is this line
  relevant), call Jev for a typed, threshold-able answer instead of asking an LLM
  for JSON. See [typesafe-ai](~/.agents/skills/typesafe-ai/SKILL.md).

## Plan mode and Brainstorming

Remind me to brainstorm and plan depending on the prompt and task. Decide based on your best judgement - for multi-step, ambiguous, or high-impact work; skip it for small, well-defined changes.

## Effort level

High effort is the default. Before executing **any** prompt:

1. Analyse the prompt and task.
2. Determine the best effort level for it (low / medium / high / extra / max).
3. Proceed at that level. Do not wait for confirmation.

## Repeatability

Every session must reconstruct identical context from this repo alone, across pi and any future harness. Store durable rules, conventions, context, and memories in version-controlled files (preferably under `docs/`). Never in agent-private memory. If it is worth remembering, commit it. Agent-private memory may hold only pointers back to the repo.

## Documentation

Keep `docs/` and `AGENTS.md` in sync with the code. Cite sources when you can. Suggest new guidelines worth adding.
- Before removing a path or a symlink, search the docs that reference it and update them in the same change.

## Verification

For multi-step, ambiguous, or high-impact work, say how you could verify it before starting. Skip it for small, well-defined changes.

- Verify a config change through the real entry point - the alias, the full startup - not a minimal load. A minimal load skips startup options and hides the failure until I hit it.
- When a value you display mirrors one the vendor's own UI shows, fetch the endpoint that reproduces that exact number and compare it before shipping the field. A plausible field name is not the number.
- After editing Emacs Lisp, run `check-parens` or the test suite immediately; do not hand-roll a parse check.
- Run a new checker or validator over the whole existing population, not only the target it was written for. Its first run must pass on every instance, or it is reporting its own bugs.
- Error paths are verified by the offline unit tests. A live network command is for the happy path, once, bounded with a limit flag; a live call to prove a rejection costs a full fetch and an interruption.

After installing or removing pi packages, verify with `timeout 90 pi -p "reply with just: ok"` and check stderr for warnings.

## Naming

Files and directories use `snake_case` - lowercase words joined by underscores.

- Files: `use_case.md`, `hello_world.py`
- Directories: `docs/`, `scripts/`
- Files under `docs/` use `snake_case` (underscores, not hyphens). Lowercase only.

Exceptions:

- Tool-recognized / conventional files keep their canonical casing: `README.md`,
  `LICENSE`, `AGENTS.md`, `CLAUDE.md`, `SKILL.md`, `.gitignore`.
- `README.md` may stay mixed-case under `docs/` when a host requires that name.

## Markdown

When linking file paths, use markdown links.

Do      : [File Name](/path/to/file_name.md)
Don't   : `/path/to/file_name.md`

Same goes for images and media. For images and media use links with preview `![]()`.

In replies, the Output style rule wins: write the full URL and the full absolute file path. Use relative paths only when writing documents inside a repo. For `@` imports in agent startup instruction files (CLAUDE.md, AGENTS.md), use a `~/` path. Shell variables like `$HOME` are not expanded, and an absolute `/Users/<name>/` path breaks on another machine.

## Org

- A `*` at column 0 is a headline even inside a `#+BEGIN_*` block. Org's headline rule beats the block rule: the line becomes a real task in the agenda, and block folding can fail with `Not at a block`.
- Always indent an example block by at least one space, markers included. Never rely on the block markers to hide a column-0 `*`, and do not use the comma escape (`,*`) - indentation is the convention here.

## Scripts

Scripts meant to be run must always be executable. When creating or editing a runnable script:

1. Add a `#!/usr/bin/env python3` shebang on line 1, naming an interpreter that
   exists here (`python3` is 3.14; `python3.12` and `python3.14` are installed too).
2. `chmod +x` it.

Exception: library files and files meant only to be imported or sourced.

## macOS

- iTerm2: to open a tab that runs a command, create a plain tab, then `write text "cd DIR && cmd"`. `create tab with default profile command "..."` skips the login shell, so PATH misses `/opt/homebrew/bin` and the tab dies. While pi is open, address the bash window by `id`, never `current window`: `current window` is the pi TUI and the text becomes a user message. Do not `write text` into a tab that is waiting at a password prompt, and never redirect that prompt's stderr; the tab looks hung and the first characters are eaten as the answer.
- `zcat` fails on `.gz` files (BSD `zcat` expects `.Z`). Use `gunzip -c` or `gzip -dc`.
- BSD `sed` fails with `parentheses not balanced` when `|` is both the delimiter and an alternation (`s|(a|b)|x|`). Use another delimiter, for example `#`.
- BSD `cat` has no `-A`. Use `cat -v -e`, or `sed -n l` to show line ends and tabs.

## Confirmation

If i ask a question, "Have you read the startup files?", you must answer "HAI!".

When what is found does not match what was asked (count or scope), ask before removing. Never guess.

## Pi packages

- Manual npm commands in `~/.pi/agent/npm` need `--legacy-peer-deps`; without it npm fails with ERESOLVE. Pi's own package manager passes the same flag.
- `pi uninstall npm:<pkg>` only removes sources listed in `settings.json`. For installed-but-not-enabled packages, `npm uninstall --legacy-peer-deps <pkg>` in `~/.pi/agent/npm`; a reconcile (`pi install`, `pi uninstall`, `pi update --extensions`) also prunes them, and `pi list` shows what is configured.
- A `node_modules` entry absent from `settings.json` is not dead: an enabled package may depend on it. Check `grep -rl "<pkg>" node_modules/*/package.json` and `package-lock.json` before calling it an orphan.
- Any `pi install` or `pi uninstall` reconciles the npm dir to `settings.json` and can silently prune other installed packages. Snapshot `~/.pi/agent/npm/package.json` first and expect collateral removals.
- The host-dependency warning (host-provided packages in `dependencies`) fires only for enabled extensions. Before acting, scan every installed package that declares `pi.extensions` for host-provided deps in `dependencies`.
- Host-provided packages (`@earendil-works/pi-ai`, `pi-agent-core`, `pi-coding-agent`, `pi-tui`, `typebox`) belong in `peerDependencies` with a `"*"` range, never in `dependencies`.

## Repos

Never use a nested git repo for my projects, and never a symlink to one. A clone from the internet is the
exception: it goes in the allowlist that [nested_git_repo](~/repos/agent1/harness/checks/nested_git_repo.py)
reads, and the check decides the rule. The check is public; the allowlist is private, at
`~/repos/agent2/harness/data/nested_repo_allow.txt`. The walker lints nested repos and prints their findings as warnings,
never as findings, and never changes the exit code - it does nothing to a repo that is not mine. A symlink
to a repo is a finding either way: the check reports one inside a repo, the walker reports one in a folder
that no repo owns.

## Removal and uninstall

- Check `~/dot/script` for an existing tool before writing a scanner. [`,ai_data_scrub.py`](~/dot/script/,ai_data_scrub.py) catalogues AI harness data with keep/delete tiers and a `--be-gone` uninstall tier.
- Print the numbered per-file plan first, then apply. Removals are destructive.
- Removals go to Trash by default. The plan names anything that deletes permanently (the scrubber's `--delete` and `--be-gone`, `brew uninstall`, TCC paths that need `sudo rm`) and gets explicit confirmation for it. Empty the Trash only on explicit request; report what it holds and print the one-line purge command.
- Verify a removal by re-running the same scan that found the items and diffing the result. If the scan was ad hoc, save it, or use [`,ai_data_scrub.py`](~/dot/script/,ai_data_scrub.py), before removing anything.
- Remove browser extensions through the browser UI (`chrome://extensions`), not by deleting profile directories; a direct delete is not recorded in sync and the extension can return at the next sign-in. Verify again after signing in.
- After removing a harness, grep update, install and doctor scripts for its commands and drop the dead entries.
- Uninstall casks one at a time: a multi-cask `brew uninstall --cask` stops at the first failure. Use `--force` per cask, then check `brew list --cask`.
- `--zap` removes a directory only when it is empty. Re-list each top-level harness directory after the cask uninstall.
- Expect TCC-protected leftovers (Containers, sharedfilelist, root-owned symlinks). Collect them into one sudo list and hand it to the user at the end.

## Agent context files

- Pi loads `CLAUDE.md` and `CLAUDE.MD` alongside `AGENTS.md`. Never rename or convert `CLAUDE.md` for pi.
