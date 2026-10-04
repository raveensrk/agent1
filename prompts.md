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

## Stage 2 - Review

Based on this session,

- Go back and verify all your work so far. Make sure you used best practices, were efficient, and didn't introduce any issues.
- If you can verify the work so far with a test, create it.

## Stage 2.1 - UI/UX, GUI, Web UI

- If there is any improvements that can be made to the user interface, do it.
- Refer: https://lawsofux.com/
- Each element in the UI must be named correctly in a way the user can refer to them in claude code chat.
- Comfort over dense.
- Multi window and tabs support.
- Help should be inside app

## Stage 2.2 - CLI

- If there is any improvements that can be made to the cli, do it.
- Refer
  - https://clig.dev/
  - https://github.com/cli-guidelines/cli-guidelines
  - https://github.com/cli-guidelines/cli-guidelines/blob/main/content/\_index.md

## Stage 3 - Documentation

Based on the current session update the documentation and training data.

- Remove stale docs
- Write and Update documentation
- Reconcile docs and codebase.
- Try to reduce token usage in the project by updating the docs.
- Write docs like a book and wiki.
- Based on this session update and reconcile the docs and codebase.
- If you learned anything new, add notes and instructions to the docs.
- Update training data if any.
- If you can draw diagrams with mermaid and explain better then replace those blocks of text with mermaid diagram.
- Follow the CommonMark spec for markdown: <https://spec.commonmark.org/0.31.2/>
- Use active voice.

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

## Stage 4.1 - Publish

- Create a script called `publish.py` in `scripts/` directory.
- It must read the entire project and create a website using pandoc. It must also support mermaid diagram rendering. The website must be published under a directory called `publish/`.
- The website must be dark mode.
- It must have a sidebar towards the left and as i navigate the website the sidebar must be synchronized with the page i currently read.
- Keep the website simple, minimal and functional. No bloat. KISS Philosophy.
- One page html document with all assets under `assets` directory.

## Stage 5 - Release

- Commit with a sensible message. Tag. Push the changes to the repository.

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
