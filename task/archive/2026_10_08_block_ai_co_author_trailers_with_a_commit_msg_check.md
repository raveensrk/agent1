---
id: "cxfksqc6j9"
title: "Block AI co-author trailers with a commit-msg check"
state: "done"
due: ""
priority: ""
tag: ["tooling"]
repeat: ""
effort: ""
postpone: 0
created: "2026-10-08"
closed: "2026-10-11T20:24"
---

git.md says "Never add an AI co-author trailer", but only Claude Code enforces it (attribution off in ~/.claude/settings.json since 2026-10-08). Pi and other harnesses still rely on the prose rule.

- [ ] Add harness/checks/no_ai_coauthor.py: reject a commit message holding a Co-Authored-By: line that names an AI (Claude, noreply@anthropic.com, Codex, Copilot, GPT, Gemini, ...)
- [ ] Wire it as a commit-msg hook, harness-agnostic like the other checks
- [ ] Test: a message with the trailer fails, a human co-author passes
- [ ] Point git.md's rule at the check

## Log

- done 2026-10-11 20:24: agent1 harness/githooks/commit-msg + 4 tests (real git commits); global core.hooksPath set by dot config/gitconfig; probe: AI trailer commit exit 1, plain commit exit 0; git.md points at it
