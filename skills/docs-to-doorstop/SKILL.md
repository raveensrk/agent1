---
name: docs-to-doorstop
metadata:
  scope: global
description: Turn a directory of docs and specs into a Doorstop requirements tree in ASPICE 4.0 form - SYS.1, SYS.2, SYS.3 and HWE.1 to HWE.4 - written in short, simple YAML items with D2, Mermaid or animated SVG diagrams where a picture explains it more simply. Scans the input first and asks every doubt before writing. Use when the user says convert docs to doorstop, make requirements from these specs, ASPICE requirements, doorstop tree, or runs /docs-to-doorstop.
argument-hint: "<input directory>"
---

# Docs to Doorstop

Read a folder of docs and specs. Write a Doorstop tree that follows ASPICE 4.0.
Every behaviour the docs describe becomes a requirement.

Separate from Lemmax. Do not use the Lemmax workflow or its files here.

## 1. Scan

- Input: the directory given as argument. No argument: ask for it.
- Output: `reqs/` next to the input, `<parent of input>/reqs/`.
- Read every file in the input: Markdown, text, PDF, images, tables.
- List each stated behaviour, constraint and quality goal, with its source
  file and section.
- If `reqs/` exists, load it. This is an update run (see step 6).

## 2. Ask every doubt

Before writing anything, ask the user every doubt, 4 questions a round, until
none are left. Ask in plain words, one decision a question. Doubts include:

- two docs that disagree,
- a vague word ("fast", "large", "soon") with no number,
- a behaviour that could be stakeholder or system level,
- a missing actor, condition or limit,
- whether something is hardware or not.

Never guess. Write nothing until the user has answered all of them.

## 3. Tree

Create documents with the `doorstop` CLI, inside `reqs/`:

| Prefix | ASPICE 4.0 | Content | Parent |
|---|---|---|---|
| SYS1 | SYS.1 | Stakeholder requirements | - |
| SYS2 | SYS.2 | System requirements | SYS1 |
| SYS3 | SYS.3 | System architecture elements | SYS2 |
| HWE1 | HWE.1 | Hardware requirements | SYS3 |
| HWE2 | HWE.2 | Hardware design elements | HWE1 |
| HWE3 | HWE.3 | Hardware design verification tests | HWE2 |
| HWE4 | HWE.4 | Hardware requirements verification tests | HWE1 |

```sh
cd <parent>/reqs && git init -q 2>/dev/null   # doorstop needs a VCS root
doorstop create SYS1 ./SYS1
doorstop create SYS2 ./SYS2 --parent SYS1
# ... and so on for each row
doorstop add SYS2
doorstop link SYS2-001 SYS1-001
```

If `reqs/` sits inside an existing git repo, skip `git init`.
No software levels (SWE). The tree is system and hardware only.

## 4. Items

Each item is a Doorstop YAML file. Fill these fields on every item:

```yaml
active: true
normative: true
level: 1.1
header: Short name
text: |
  The system shall ...
links:
- SYS1-001
# custom attributes
status: draft          # draft | reviewed | approved
priority: must         # must | should | could
rationale: |
  Why this is needed, one or two lines.
verification: |
  How to show it is met: method and pass criteria.
source: docs/spec.md#section
diagram: diagrams/SYS2-004.d2   # only when a diagram exists
```

Text rules:

- At most 5 lines of text, every level. Longer: split into more items.
- Requirements (SYS1, SYS2, HWE1): one "The system shall ..." statement.
  For HWE1 "The hardware shall ...". For SYS1 the stakeholder may be named:
  "The driver shall be able to ...".
- No implementation details in SYS1, SYS2, HWE1: say what, never how.
- SYS3 and HWE2 hold design, as ASPICE 4.0 expects: elements, interfaces,
  allocation. Still 5 lines, still plain words.
- Plain, short words. One idea per sentence. No jargon the docs do not use.
- Tests (HWE3, HWE4): text is the test; `verification` holds pass criteria;
  link to the item it verifies.
- Each requirement keeps its own `verification` field AND has a linked test
  item in HWE3 or HWE4 where it is hardware.
- Every listed behaviour from step 1 maps to at least one item. Keep the map
  until step 5.

## 5. Diagrams

Add a diagram only when it explains more simply than text.
Store it as a file in `reqs/<PREFIX>/diagrams/<UID>.<ext>` and set `diagram:`.

- D2 (`.d2`): structure, architecture, data flow. Check with `d2 fmt` and
  render `d2 <file> <file>.svg`.
- Mermaid (`.mmd`): sequences, flows, states. Check with
  `mmdc -i <file> -o <file>.svg`.
- Animated SVG (`.svg`): only behaviour over time - sequences and state
  changes where motion makes the order clear. SMIL or CSS animation, no
  scripts, readable when paused.

A diagram that fails to render is fixed or removed before finishing.

## 6. Update runs

When `reqs/` exists:

- Keep every UID. Never renumber.
- Add new items for new behaviours.
- Set `active: false` on items whose source is gone. Do not delete.
- Before changing an existing item's text, show old and new and ask.

## 7. Check and finish

- Run `doorstop` in `reqs/`. Fix every error and warning, then run again.
- Check each item text is 5 lines or fewer.
- Check the behaviour map: every behaviour has an item. List any gap and fix.
- Report: items per document, diagrams made, doubts resolved, gaps left.
