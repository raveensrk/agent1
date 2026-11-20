---
name: investigator-ant
metadata:
  scope: global
description: Investigate a task before building it - read the repo, research missing facts, ask the user simple questions, prove the task can be built with evidence or a throwaway spike, then plan it. In normal use it writes no files and answers in the session with findings and a short plan. Run by Ishikari's investigator ant it writes the product spec, tech spec, docs brief and worker plans and replies in JSON. Use when the user says investigate this, can this be built, how would we build this, plan this task, or runs /investigator-ant. Also the proof step of /add-requirement.
argument-hint: "[the task]"
---

# Investigator

Find out what a task needs, prove it can be built, then plan it. Both modes
share [Investigate](#investigate), [Ask](#ask) and [Proof](#proof). No plan
comes before the proof passes.

## Which mode

- **Ishikari mode** only when your prompt says you are an ant of the Ishikari
  workflow and tells you to follow this skill's Ishikari mode. Then follow
  [Ishikari mode](#ishikari-mode) and the ant's prompt, and nothing else.
- **Normal mode** every other time: the user runs the skill, it triggers in a
  normal session, or another skill or agent calls it. Then follow
  [Normal mode](#normal-mode) and ignore everything Ishikari-only: no Ishikari
  spec or plan files, no JSON reply, no Ishikari paths, never wait for an ant's
  inputs.
- **No user to ask** in normal mode (another agent called it): never wait. Take
  the recommended answer, go on, and list each question with the answer taken at
  the end.

## Investigate

1. Read what the task needs; reread when needed. Enough to judge the task.
   Critique it: gaps, risks, unclear scope.
2. Missing facts the repo cannot answer: start up to 5 researcher agents at once
   (model opus, effort low when the tool takes it) and wait for them. Stop each
   one with TaskStop once its facts are back; never reuse one. They read only,
   change nothing, never open or quote secrets (passwords, keys, tokens, ~/.ssh,
   keychains, .env, credential files, browser profiles). A fact about a user
   interface (GUI, CLI or TUI): tell the researcher to use the `/ux` skill in
   review mode (or inspect UI code and docs directly if `/ux` is unavailable),
   never plan mode. Normal mode: start one only when reading it yourself would
   cost more.

## Ask

- Ask nothing the repo, the research or an earlier answer settles, and never the
  same question twice.
- At most 8 questions in all; past that, take the recommended answer.
- Every question in `/ask-simple` style: one short plain sentence, 2-4 answers,
  recommended first and marked (Recommended). Up to 4 at once that do not depend
  on each other, most important first.
- Normal mode: ask with the `/ask-simple` skill (fallback: the question tool).
  No user to ask: see [Which mode](#which-mode). Ishikari: put them in the JSON
  reply; the main session asks.

## Proof

Prove the task can be built before designing. Evidence, for the exact versions
in use, is any of:

- Library docs: the official page showing the feature.
- Repo code: something that already does it, or close.
- Working example: a known project or sample doing the same.
- Spike: only if the above is not enough, a tiny throwaway snippet in a scratch
  folder outside the repo (the session's scratchpad when it has one), run once,
  then deleted. Never in the repo.

Guessing is not evidence. "Probably supported" is not evidence. The project
stays untouched.

Cannot be built as asked, or the design needs a choice only the user can make:
ask (see [Ask](#ask)), with 2-4 alternatives, each with its trade-offs and its
own evidence. Only when no answer could fix it, report it as a blocker.

## Normal mode

1. [Investigate](#investigate), then [Ask](#ask) until nothing important is
   unclear.
2. Run the [Proof](#proof).
3. Write no files. End in the session with:
   - **Findings**: what the task really needs, and the gaps and risks found.
   - **Can it be built**: yes or no, with the evidence.
   - **Plan**: the parts of the change, the files each touches, how each is
     tested, the test command, and the docs or help text to update. Short.
   - **Risks**: what could still go wrong.
   - **Questions**: only when answers were taken without the user, each question
     with the answer taken.
4. Proof failed: give findings, the blocker and the alternatives offered, with
   their evidence. No plan.

## Ishikari mode

You stay alive for the whole planning talk: the main session sends you the
user's answers as messages, so keep everything you read and learn. You do all
the planning: no other ant plans, so nothing is lost between ants.

- Product spec (product_spec.md): what the product does. Behaviours and
  invariants, nothing else.
- Tech spec (tech_spec.md): the architecture and the code's shape.
- One plan per worker ant, to build them.

Inputs (filled in by the main session): repo, main branch, state folder, task,
the plans folder, and the saved test and check commands.

You work in two parts. Part 1 ends with the product spec. Part 2 starts only
when the main session says "go on": the tech spec and the worker plans.

### Part 1: investigate

1. [Investigate](#investigate).

2. Ask as in [Ask](#ask). Answers come back as JSON `[{question, answer}]`.

3. Each reply is ONLY this JSON, no other text:

   ```json
   {"questions": [{"question": "", "why": "", "answers": []}],
    "remaining": 0, "blocker": "", "productSpecWritten": false,
    "ids": [], "testCommand": "", "checkCommand": "", "trivial": false,
    "trivialWhy": "", "techSpecWritten": false, "plansWritten": false,
    "proof": "", "plans": []}
   ```

   `remaining` is your guess of questions left after these.

   Docs: the run ends with a docs ant that updates docs/ (or doc/), or writes
   docs/ from scratch when the repo has neither. It cannot ask the user, so
   every docs question is yours to ask now, inside the same 8. Ask only what the
   repo, the task and the earlier answers do not settle:

   - No docs folder: who will read the docs, and anything about the product's
     purpose, scope or non-goals you could not state yourself.
   - Root docs or notes other than README.md, LICENSE, CHANGELOG and AGENTS.md:
     whether each is merged into the docs, moved into docs/ as it is, or left.
   - Requirement files (requirements.org, REQUIREMENTS.md, PRDs, user stories):
     whether each is converted into the docs, kept and linked, or left out.
   - Nothing to ask about: no docs question.

4. When nothing important is unclear, write product_spec.md in the plans folder
   (make the folder; write no other file; change nothing in the repo). It holds
   two lists and nothing else: no goals, no background, no decisions log, no
   facts, no assumptions, no how.

   - Behaviours: what the product does once the task is done, each with an id
     B1, B2... and written as given / when / then, so an ant can check it. Each
     answer the user gave shows up here as the behaviour it led to.
   - Invariants: what must always hold, before and after, each with an id I1,
     I2..., written so an ant can check it (existing tests pass, a public
     interface stays as it is, data is never lost...).

   A task that changes no behaviour (a refactor, a cleanup, docs) has no
   behaviours: write "No behaviour changes" and the invariants that must hold.

   Reply with questions empty, productSpecWritten true, ids (every B and I id,
   in order) and the test and check commands.

   Then judge whether the task is trivial and set trivial and trivialWhy (one
   plain line). Trivial means all of: small, known scope (1-2 files, easy to
   find); one sensible way to do it, no design choice; one task that cannot be
   split. Docs or config only helps but is not needed. If you asked the user any
   question, it is not trivial.

   Then stop and wait: do not start part 2 until you are told to go on.

### Part 2: tech spec and plans (after "go on")

5. Run the [Proof](#proof) and put the evidence in proof. If an answer changes
   what the product does, update the product spec and its ids. A blocker goes in
   blocker. If you were told a fast path was tried and given up, plan for that
   reason.

6. Tech spec: write tech_spec.md in the plans folder: the architecture and the
   code's shape. The parts of the change, the files each part owns, and every
   name, interface and data shape that crosses between parts, exact, so worker
   ants building in parallel fit together. Map every behaviour and invariant id
   to the part that delivers it.

   Docs brief: write docs_brief.md in the plans folder, for the docs ant. It
   holds, in short lists: the product's purpose, its readers, scope and
   non-goals; the reason behind each main design choice; the user's answer for
   each root doc, note and requirement file, by path; and what is still unknown,
   for the docs' Open questions chapter. Only what the user said or the repo
   shows: never guess a reason.

7. Plans: split the work into tasks that worker ants build in parallel, each in
   its own git worktree, so no two tasks edit the same file.

   - Keep tasks small so more run at once: at most about 3 files per task,
     splitting a big change by files. Give each task its own test file. Merge
     tasks that would be too small to stand alone.
   - Only when a task must edit a file another task creates, put that task's id
     in its "after".
   - A plan is one worker's thin slice of the two specs, never a copy of them.
     It holds only: the files to touch; the spec ids it covers (each B and I id
     belongs to at least one plan, and every plan covers at least one); the
     interfaces from the tech spec it uses or provides, by name; the test file
     and the tests that prove each id; and the test command.
   - No prose from the specs is repeated: the worker reads the specs for the
     detail, and cannot ask questions, so the specs must hold everything it
     needs. Never write out the text, labels or code a worker writes.
   - Write each plan to `<plans folder>/<id>.md`, with id in lowercase letters,
     digits and dashes, never `fast`, `check-fix` or `docs_brief` (Ishikari's
     own names). Change no other files, and nothing in the repo.
   - One task only: write no plan file. The one worker builds straight from the
     two specs; still give its entry in plans (step 8), covering every id.

8. Reply with techSpecWritten and plansWritten true (also for one task, with no
   file written), proof, ids (again, as the product spec has them now), and
   plans, one entry per plan:

   ```json
   {"id": "", "title": "", "files": ["repo-relative paths"], "covers": ["spec ids"],
    "after": ["plan ids"], "workflow": "optional saved workflow name"}
   ```

9. If the main session sends back problems with the plans (two tasks on one file
   or on a folder and a file inside it, a loop in after, a bad id or path, a
   spec id no plan covers), fix the plan files, the specs if needed, and the
   list, and reply again as in step 8.

### Always

10. If the task cannot be done at all as asked, say why in blocker.
11. Never reply with questions together with productSpecWritten true in part 1,
    or with plansWritten true in part 2, and never with none of questions, a
    written flag or blocker.
