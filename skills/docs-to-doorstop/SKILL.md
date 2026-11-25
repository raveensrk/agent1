---
name: docs-to-doorstop
metadata:
  scope: global
description: Turn a directory of docs and specs into a Doorstop requirements tree in ASPICE 4.0 form - the full V-model, SYS.1 to SYS.5, HWE.1 to HWE.4 and SWE.1 to SWE.6 - written in short, simple YAML items with D2, Mermaid or animated SVG diagrams where a picture explains it more simply. Scans the input first and asks every doubt before writing, then proves the tree with Doorstop and a bundled ASPICE checker. After each run it reviews the run and suggests improvements to itself, applied after a yes. Use when the user says convert docs to doorstop, make requirements from these specs, ASPICE requirements, doorstop tree, or runs /docs-to-doorstop.
argument-hint: "<input directory>"
---

# Docs to Doorstop

Read a folder of docs and specs. Write a Doorstop tree that follows ASPICE 4.0.
Every behaviour the docs describe becomes a requirement.

Separate from Lemmax. Do not use the Lemmax workflow or its files here.

Before step 1, read [lessons.md](lessons.md) and follow it.

`SKILL_DIR` below is the directory holding this file. The scripts are in
`SKILL_DIR/scripts/`.

## References

Read these when a rule here is unclear. Do not guess past them.

- ASPICE 4.0 PAM, free from VDA QMC (do not redistribute):
  <https://vda-qmc.de/en/automotive-spice/>. Chapter 4.3 is SYS, 4.4 is SWE,
  4.7 is HWE. Annex B defines the information items 17-00 Requirement,
  17-54 Requirement Attribute and 08-60 Verification Measure.
- Doorstop docs, `develop` branch:
  - Items and fields:
    <https://github.com/doorstop-dev/doorstop/blob/develop/docs/reference/item.md>
  - Documents and `.doorstop.yml`:
    <https://github.com/doorstop-dev/doorstop/blob/develop/docs/reference/document.md>
  - Creating documents and items:
    <https://github.com/doorstop-dev/doorstop/blob/develop/docs/cli/creation.md>
  - Validation and its messages:
    <https://github.com/doorstop-dev/doorstop/blob/develop/docs/cli/validation.md>
  - Publishing:
    <https://github.com/doorstop-dev/doorstop/blob/develop/docs/cli/publishing.md>
- Diagrams: D2 <https://d2lang.com/>, Mermaid <https://mermaid.js.org/>,
  SVG SMIL animation
  <https://developer.mozilla.org/en-US/docs/Web/SVG/Element/animate>.

## 1. Scan

- Input: the directory given as the argument. With no argument, ask for it.
- Output: `reqs/` next to the input, at `<parent of input>/reqs/`.
- Read every file in the input: Markdown, text, PDF, images, tables.
- List each stated behaviour, constraint and quality goal, with its source
  file and section. This is the behaviour map. Keep it until step 7.
- If `reqs/SYS1/.doorstop.yml` exists, load the tree. This is an update run
  (see step 6).

## 2. Ask every doubt

Before writing anything, ask the user every doubt, 4 questions a round, until
none are left. Ask in plain words, one decision a question. Doubts include:

- two docs that disagree,
- a vague word ("fast", "large", "soon") with no number and unit,
- a behaviour that could be stakeholder or system level,
- a missing actor, condition or limit,
- the allocation of every SYS3 element: hardware, software, other, or a mix.
  Always ask. Never decide allocation alone, even when the docs seem clear.
- each requirement that seems to need a `trace_exception` (step 4).

Never guess. Write nothing until the user has answered all of them.

## 3. Tree

Create the tree with the bundled script. Never create documents by hand.

```sh
SKILL_DIR/scripts/create_tree.sh <parent of input>/reqs
```

It makes 15 documents, each with `--sep -` and the default fields, and runs
`git init` when `reqs/` is not already inside a git repo (Doorstop needs one).
It stops with an error if a tree exists there or if the repo already has a
Doorstop tree elsewhere (Doorstop allows one root per repo). On that error,
ask the user. Never delete or move their tree.

The V-model:

```
SYS1 stakeholder reqs
└ SYS2 system reqs ─────────────────────────── SYS5 system verification
  └ SYS3 system architecture ──────────────── SYS4 integration verification
    ├ HWE1 hardware reqs ───────────────────── HWE4 hw reqs verification
    │ └ HWE2 hardware design ───────────────── HWE3 hw design verification
    └ SWE1 software reqs ───────────────────── SWE6 sw verification
      └ SWE2 software architecture ─────────── SWE5 integration verification
        └ SWE3 detailed design and units ───── SWE4 unit verification
```

| Prefix | ASPICE 4.0 | Kind | Parent document |
|---|---|---|---|
| SYS1 | SYS.1 Requirements Elicitation | requirement | - |
| SYS2 | SYS.2 System Requirements Analysis | requirement | SYS1 |
| SYS3 | SYS.3 System Architectural Design | design | SYS2 |
| SYS4 | SYS.4 System Integration and Integration Verification | test | SYS3 |
| SYS5 | SYS.5 System Verification | test | SYS2 |
| HWE1 | HWE.1 Hardware Requirements Analysis | requirement | SYS3 |
| HWE2 | HWE.2 Hardware Design | design | HWE1 |
| HWE3 | HWE.3 Verification against Hardware Design | test | HWE2 |
| HWE4 | HWE.4 Verification against Hardware Requirements | test | HWE1 |
| SWE1 | SWE.1 Software Requirements Analysis | requirement | SYS3 |
| SWE2 | SWE.2 Software Architectural Design | design | SWE1 |
| SWE3 | SWE.3 Software Detailed Design and Unit Construction | design | SWE2 |
| SWE4 | SWE.4 Software Unit Verification | test | SWE3 |
| SWE5 | SWE.5 Software Component Verification and Integration Verification | test | SWE2 |
| SWE6 | SWE.6 Software Verification | test | SWE1 |

Doorstop facts that shape the work:

- Add items with `doorstop add <PREFIX>`, then read the UID it prints. Link
  with `doorstop link <CHILD> <PARENT>`.
- There is no command to set fields (`doorstop edit` opens an editor). Fill
  fields by editing the YAML file. Keep the keys Doorstop wrote.
- Quote a level that is not a plain float: `level: '1.10'`, or YAML reads
  it as 1.1.
- A heading is an item with `normative: false` and a level ending in `.0`.
  Use headings to group items by function (ASPICE BP2: structure).
  A heading has no links. `check.py` skips it.
- A requirement with no parent that is still needed is `derived: true`. It
  still needs a rationale. Ask the user before making one.

## 4. Items

Every normative item carries these fields:

```yaml
header: Short name
text: |
  The system shall ...
links:
- SYS1-001
status: draft          # draft | reviewed | approved
priority: must         # must | should | could
rationale: |
  Why it is needed, one or two lines.
verification: |
  How to show it is met.
source: docs/spec.md#section
```

Text rules, every level:

- `text` is at most 5 lines. If it is longer, split it into more items. The
  limit covers only `text`. Keep the other fields short too.
- Plain, short words. One idea per sentence. No jargon the docs do not use.

Requirements (SYS1, SYS2, HWE1, SWE1):

- One statement with "shall". SYS1 names the stakeholder: "The user shall
  be able to ...". SYS2: "The system shall ...". HWE1: "The hardware
  shall ...". SWE1: "The software shall ...". EARS openings are fine:
  "When ...", "While ...", "If ..., then ...".
- No design and no implementation: say what, never how.
- Verifiable, with limits as numbers and units. Cover functional and
  non-functional needs: timing, power, accuracy, range.
- No contradictions with other requirements.
- `verification` holds the verification criteria.
- HWE1 and SWE1 link to their SYS3 element AND to the SYS2 requirement they
  come from (ASPICE HWE.1.BP5, SWE.1.BP5). Doorstop shows the SYS2 link as an
  INFO message only. That is expected.

Design (SYS3, HWE2, SWE2, SWE3):

- Design is allowed: elements, interfaces, static and dynamic behaviour,
  modes. Still 5 lines, still plain words.
- SYS3 elements carry `allocation`, a list from `hardware`, `software` and
  `other`, as the user confirmed in step 2. Write the hardware-software
  interfaces at SYS3 (ASPICE SWE.1 Note 4).
- `other` (mechanics, housing) has no lower level. Its SYS4 test verifies it.
- SWE3 may also link to the SWE1 requirement it meets. SWE5 may also link
  to SWE3 units.

Tests (SYS4, SYS5, HWE3, HWE4, SWE4, SWE5, SWE6) are ASPICE verification
measures (08-60):

- `text` is the measure: what to do and what to observe.

- `verification` has five labelled lines:

  ```yaml
  verification: |
    Technique: test | measurement | analysis | simulation | review | inspection
    Pass: the pass/fail criteria, with numbers.
    Entry: what must be ready before it starts.
    Exit: when it is done, and when to abort.
    Setup: the environment and equipment needed.
  ```

- Link each test to the item it verifies. Verification results are not in
  this tree. Say so in the report.

Coverage (checked by `check.py`):

| Parent | Needs a child in |
|---|---|
| SYS1 | SYS2 |
| SYS2 | SYS3 (waivable), SYS5 |
| SYS3 | SYS4, plus HWE1 if `hardware`, SWE1 if `software` |
| HWE1 | HWE2 (waivable), HWE4 |
| HWE2 | HWE3 |
| SWE1 | SWE2 (waivable), SWE6 |
| SWE2 | SWE3 (waivable), SWE5 |
| SWE3 | SWE4 |

"Waivable" means a requirement with `trace_exception: <reason>` may skip the
design child. ASPICE allows this for requirements that are not properties of
the product, such as process requirements (SYS.2 Note 8, SWE.1 Note 10). The
test child is never waived. Ask the user before adding each one.

Every behaviour in the map from step 1 needs at least one requirement.

## 5. Diagrams

Add a diagram only when it explains something more simply than text.

- Store it at `reqs/<PREFIX>/diagrams/<UID>.<ext>`.

- Link it from the item with `references`. The path is relative to the git
  root that `create_tree.sh` printed, not to `reqs/`. Doorstop then fails if
  the file is missing.

  ```yaml
  references:
  - path: SYS3/diagrams/SYS3-003.d2        # git root is reqs/
  # - path: reqs/SYS3/diagrams/SYS3-003.d2 # reqs/ inside a bigger repo
    type: file
  ```

- D2 (`.d2`): structure, architecture, data flow, states. Check with
  `d2 fmt <file>` and `d2 <file> <file>.svg`.

- Mermaid (`.mmd`): sequences, flows, states. Check with
  `mmdc -i <file> -o <file>.svg`. `mmdc` needs a headless Chrome. If it
  fails to launch, draw the diagram in D2 instead and tell the user.

- Animated SVG (`.svg`): only for behaviour over time, such as sequences and
  state changes, where motion makes the order clear. Use SMIL or CSS
  animation, with no scripts. It must have a `<title>` and be readable when
  paused. Check with `xmllint --noout <file>`.

A diagram that fails its check is fixed or removed before finishing.

## 6. Update runs

When the tree exists:

- Keep every UID. Never renumber.
- Add new items for new behaviours.
- Before changing an existing item's text, show the old and new text and ask.
- When a behaviour's source is gone, set `active: false` on its item. Never
  delete an item. Doorstop then fails on every active item that links to it
  (`no item with UID`), and `check.py` lists them. For each one, ask the
  user: remove that link (if it has another parent), or make it inactive
  too. Repeat down the tree until none are left.

## 7. Check and finish

Run both checks in `reqs/`. Fix every error and warning, then run them again.

```sh
doorstop -W                         # Doorstop's own validation
SKILL_DIR/scripts/check.py .        # ASPICE rules Doorstop does not check
```

- `WARNING: <DOC>: no items` is allowed only for a whole domain the product
  does not have: all SWE documents when no SYS3 element is `software`, all
  HWE documents when none is `hardware`. Confirm it with the user and list it
  in the report. Any other empty document is a gap to fix.
- Always pass `-W`. Plain `doorstop` marks every new item as reviewed by
  itself (`REVIEW_NEW_ITEMS`). Review is the user's sign-off, not the
  skill's.
- Never run `doorstop review` or `doorstop clear`.
- Doorstop may write link fingerprints (`- SYS1-001: <hash>`). That is
  normal. Keep them.
- `check.py` checks the fields, the 5-line limit, "shall" wording, the test
  labels, allocation, the extra SYS2 links, coverage and dead links. It exits
  1 when anything is wrong.
- Check the behaviour map. Every behaviour has an item. List any gap and fix
  it.

Then report:

- items per document,
- diagrams made,
- doubts resolved,
- `trace_exception` items and their reasons,
- gaps left,
- that verification results are out of scope.

## 8. Review the run and improve this skill

After every run, before ending, look back on how the run went. Judge the
skill, not the requirements.

Look for:

- doubts the user had to answer that a rule here could have settled,
- user corrections to items, wording, levels or links,
- Doorstop or `check.py` errors that took more than one fix,
- diagrams that failed to render or were not simpler than text,
- items that broke the 5-line limit or held implementation details,
- behaviours missed in step 1 and found later,
- steps that were slow, repeated or skipped.

Then:

1. List up to 5 suggestions, costliest problem first. Each one gives what
   went wrong (with evidence from this run), the exact change to this
   `SKILL.md`, to `lessons.md` or to a script, and why it helps next time.
2. Ask the user which to apply. Change nothing without a yes.
3. Apply the chosen ones. A rule change goes in `SKILL.md` or a script. A
   narrow lesson (one tool quirk, one wording fix) goes in `lessons.md` as
   one dated line.
4. Commit the change to the agent1 repo.

Keep `lessons.md` short. When a lesson has held for 3 runs, suggest moving it
into `SKILL.md`. When a lesson is wrong or stale, suggest deleting it.
