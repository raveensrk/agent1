---
name: ishikari
metadata:
  scope: global
description: Run the Ishikari workflow on a task - ants review it, plan it, build it in parallel worktrees, check and fix it, test it together, and merge it - stopping only to ask the user. Use when the user runs /ishikari, or says run ishikari, use the ants, or build this with Ishikari.
argument-hint: "<task> [repo path]"
---

# Ishikari

Drive the three Ishikari workflows for one task. Design, rules and diagram:
[age_of_agents/index.md](~/repos/agent1/age_of_agents/index.md). Scripts:
`~/repos/agent1/age_of_agents/workflows/ishikari-{plan,build,finish}.js`.
Run each with the Workflow tool's `scriptPath` and pass `args` as JSON.

Ask every question with the `/ask-simple` skill. Never answer for the user.

## 1. Setup

- Repo: the path in the arguments, else the current repo. Task: the rest of
  the arguments; if there is none, ask for it.
- Run `python3 ~/repos/agent1/age_of_agents/tools/ishikari.py setup <repo>`.
  Keep its JSON as `env` for every step.

## 2. Plan

- Run `ishikari-plan` with `{env, task}`. Any cleanup plan the last finish
  left is a task the user may add; offer it.
- `review`: ask its questions, then run again with
  `{env, task, review, answers}`: one answer per question, in order, `''`
  if skipped.
- `blocked` or `error`: show the reason and stop.
- `plans`: show the requirement and each plan's title, files and `after`.
  Ask for approval. On yes, write the requirement to its file and commit
  only that file. Then remove the answered critiques by piping the
  `answeredCritiques` JSON into
  `python3 <env.tool> boards remove <env.state> critiques`.
  Add the result's `testCommand` to `env`.

## 3. Build

- Run `ishikari-build` with `{env, plans}`; later rounds also pass `bugs`.
- Final review: for each task show status, notes, nits, base problems and
  fix history; show escalated, blocked and error tasks with their bugs.
  Offer to show the diff (`git -C <repo> diff <main>...<branch>`).
- Ask which tasks to approve, which to send back (with the user's guidance)
  and which to drop. Tasks sent back go to a new build round as
  `bugs: [{task, branch, bug, after, history, guidance}]`.

## 4. Finish

- Run `ishikari-finish` with `{env, approved, together, drop}`; `approved`
  items are `{id, branch, after}` from the build result.
- `mainMoved: false`: show the reason; nothing is lost, run finish again
  once it is fixed.
- `bugs` and `waiting`: offer a new build round for them.
- Report what landed on main, the new critiques count and any cleanup plan.
