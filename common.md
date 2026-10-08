# Common

Agent1 is for everyone. Public rules, written for any agent and any harness.

## General

At session start, Read these files

- [Emoji Legend](emoji_legend.md) - in the same directory as this file
- [Experimental rules](experimental.md) - live trial rules; a keeper moves into common.md or another file, the rest are deleted
- [Waypoint skill](~/repos/waypoint/skills/waypoint/SKILL.md) - tasks: one Markdown file per task, the `waypoint` CLI the only writer. The Waypoint repo's `install.py` installs it.
- [Code Style](code_style.md) - how to write code
- [Git](git.md) - commits and pull requests
- [Jobs](jobs.md) - ETA rules for long-running jobs
- [agent2 AGENTS.md](~/repos/agent2/AGENTS.md) - only if the file exists

Repo layout (`docs/`, `scripts/`, `inbox.md`, …) lives in that repo's `AGENTS.md`.

- Tool configs live in `~/dot/config`, installed by `~/dot/script/install.py` (no symlinks). Read `~/dot/AGENTS.md` before searching for a tool's config.
- Tool list: when `~/dot/docs/dev_tools.md` exists, read it before choosing a tool and prefer a tool listed there over an unlisted one.

## Working style

- When using lists always prefer numbered lists.

- Nothing vague - precise goal / result.

- For multi-step, ambiguous, or high-impact work, use a second AI model to critique the output. Skip it for small, well-defined changes.

- Define the precise criteria for a great result up front.

- Use a past example as the format to match.

- Interview me and ask clarifying questions before starting a task.

- Ask one question at a time. When a decision is needed, ask it as an MCQ and mark the option you recommend with "(recommended)".

- Batch 2-4 questions in one call only when they are genuinely independent of each
  other; otherwise one at a time.

- When I name a priority and a timeframe together - "B - next weekend", "C", "B
  it" - set both in one pass rather than asking again:
  `waypoint edit <ref> --priority B --due <date>` on the date I mean. "Next weekend" is the coming Saturday unless
  I say otherwise.

- "Later" on a task means postpone it one week - `waypoint postpone <ref> +1w`,
  which works on an undated task too. Keep the task `todo`; the only states are
  `todo`, `in_progress`, `done` and `obsolete`.

- When a task has two plausible architectures, ask one MCQ before writing any code.

- Verify a library call in a scratch buffer or a one-liner before using it in code.

- A bulk or destructive change prints a per-file plan first, then applies, and a
  formatter or rewriter is proven on copies before it sweeps: run it on one or
  two representative files in `~/tmp`, diff the result, then apply it across the
  tree. The sweep that skipped that step rewrote 15 `SKILL.md` frontmatter
  blocks on 04 Oct 2026.

- Back a recommendation with a number measured on this machine, not from memory; a
  constant that ships records its sample size and date beside it.

- When a measurement shows an approach costs more than the option text said, stop
  and re-ask with the measured number instead of pushing on to make the original
  option true. An option offered as "about 5 s per refresh" turned out to need a
  visible window, a one-time login and a persistent profile, because headless
  Chrome is hard-blocked by Cloudflare; the session spent 40 more minutes making
  the broken option work, and the answer was then reversed twice.

- Minimal fix - the smallest change that solves the problem. Do not expand scope across layers unless each layer is load-bearing.

- For operational tasks, prefer native CLI commands and short shell sequences over ad-hoc Python/JavaScript wrappers when existing tools can perform the task safely. Before writing a wrapper, explain the specific capability the native CLI lacks.

- When a command fails because a dependency is missing, stop and ask: install it, or use an alternative. Never silently substitute a different tool or runner.

- Read the exact region before an edit when this session has not shown that text - one guessed `oldText` aborts the whole batch and costs a retry.

- A repeated question gets a fresh measurement, not the old answer. Re-scan, diff against the previous answer, and report what changed; another session or process may have altered the machine meanwhile.

- End a bash call so it exits 0 when finding nothing is a valid answer:
  `grep -c ... || true`, `ls <glob> 2>/dev/null || true`. A clean scan that exits
  1 is reported as an error and reads as a failure - 12 of those in one session.

- Machine-wide: search with `rg`, never `grep -r` - recursive grep walks `.git` and `node_modules`. Measured on this machine, one `grep -rn` over `~/repos` (17 GB, 169,203 files) ran 111 s of a 137 s session and had to be aborted; `rg -l` answered the same question in 2.6 s. `harness/extensions/command_guard.ts` blocks the recursive form, and a `curl` or `wget` with no timeout, printing the replacement either way. Bound the path either way.

- Machine-wide: a path a command already named needs no second scan to confirm it. When that path turns out missing, ask one question instead of searching for an alternative: the sweep cost 111 s on a task whose whole ambiguity was one question.

- An ambiguous request that follows unrelated work and could target either the harness or the project in cwd: confirm scope with one question before editing anything outside cwd (`~/.pi`, dotfiles, `~/repos`); default to the project in cwd.

- Symlinks: never create one, never commit one. Warn me first and name the alternative you chose instead - [no_symlinks.py](harness/checks/no_symlinks.py) decides it.

## Browser and computer use

Topic file: [browser.md](browser.md) - maximize first, browser order, one-tab rule, window frames.

## Harness

The harness is everything around the model that turns a rule into a signal: checks, generators, hooks and guards. Prose is the fallback, not the default. The grid, the commands and the check contract live in [harness/README.md](harness/README.md).

- A rule a check can decide belongs in a check, not in prose. Write it in [harness/checks](harness/checks), run by [lint.py](harness/lint.py), and keep the prose rule only if it says something the check cannot.
- Deterministic first, and pick the shape the rule needs: decidable after the work, a check; a falsifier pinned to a tool, like `mdformat --check` (the pinned pair lives in [mdformat_check.py](harness/checks/mdformat_check.py)); judgement stays prose, never faked with a regex, and Jev only when the answer is a label or a score with a threshold. Convert with the [determinize](skills/determinize/SKILL.md) skill.
- A skill is discovered by its frontmatter, so a sweep that eats it is silent: [skill_frontmatter.py](harness/checks/skill_frontmatter.py) wants `name` and `description` in every `SKILL.md`, and the directory name to match it.
- Instruction files stay thin: decisions and routing, nothing else. The file names the decision and the program that decides it; the detail lives in an on-demand doc or inside the check.
- A check that walks the filesystem confirms its root is a repo root first: the dispatcher falls back to the working directory when the edited files are in no repo, and a check that walked it found a file in Trash.
- The deterministic layer is harness-agnostic: one check command, one guard contract, committed in the repo. Only the wiring is per harness.
- A mistake that happened twice means a signal is missing, not that a rule was too quiet. Ask "how could this be the last time?" and name the check, generator or hook that will catch it next time, before you touch rule text.
- A refusal, block or guard always prints the exact replacement command with its syntax. Never block without steering; the next attempt must be the right one.
- When code needs a semantic decision (is this a refund request, is this line relevant), call Jev for a typed, threshold-able answer instead of asking an LLM for JSON. See [typesafe-ai](~/.agents/skills/typesafe-ai/SKILL.md).

## Parallel work

- Delegation to subagents is authorized. A `reviewer` subagent critiques
  multi-step, ambiguous, or high-impact implementation before it is summarized;
  a `scout` maps an unfamiliar subsystem before claims about it; an `oracle`
  challenges a risky or irreversible decision; long jobs run in the background.
  Complexity alone does not authorize a subagent.
- Before starting a reviewer subagent, always ask me which model and effort level to use and wait for my answer before launching it.
- A second concurrent session on one repo takes its own worktree and branch:
  run `/worktree` in that session before it edits anything. One branch per
  worktree; merge back when the task ends.
- A subagent shares the parent session's working tree. Do not run a subagent on
  the same files the parent is editing; isolate in a worktree first.

## Plan mode and Brainstorming

Remind me to brainstorm and plan depending on the prompt and task. Decide based on your best judgement - for multi-step, ambiguous, or high-impact work; skip it for small, well-defined changes.

## Effort level

High effort is the default. Before executing **any** prompt:

1. Analyse the prompt and task.
2. Determine the best effort level for it (low / medium / high / extra / max).
3. Proceed at that level. Do not wait for confirmation.

## Repeatability

Every session must reconstruct identical context from this repo alone, across pi and any future harness. Store durable rules, conventions, context, and memories in version-controlled files. Never in agent-private memory. If it is worth remembering, commit it. Agent-private memory may hold only pointers back to the repo.

## Documentation

Keep `docs/` and `AGENTS.md` in sync with the code. Cite sources when you can. Suggest new guidelines worth adding.

- Follow code-as-doc wherever practical: use clear code and keep small program-specific documentation in the program itself (docstrings, comments, or `--help`). Ask me before creating a separate documentation file.

- Before removing a path or a symlink, search the docs that reference it and update them in the same change.

## Verification

For multi-step, ambiguous, or high-impact work, say how you could verify it before starting. Skip it for small, well-defined changes.

- Verify a config change through the real entry point - the alias, the full startup - not a minimal load. A minimal load skips startup options and hides the failure until I hit it.
- A mechanism whose only real test is me pressing a key or looking at a window: ask for that one probe before building the rest of it. An Automator service passed `automator run`, then did nothing for three real key presses, and the route cost 25 minutes.
- Never report a keybind, hotkey or shortcut as working from a log line that merely correlated with my press. The evidence is the press, or a mechanism that answers to a synthetic event in the same session - skhd fires on `osascript -e 'tell application "System Events" to key code 105'`, a service shortcut never does.
- A poll loop that finds no process is not evidence that nothing fired. After a negative poll, read the target's own artifact (its log file) and say "not observed", not "did not fire".
- When a value you display mirrors one the vendor's own UI shows, fetch the endpoint that reproduces that exact number and compare it before shipping the field. A plausible field name is not the number.
- After editing Emacs Lisp, run `check-parens` or the test suite immediately; do not hand-roll a parse check.
- Run a new checker or validator over the whole existing population, not only the target it was written for. Its first run must pass on every instance, or it is reporting its own bugs.
- Error paths are verified by the offline unit tests. A live network command is for the happy path, once, bounded with a limit flag; a live call to prove a rejection costs a full fetch and an interruption.

After installing or removing pi packages, verify with `timeout 90 pi -p "reply with just: ok"` and check stderr for warnings.

## Naming

Files and directories use `snake_case` - lowercase words joined by underscores. [file_naming.py](harness/checks/file_naming.py) decides it: lowercase letters, digits, underscores and dots only, with the canonical tool names (`README.md`, `LICENSE`, `AGENTS.md`, `CLAUDE.md`, `SKILL.md`, `.gitignore`, `.claude-plugin/`) exempt. Skill directories under `skills/` are kebab-case by the Agent Skills format, decided by [skill_frontmatter.py](harness/checks/skill_frontmatter.py). Pi package prompts under `prompts/` may use kebab-case `.md` filenames: Pi uses them as slash-command names.

Names are singular: files, directories, fields, keys, tables, variables and CLI verbs (`tag` not `tags`, `task/` not `tasks/`). Use the plural only when the singular is already taken or would read wrong.

## Theme

Dark theme by default: HTML pages, reports, apps, GUIs, terminal output colors and tool configs. Do not follow the system's light setting. Offer light only as an explicit option the user switches to.

## Markdown

When linking file paths, use markdown links.

Do : [File Name](/path/to/file_name.md)
Don't : `/path/to/file_name.md`

Same goes for images and media. For images and media use links with preview `![]()`.

In replies, the Output style rule wins: write the full URL and the full absolute file path. Use relative paths only when writing documents inside a repo. For `@` imports in agent startup instruction files (CLAUDE.md, AGENTS.md), use a `~/` path. Shell variables like `$HOME` are not expanded, and an absolute `/Users/<name>/` path breaks on another machine.

## Org

- A `*` at column 0 is a headline even inside a `#+BEGIN_*` block. Org's headline rule beats the block rule: the line becomes a real task in the agenda, and block folding can fail with `Not at a block`.
- Always indent an example block by at least one space, markers included. Never rely on the block markers to hide a column-0 `*`, and do not use the comma escape (`,*`) - indentation is the convention here.

## Scripts

Scripts meant to be run are executable: a line-1 shebang naming an installed interpreter (`python3` is 3.14; `python3.12` and `python3.14` are installed too), then `chmod +x`. Library files meant to be imported or sourced are exempt. [interpreter_resolves.py](harness/checks/interpreter_resolves.py) and [script_exec_bit.py](harness/checks/script_exec_bit.py) decide the hard half.

## CLI apps

Topic file: [cli.md](cli.md) - help shape, bare calls, short flags, one help table. [cli_help.py](harness/checks/cli_help.py) decides the hard half: a file that parses options must mention both `-h` and `--help`.

## macOS

Topic file: [macos.md](macos.md) - iTerm2 tabs, BSD tool traps, PlistBuddy, screenshots, hung processes.

## Confirmation

If i ask a question, "Have you read the startup files?", you must answer "HAI!".

When what is found does not match what was asked (count or scope), ask before removing. Never guess.

## Pi packages

Topic file: [pi.md](pi.md) - npm `--legacy-peer-deps`, reconcile pruning, orphan checks, host dependencies.

## Repos

Topic file: [repos.md](repos.md) - no nested git repos, no symlinks to one, the allowlist and the walker. Loaded only when `~/repos` exists.

## Removal and uninstall

Topic file: [removal.md](removal.md) - plan first, Trash by default, casks one at a time, TCC leftovers.

## Agent context files

- Pi loads `CLAUDE.md` and `CLAUDE.MD` alongside `AGENTS.md`. Never rename or convert `CLAUDE.md` for pi.
