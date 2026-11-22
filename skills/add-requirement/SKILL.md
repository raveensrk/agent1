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

- Name the check that will prove it: unit test, window check or acceptance check.
  In a file on the math names it goes in a proof's `:TEST:`; in an old file, `:VERIFY:`.
- The project's test tools must be able to run it. No manual look, no dev session.

## 5. When it cannot be built as asked

- Stop. Say why, with the evidence.
- List 2 to 4 alternatives, each with trade-offs and its own evidence.
- Ask with the question tool (Claude Code: `AskUserQuestion`). User picks. Do not pick for them.

## 6. Check existing requirements

<!-- lemma: RT-15 -->

- Run `lemmax list --json` in the repo that holds the file: `{"version": 1, "rows": [...]}`, a row per requirement with its id, state, `:NEEDS:` and aliases-resolved links.

- Without lemmax on PATH, read the files instead.

- Duplicate: say so, offer to edit that one instead.

- Conflict: show both, ask which wins.

- It builds on another: set `:USES:` (old files: `:NEEDS:`) to its `:ID:`.

## 7. Draft and approve

Draft as an org heading, CONJECTURE (old files: OPEN), with:

- `:ID:` - new, never reused: a UUID v7 from `lemmax new-id`; a project whose old ids still count up may use `lemmax next-id <LETTER>`.
- `:CREATED:`, `:LAST_EDITED:` - today, `YYYY-MM-DD`.
- `:USES:` (old files: `:NEEDS:`) if it builds on another.
- Its proof: a heading in `FILE.proofs.org`, OPEN, with a new `:ID:`,
  `:PROVES:` the conjecture's id and `:TEST:` the named check (old files:
  `:VERIFY:` on the conjecture). `lemmax migrate FILE` moves an old file over.
- Body - what it does, in plain lines.
- One `Evidence:` line with links or paths.

Show the draft. Wait for a clear yes.

## 8. Write

- On yes: add `:APPROVED:` with today's date, write it into the file, commit as `docs(requirements): add <ID> <summary>`.
- On no or edits: revise and show again.
- Write no code. Building is a separate step.
