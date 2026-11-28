---
name: relayout
metadata:
  scope: global
description: Check a repository's folder and file layout against its languages' usual layout and the user's rules. Keep a good layout as it is; otherwise move and rename files to make it clearer. Small moves run after a yes; big reshapes are listed apart and run only when picked. Use when the user says relayout, fix the repo layout, reorganize the folders, tidy where files live, or runs /relayout. Prints the plan and waits for a yes before moving anything; behavior stays the same.
argument-hint: "[path or area, e.g. src/ui]"
---

# Relayout a repository

Keep a good layout. Fix a poor one with moves and renames only. Plan first,
move after a yes, verify each step.

## 1. Look first

- Git repos only. No git: stop and say why - git is the undo for every move.
- Note any uncommitted changes. Planning goes on, since it moves nothing;
  Apply waits for a clean tree.
- Read the repo's `AGENTS.md` or `CLAUDE.md`, its Layout section, its
  requirements and its docs.
- Learn how it builds and tests. Run both once, before any change, and note
  what already fails.
- Limit the scan to the path or area given as an argument, if any.

## 2. Pin what must not move

```
python3 scripts/pinned.py [DIR]
```

Read-only. Prints each pinned path and the reason:

1. Outside use: another repo, a dotfile or a setting points to it. Example:
   the global `CLAUDE.md` reads `agent1/common.md`.
2. Tool-required: a place a tool looks for, like Cargo's `src/`, SwiftPM's
   `Sources/`, a Claude plugin's `skills/` and `.claude-plugin/`.
3. Root files: `README.md`, `AGENTS.md`, build and config files.

Pinned paths never move. The plan lists them, so the user sees why.

## 3. Judge

Compare the layout with:

1. The language's usual layout, in
   [references/standards.md](references/standards.md).
2. The user's rules: the repo's Layout section, its requirements, and
   [agent1.md](../../docs/rules/agent1.md) section Architecture - core and UI
   apart.

Signs of a poor layout. Each finding names the path and the evidence:

1. Loose files at the root that belong together.
2. Vague names: `misc/`, `stuff/`, `utils2/`, `new/`, `old/`.
3. Mixed name styles in one folder. When the language fixes no style, the
   style most files already use wins.
4. Tests far from the code they test.
5. One-file folders, or nesting deeper than the content needs.
6. Two folders doing one job, like `scripts/`, `bin/` and `tools/`.
7. Code, data and docs mixed in one folder.
8. Core and UI code mixed in one place.
9. A name that no longer says what the file holds.

A move must make a file easier to find, not only different. When in doubt,
keep. No finding: print `Layout is good - no changes.` and stop.

## 4. Plan

Lint every file the moves and their reference fixes touch:
`python3 ~/repos/agent1/harness/lint.py FILE ...`. A moved file counts as
changed, so its commit faces that lint.

Print, in this order:

1. Before and after trees of the parts that change.
2. Small moves: one numbered table - from, to, why, references to fix.
3. Big reshapes, apart: new top folders, a core and UI split, merged
   folders. Each runs only if picked.
4. Fixes, apart: one row per lint finding on a touched file. A fix is not a
   move; it runs only if picked.
5. Pinned paths that stay, with the reason.

Then stop and wait for a yes. The user may answer with row numbers to pick a
subset. When what was found does not match what was asked, in count or in
scope, ask before moving anything.

## 5. Apply

- The working tree must be clean. If it is not, stop and say what is in the
  way; never stash.
- Branch first: `git switch -c relayout/<YYYY-MM-DD>`.
- One group of related moves at a time:
  1. `mkdir -p` the new parent, then `git mv`.
  2. Fix every reference: imports, namespaces, module paths, Markdown links,
     `Makefile`, scripts, hooks, CI, `.gitignore`. Find them with
     `rg -F '<old path>'`.
  3. Prove none is left: `rg -F '<old path>'` prints nothing.
  4. Run the tests and the build related to the moved files. Both must pass
     before the next group. A group that breaks either is undone with
     `git reset --hard HEAD`, not patched around. That is safe here: the
     tree started clean and each good group is committed.
  5. Commit the group: `refactor(layout): <what moved>`.
- A picked fix runs after the group it belongs to, in its own commit, with
  the same tests.
- Last: write the new layout into the repo's `AGENTS.md` Layout section, one
  line per top folder. No `AGENTS.md`: create one with only that section.
  Commit as `docs(agents): record layout`.
- Update docs and READMEs that show the old tree.

## 6. Report

- What moved and why, one line per group, with its commit.
- Pinned paths, and the big reshapes and fixes not picked.
- Files moved, files renamed and references fixed, as exact numbers.
- The branch, and the landing step from
  [git.md](../../docs/rules/git.md#landing-a-branch). Wait for a yes.
- Next: run `/determinize` on the Layout section, so a check keeps it tidy.

## Rules

- Behavior stays the same: moves, renames and reference fixes only, plus
  the fixes the user picked.
- Change no file before the yes in step 4.
- Move only what the plan listed. Pinned paths never move.
- Never move a file into or out of another repo.
- Never leave a symlink or a stub at an old path.
- Never remove or skip a test to make a step pass.
