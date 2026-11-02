---
last_reviewed: 2026-11-02
---

# Parallel sessions

- A second concurrent session on one repo takes its own worktree and branch: run
  `/worktree` in that session before it edits anything. One branch per worktree;
  land it on main when the task ends ([Landing a
  Branch](git.md#landing-a-branch)).
