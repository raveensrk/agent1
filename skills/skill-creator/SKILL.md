---
name: skill-creator
description: Author a new agent skill or improve an existing one - interview, scaffold, write, validate, install, test. Use when the user says create a skill, make a skill, turn this into a skill, improve or fix a skill, or asks how to write a SKILL.md.
argument-hint: "[skill idea or skill to improve]"
---

# Skill creator

Turn a repeated task into a skill, or fix one that exists: a small instruction
package at `~/repos/agent1/skills/<name>/SKILL.md`, installed by this repo's
`install.py` into every harness. A skill is instructions only - it grants no
new tools, filesystem, network, or approval privileges.

## 1. Check it should exist

Climb the ladder before writing anything:

- Search for an existing skill: list `~/repos/agent1/skills/`, `~/.agents/skills/`, and run `npx skills find <query>` (the find-skills skill).
- If one already does the job, improve that skill instead of adding a second copy.
- If the task is one-off, say so and skip the skill.

## 2. Interview - one question at a time

Ask one question at a time, as an MCQ with a recommended option:

1. What repeated task should this cover? Ask for one real past example.
2. Which phrases should trigger it? Those exact words go in the description.
3. What goes in, and what comes out? Match the example's format.
4. Does it need `scripts/` (a deterministic or fragile operation), `references/` (a long schema or doc), or nothing?
5. How will we verify it worked? Prefer a runnable check.

Stop when a fresh agent reading only the SKILL.md would do the task the same way.

## 3. Scaffold

```bash
./scripts/init_skill.py <name> --resources scripts
```

Run from this skill's directory, or use the full path under `~/repos/agent1/skills/skill-creator/`. The script refuses bad names and existing directories.

- Kebab-case: lowercase letters, digits, single hyphens, 64 chars max. The directory name is the `name:`.
- Location: `~/repos/agent1/skills/<name>/SKILL.md`.
- Show the plan (name, description, step outline, resources) and get a yes before writing files.

Frontmatter shape:

```md
---
name: <same-as-directory>
description: <what it does> - <what it produces>. Use when <trigger 1>, <trigger 2>.
---
```

`description` is the only field loaded at session start. It must state both what and when, in the user's own trigger words, or the skill will not fire.

## 4. Write the body

- Numbered, procedural steps in run order. Command first, then the one-line why.
- Short sentences, plain hyphens, greppable words.
- Examples over prose: one realistic input and its output.
- Include the check in the skill: what to run to prove it worked.
- House rules apply: minimal solution, ask before destructive actions, verify through the real entry point.

Resources only when they remove real repeated work:

- `scripts/` - deterministic or fragile steps. Shebang, `chmod +x`, one runnable check.
- `references/` - long schemas or docs, read on demand.
- `assets/` - files copied into output.
- Never a README, changelog, or setup notes.

## 5. Install and verify

```bash
cd ~/repos/agent1
./install.py --dry-run    # expect one new link per installed harness
./install.py
```

- Add a one-line entry to `skills/index.md`, matching the existing shape.
- Structural check: `~/repos/agent1/skills/skill-creator/scripts/validate_skill.py ~/repos/agent1/skills/<name>` - frontmatter, name matches directory, description has a trigger, links resolve.

Test the trigger and the output. Write 2-3 realistic prompts a user would say, plus one that should not fire the skill. Judge by behavior, since a fresh session is what loads the skill:

```bash
timeout 120 pi -p "<prompt>"
```

- Pass: the skill fires on the right prompts and the output matches its format.
- Did not fire: reword the description to the user's actual phrase - not a synonym.
- Wrong output: fix the step the agent skipped in the body.
- Record pass/fail per prompt in the report.

## 6. Improve an existing skill

When the user names a skill to fix, optimize, or extend:

1. Read the whole SKILL.md and every resource. Run `validate_skill.py` first and fix structural errors before content.
2. Collect the evidence: what failed in real sessions, what the user corrected, what takes too many steps. Quote it.
3. Plan the smallest diff: which sections change, what gets added or deleted. Show it and get a yes.
4. Edit in place. Keep the skill's voice and step order. Change the description only when the trigger phrases change.
5. Re-verify: validate, `./install.py` (symlink follows the repo), then the test prompts from section 5.
6. Report the diff and what now works.

## 7. Report

Show the path, the symlink, the trigger phrases, and the verification result.
Skills are read at session start, so a new session is what picks it up; in a
live session, `/reload` picks up an edit, and `/skill:<name> <idea>` forces one.
