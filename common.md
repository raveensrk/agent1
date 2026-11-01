# Common

Agent1 is for everyone. Public rules, written for any agent and any harness.

## General

At session start, Read these files

- [Experimental rules](experimental.md) - live trial rules; a keeper moves into common.md or another file, the rest are deleted
- [task-router-2 skill](~/repos/task-router-2/resources/skills/task-router-2/SKILL.md) - tasks: one GNU recfile, the `task-router-2` CLI the only agent writer. `task-router-2 skill install` installs it.
- [Git](git.md) - commits and pull requests
- [Jobs](jobs.md) - ETA rules for long-running jobs
- [agent2 AGENTS.md](~/repos/agent2/AGENTS.md) - only if the file exists
- Repo layout (`docs/`, `scripts/`, `inbox.md`, …) lives in that repo's `AGENTS.md`.
- Tool configs live in `~/dot/config`, installed by `~/dot/script/install.py` (no symlinks). Read `~/dot/AGENTS.md` before searching for a tool's config.
- Tool list: read [Dev Tools](dev_tools.rec) before choosing a tool and prefer a tool listed there over an unlisted one.
- [Working Style](working_style.md)
- [browser.md](browser.md) - maximize first, browser order, one-tab rule, window frames.
- The user also works with org-mode text sometimes.

## Harness

The harness is everything around the model that turns a rule into a signal: checks, generators, hooks and guards. Prose is the fallback, not the default. The grid, the commands and the check contract live in [harness/README.md](harness/README.md).

- A rule a check can decide belongs in a check, not in prose. Write it in [harness/checks](harness/checks), run by [lint.py](harness/lint.py), and keep the prose rule only if it says something the check cannot.
- Deterministic first, and pick the shape the rule needs: decidable after the work, a check; a falsifier pinned to a tool, like `mdformat --check` (the pinned pair lives in [mdformat_check.py](harness/checks/mdformat_check.py)); judgement stays prose, never faked with a regex, and Jev only when the answer is a label or a score with a threshold. Convert with the [determinize](skills/determinize/SKILL.md) skill.
- A skill is discovered by its frontmatter, so a sweep that eats it is silent: [skill_frontmatter.py](harness/checks/skill_frontmatter.py) wants `name` and `description` in every `SKILL.md`, and the directory name to match it.
- After you create or edit an `.svg`, lint it before you call it done: `python3 ~/repos/agent1/harness/lint.py FILE.svg` (xmllint, svglint, then Prettier `--check`; run the `--write` command a finding prints). [svg_lint.py](harness/checks/svg_lint.py) also runs on every SVG the session touched when the run stops; render it with `rsvg-convert` too when how it looks matters.
- Instruction files stay thin: decisions and routing, nothing else. The file names the decision and the program that decides it; the detail lives in an on-demand doc or inside the check.
- A check that walks the filesystem confirms its root is a repo root first: the dispatcher falls back to the working directory when the edited files are in no repo, and a check that walked it found a file in Trash.
- The deterministic layer is harness-agnostic: one check command, one guard contract, committed in the repo. Only the wiring is per harness.
- A mistake that happened twice means a signal is missing, not that a rule was too quiet. Ask "how could this be the last time?" and name the check, generator or hook that will catch it next time, before you touch rule text.
- A refusal, block or guard always prints the exact replacement command with its syntax. Never block without steering; the next attempt must be the right one.
- When code needs a semantic decision (is this a refund request, is this line relevant), call Jev for a typed, threshold-able answer instead of asking an LLM for JSON. See [typesafe-ai](~/.agents/skills/typesafe-ai/SKILL.md).

## Parallel sessions

- A second concurrent session on one repo takes its own worktree and branch:
  run `/worktree` in that session before it edits anything. One branch per
  worktree; land it on main when the task ends ([Landing a Branch](git.md#landing-a-branch)).

## Theme

Dark theme by default: HTML pages, reports, apps, GUIs, terminal output colors and tool configs. Do not follow the system's light setting. Offer light only as an explicit option the user switches to. This rule can be overridden by the user.

## Ruled out

If I start to install, configure or discuss the following stop and ask whether to go on. Refer Avoid card in `dev_tools.rec`.

## Markdown

1. Real file references use Markdown links. Inline and fenced code are for
   literal text and syntax examples, not navigable file references. A link label
   may use inline code: `` [`guide.md`](doc/guide.md) ``.
2. Prefer relative link destinations inside repo documents. For spaces, use
   `%20` or an angle-bracket destination: `[Guide](<doc/my guide.md>)`.
3. Markdown does not expand `~`, `$VAR` or `${VAR}` in link destinations. Do not
   assume a renderer does; use them only when the consuming tool explicitly
   supports expansion. A leading `/` is a root-relative URL, not universally
   a filesystem path.

Do : `[File Name](/path/to/file_name.md)`
Don't : `/path/to/file_name.md`

Same goes for images and media. For images and media use links with preview `![]()`.

In replies, the Output style rule wins: write the full URL and the full absolute file path. Use relative paths only when writing documents inside a repo. For `@` imports in agent startup instruction files (CLAUDE.md, AGENTS.md), use a `~/` path. Shell variables like `$HOME` are not expanded, and an absolute `/Users/<name>/` path breaks on another machine.

## Scripts

Scripts meant to be run are executable: a line-1 shebang naming an installed interpreter (`python3` is 3.14; `python3.12` and `python3.14` are installed too), then `chmod +x`. Library files meant to be imported or sourced are exempt. [interpreter_resolves.py](harness/checks/interpreter_resolves.py) and [script_exec_bit.py](harness/checks/script_exec_bit.py) decide the hard half.

## CLI apps

Topic file: [cli.md](cli.md) - help shape, bare calls, short flags, one help table. [cli_help.py](harness/checks/cli_help.py) decides the hard half: a runnable, options or not, must handle `-h` and `--help` (short help) and a `help` command (long help).

## macOS

Topic file: [macos.md](macos.md) - iTerm2 tabs, BSD tool traps, PlistBuddy, screenshots, hung processes, where apps from `~/repos` install.

## Confirmation

If i ask a question, "Have you read the startup files?", you must answer "HAI!".

When what is found does not match what was asked (count or scope), ask before removing. Never guess.

## Pi packages

Topic file: [pi.md](pi.md) - npm `--legacy-peer-deps`, reconcile pruning, orphan checks, host dependencies.

## Repos

Topic file: [repos.md](repos.md) - no nested git repos, no symlinks to one, the allowlist and the walker. Loaded only when `~/repos` exists.

## Removal and uninstall

Topic file: [removal.md](removal.md) - plan first, Trash by default, casks one at a time, TCC leftovers.

