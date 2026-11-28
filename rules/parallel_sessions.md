---
last_reviewed: 2026-11-02
---

# Parallel sessions

- A second concurrent session on one repo takes its own worktree and branch: run
  `/worktree` in that session before it edits anything. One branch per worktree;
  land it on main when the task ends ([Landing a
  Branch](git.md#landing-a-branch)).

## Briefing an agent

A brief handed to a subagent or a parallel agent starts with
[agent_brief_header.md](../prompts/agent_brief_header.md): its safety, git,
test and report rules, written once. The brief adds the task below it and may
tighten those rules, never loosen them.
