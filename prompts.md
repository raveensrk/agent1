# Prompts

## Purpose

Personal paste-bin. Copy a prompt into chat. Agents do not treat this file as rules.

## Stage 0 - Planning

- Interview me.
- Interview me until you uncover the goal of this project.
- Before we start building, interview me about this: What is the core problem this solves? Who is this for? What does success look like? What should this NOT do? Summarize it back to me before we write any code.
- Import @file
- I am thinking to `do this thing`. Brainstorm with me until we uncover the goal.
- Is there a project in the internet available that does this exactly? Or any alternative. I dont want to implement a new project if there is something that exists online.

### Refactor

- Go over this entire project and critic it.
- Tell me which parts of the project we can refactor.
- Should we replace the backend or frontend or both? The codebase of the project must align with the docs. Which framework would be be suited for this kind of work? I want the project to be highly expressive so the programming languages used must also be highly expressive.

## Stage 0.1 - Optional

- Do /init and add to @AGENTS.md. Refer @AGENTS.md in @CLAUDE.md.

## Stage 1 - Vibe Coding

- Review all TODO comments in the codebase, group by priority, and propose a step-by-step plan to resolve each.
- Improve these prompts. Make them concise without losing information.
- Follow these conventions <https://www.conventionalcommits.org/en/v1.0.0/>
- What do do next?
- Tell me next steps.
- Lessons from this run become <skill> rules

### Visual Explanation

Create a presentation and draw an animated diagram and visually explain. Use https://github.com/juliangarnier/anime. Don't use any skills.

## Stage 2 - Review

------------------------------------------------------------------------------

Based on this session,

- Go back and verify all your work so far. Make sure you used best practices, were efficient, and didn't introduce any issues.
- If you can verify the work so far with a test, create it.

------------------------------------------------------------------------------ 

## Stage 2.1 - UI/UX, GUI, Web UI

------------------------------------------------------------------------------ 

- Review this whole repo
- Are there any improvements that can be made?
- Refer: https://lawsofux.com/
- Comfort over dense.
- Help should be available inside app
- Must have multi window and tabs support.
- Must be cross-platform: MacOS and Linux

------------------------------------------------------------------------------ 

If the current OS is MacOS, when a commit is made, automatically install the app to `~/Applications/My_Apps`.

All gui apps installed from `~/repos` must install into `~/Applications/My_Apps`.

Fix already existing apps.

______________________________________________________________________

## Stage 2.2 - CLI

------------------------------------------------------------------------------ 

Are there any improvements that can be made?

Refer:

- https://clig.dev/
- https://github.com/cli-guidelines/cli-guidelines
- https://github.com/cli-guidelines/cli-guidelines/blob/main/content/\_index.md

------------------------------------------------------------------------------ 

## Stage 3 - Documentation

Based on the current session do the following,

- If `docs` directory does not exist create it.
- All documentation goes in `docs`.
- Remove stale docs and Reconcile docs and codebase.
- Write docs like a book
- If you learned anything new, add notes and instructions to the docs.
- Update training data if any.
- Reduce prose and draw more diagrams with mermaid when you can
- Draw Architecture diagrams
- Follow the latest CommonMark spec for markdown
- Before starting research the web for all the required information and grill me until you understand the goal.
- In root of the repository if there is any documentation or notes exists ask user if it can be moved to docs.
- README.md and AGENTS.md are the only docs files allowed in root.
- Keep the documentation minimal and unique. No duplicate information.

## Stage 4 - Maintenance

Based on this current session do the following,

- Find dead code and remove it.
- Try to reduce bloat in the project.
- Make performance improvements to the project.
- Perform maintenance and clean up redundancies in this project.
- Break large code blocks into smaller, focused components to improve usability and maintainability.
- Add helper scripts if they reduce token usage or improve task quality.
- Suggest an idea, improvement, tweak, or optimization for this project.
- Finally, Critic this project.

### Skills

- List all installed skills in this computer for all AI Agent Harnesses.
- List all installed skills in this computer for this current AI Agent Harness.

______________________________________________________________________

List all installed ai related apps / skills / configs / ai agent harness / data in this computer for all AI Agent Harnesses. Create a live webserver. The list must be a check box ill select and a button called delete - for you to act on. Use clojure.

______________________________________________________________________

### AI data scrub

Scrub what AI agent harnesses leave on this Mac: sessions, caches, telemetry,
logs and memories. Keep configs and logins unless I pick a bigger tier.

1. Scan. Look in each harness's folders and list what exists, with size:
   - Claude Code: `~/.claude`, `~/.claude.json`, `~/.claude.json.tmp.*`
   - Claude Desktop: `~/Library/Application Support/Claude`,
     `~/Library/Caches/com.anthropic.claudefordesktop*`,
     `~/Library/Caches/claude-cli-nodejs`
   - Codex: `~/.codex`, `~/Library/Caches/com.openai.codex`; CodexBar:
     `~/.codexbar`, `com.steipete.codexbar`
   - ChatGPT Desktop: `~/Library/Application Support/ChatGPT`, `com.openai.chat`
   - Cursor: `~/.cursor`, `~/Library/Application Support/Cursor`
   - VS Code: `~/.vscode`, `~/Library/Application Support/Code`
   - Gemini CLI: `~/.gemini`; Grok CLI: `~/.grok`; Pi: `~/.pi`
   - opencode: `~/.config/opencode`, `~/.local/share/opencode`,
     `~/.local/state/opencode`, `~/.cache/opencode`, `~/.opencode`
   - Ollama: `~/.ollama`; Hermes: `~/.hermes`; OpenClaw: `~/.openclaw`
   - Shared: `~/.cache/huggingface`, `~/.cache/puppeteer`
   - Any other AI app in `/Applications`, plus its bundle id's leftovers in
     `~/Library` (Preferences, Caches, WebKit, Saved Application State,
     Application Scripts, Containers, HTTPStorages, Group Containers).
2. Sort every path into cache, history, data, auth or config, and mark it
   delete or keep:
   - Delete: session transcripts, history logs, file-history, plans,
     telemetry, backups, caches, shell snapshots, paste caches, crash and
     sentry dirs, Chromium storage (Cache, GPUCache, IndexedDB, Local
     Storage, …), memory/log/state sqlite databases, installation ids, and
     temp litter.
   - Keep: settings and config files, `AGENTS.md`, rules, hooks, skills,
     plugins, extensions, automations, `auth.json`, OAuth/identity files and
     Claude Desktop's `Cookies` (keeps me signed in), and Codex's
     `chrome-native-hosts*.json` (deleting it breaks the browser extension).
   - Keep and flag for me to review: Ollama model weights (huge, a re-download),
     opencode `repos` (may hold unpushed work), and Hermes/OpenClaw agent
     installs, tools and workspaces.
3. Show the plan as a numbered table: harness, path, category, size, delete or
   keep, and why. Total the space it frees. Then stop and wait for my yes.
4. Before deleting, check that no harness is running (`pgrep -x claude codex opencode pi Claude ChatGPT Cursor ollama`). Deleting a live sqlite or its
   `-wal`/`-shm` files corrupts it. Tell me to quit what is running.
5. Move the delete rows to the Trash with `trash`, never `rm`. Take each sqlite
   file's `-wal` and `-shm` with it.
6. Re-run the same scan and show what is left and what was freed.

Bigger tiers, only when I ask, per harness:

- All: also configs, skills, plugins and auth.
- Be gone: also the app bundle, its `~/Library` leftovers, its keychain items
  (`security delete-generic-password -l <name>`), LaunchAgents that mention
  it, `defaults delete <bundle id>`, and its CLI (`npm uninstall -g` or `brew uninstall`, whichever installed it).

Never touch `~/dot` or `~/.dot`, in any tier. Never touch a path you did not
list in the plan.

______________________________________________________________________

## Stage 4.1 - Publish

- Create a script called `publish.py` in `scripts/` directory.
- It must read the entire project and create a website using pandoc. It must also support mermaid diagram rendering. The website must be published under a directory called `publish/`.
- The website must be dark mode.
- It must have a sidebar towards the left and as i navigate the website the sidebar must be synchronized with the page i currently read.
- Keep the website simple, minimal and functional. No bloat. KISS Philosophy.
- One page html document with all assets under `assets` directory.

## Stage 5 - Release

- Commit with a sensible message. Tag. Push the changes to the repository.



### Prepare repo for public release

Prepare this repo for public release. Refactor and organize and rewrite the repo in a way that it is ready to go public at any time. But keep the repo private. I will want to review before making public.

After that scrub this repo of any private data.

Private data must be handled by moving it into a different location.

## Stage 6 - Archive chat

- Archive chat

## General

- Find dead code, explain why, ask the user to remove it, then run regression tests to confirm.

## Skills

- Based on the project I'm working on, what Claude Skills should I create?

### Self-updating skill

Create a skill for `<task>`. Write `SKILL.md` with the goal, the steps, and the
criteria for a good result.

The skill must maintain itself as I use it:

- Read `SKILL.md` at the start of every run and follow it as written.
- At the end of every run, compare what I actually asked for and corrected
  against what the skill says.
- Where I deviated, ask me one question: one-off, or my new intent?
- On "new intent", rewrite only the affected lines, keep the file the same
  length or shorter, and show me the diff before saving.
- Log every change under `## Changelog` in the skill: date, what changed, what
  prompted it.
- Never widen the scope on your own. A deviation changes the skill only after I
  confirm it.

## Init

Write an AGENTS.md in the repo root that lets a fresh agent session (Claude Code
or Codex) pick up this project with no other context.

Base it on what's actually in the repo and on what we did in this session — read
the code, config, and scripts to verify anything you're unsure about. Don't
invent conventions that aren't there.

Cover:

- What this project is and what it's for, in a couple of sentences.
- Layout: the directories that matter and what lives in each.
- Setup: exact commands to install deps, run, build, test, and lint.
- Conventions the code actually follows: language/framework versions, style,
  naming, error handling, testing patterns.
- Gotchas: things that broke or surprised us, env vars and secrets required
  (names only, never values), services that must be running.
- Current state: what we changed this session, what works, what's unfinished,
  and the obvious next steps.

Keep it under ~200 lines, prose and short lists, no filler. If AGENTS.md already
exists, update it in place rather than rewriting from scratch. Show me the file
when it's done.
