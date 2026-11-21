---
name: add-requirement
metadata:
  scope: global
description: Add a requirement to a project's org requirements file only after proving it can be built and tested in the project's languages and libraries - with library docs, repo code, a throwaway spike or a working example. Offers alternatives when it cannot be built as asked, checks for duplicates and conflicts, shows the draft and writes it only after a yes. Use when the user says add a requirement, new requirement, write a requirement for, or runs /add-requirement.
argument-hint: "[the idea]"
---

# Add a requirement

Never write a requirement blind. Prove it can be built and tested first.
Format and process rules: [requirements.org](../../requirements/requirements.org).

## 1. Get the idea

- Idea comes from the argument. None given: ask for it.
- Find the project's requirements `.org` file. None or several: ask which.

## 2. Learn the stack

- Read the build files (`Cargo.toml`, `package.json`, `deps.edn`, `pyproject.toml`, ...) for languages, libraries and versions.
- Read the test setup: which test tools exist and how they run.

## 3. Prove it can be built

Follow the Proof section of the [investigator skill](../investigator-ant/SKILL.md#proof):
evidence for the exact versions in use, a spike only outside the repo, never a guess.

## 4. Prove it can be tested

- Name the check for `:VERIFY:`: unit test, window check or acceptance check.
- The project's test tools must be able to run it. No manual look, no dev session.

## 5. When it cannot be built as asked

- Stop. Say why, with the evidence.
- List 2 to 4 alternatives, each with trade-offs and its own evidence.
- Ask with the question tool (Claude Code: `AskUserQuestion`). User picks. Do not pick for them.

## 6. Check existing requirements

- Run `reqtrace list --json` in the repo that holds the file: every requirement, its id, state and `:NEEDS:`.

- Without reqtrace on PATH, read the files instead.

- Duplicate: say so, offer to edit that one instead.

- Conflict: show both, ask which wins.

- Parent fits: set `:NEEDS:` to its `:ID:`.

## 7. Draft and approve

Draft as an org heading, OPEN, with:

- `:ID:` - new, never reused: take it from `reqtrace next-id <LETTER>`, or the highest in use plus one.
- `:CREATED:`, `:LAST_EDITED:` - today, `YYYY-MM-DD`.
- `:NEEDS:` if a parent fits.
- `:VERIFY:` - the named check.
- Body - what it does, in plain lines.
- One `Evidence:` line with links or paths.

Show the draft. Wait for a clear yes.

## 8. Write

- On yes: add `:APPROVED:` with today's date, write it into the file, commit as `docs(requirements): add <ID> <summary>`.
- On no or edits: revise and show again.
- Write no code. Building is a separate step.
