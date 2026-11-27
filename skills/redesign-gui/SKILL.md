---
name: redesign-gui
metadata:
  scope: global
description: Redesign a desktop app's GUI from scratch in four gated phases - discovery interview and design brief, SVG mockup review loop, frontend-backend contract, then frontend, backend and verification - with 8 themes, multiple windows and tabs, built-in help, keyboard-only use, motion tokens and the Laws of UX, on macOS and Linux. Use when the user says redesign the GUI or UI, give this app a new design, make this a proper GUI app, or runs /redesign-gui. Interviews first; writes no UI code until the mockups and the contract are approved.
argument-hint: "[phase: discovery | mockups | contract | frontend | backend | verify]"
---

# Redesign a GUI

Redesign the app's GUI from scratch. Keep nothing of the current layout or
visual style. Full creative freedom, within
[references/requirements.md](references/requirements.md). The result looks
modern, feels polished and comfortable, and comes alive with smooth
animations. Consistency and alignment come first.

## Gates

Four approvals. Never pass one without the user's explicit yes:

1. The design brief, `docs/design-brief.md`.
2. The mockups: the user says they are satisfied.
3. The interface contract, `docs/interface-contract.md`.
4. The finished frontend, before the stub layer is replaced.

## Resume

The work spans many sessions. Find the phase before doing anything:

1. An argument such as `/redesign-gui mockups` names the phase.
2. Otherwise read `docs/` in the target repo and the git log of the redesign
   branch. The furthest approved deliverable sets the phase:

| Found                                 | Phase               |
| ------------------------------------- | ------------------- |
| Nothing                               | 1, discovery        |
| `docs/design-brief.md`, approved      | 2, mockups          |
| Mockups approved                      | 3, step 1, contract |
| `docs/interface-contract.md` approved | 3, step 2, frontend |
| Frontend approved                     | 3, step 3, backend  |
| Contract tests pass on the real one   | 3, step 4, verify   |

When an approval is not on record, ask; never assume one.

## Ground rules

1. Stack: keep the app's language, GUI framework and main libraries. Add
   libraries on top when they help (theming, icons, layout, tabs). Never
   switch framework alone: when another one would be clearly better, give
   the benefits, migration cost and risks, and ask.
2. The stack runs on macOS and Linux. When it cannot meet a requirement on
   one of them, say so before working around it.
3. Work on a new branch. Commit at the end of each phase.
4. Existing user settings and data keep working, or migrate automatically.
5. When the repo follows agent1's requirements, read
   [agent1.md](../../rules/agent1.md) sections GUI, Window and Component
   too. Where they and this skill disagree, ask which wins.

## Laws of UX

Before designing anything, read https://lawsofux.com/ in full: the main page
and every law's page it links to. Apply the laws to every design decision.
Name the laws behind the main decisions in the brief and in every mockup
round.

## Phase 1: Discovery

Interview before designing anything.

1. Read the codebase: what the app does, its current UI, its stack, what the
   backend can do.
2. Ask a few questions at a time (Claude Code: `AskUserQuestion`), about:
   1. Who uses it.
   2. The main tasks and workflows.
   3. Pain points with the current UI.
   4. How people would use multiple windows and tabs.
   5. Designs they like or dislike, and apps they find modern.
3. Challenge assumptions. Point out contradictions.
4. Write a short brief to `docs/design-brief.md`: goals, users, key screens,
   window and tab model, constraints, stack decisions, guiding Laws of UX.
5. Gate 1. Commit.

## Phase 2: SVG mockup review loop

1. Mockups go in `docs/mockups/`, one SVG per screen or state, named like
   `01-main-window-dark.svg`. Version them (`-v2`, `-v3`); never overwrite. Mockups and mockup generators are gitignored.
2. Start with 2 or 3 clearly different directions for the main screen. Let
   the user pick one before going into detail.
3. Draw detailed screens in one dark and one light theme only. Add one theme
   preview sheet showing all 8 themes, with the 5 proposed themes marked for
   approval.
4. Draw on the same layout grid and spacing scale as the final app.
5. The mockups also show:
   1. The visible keyboard focus state.
   2. The in-app help screen.
   3. A window with several tabs open.
   4. Two windows side by side.
   5. One screen on macOS and on Linux, so window controls, menu bar and
      shortcut labels differ visibly.
6. Write `docs/keyboard-map.md`: per screen, the tab order, focus groups and
   shortcuts, in macOS and Linux versions.
7. Write `docs/motion-spec.md`: every animation, with what moves, trigger,
   duration and easing. Key animations also get a before/after frame
   sequence in the mockups.
8. Each round:
   1. Show the mockups.
   2. Say what changed and why, with the Laws of UX behind it.
   3. Check alignment and component use across every screen. Name each
      intentional exception.
   4. Ask for specific feedback: layout, hierarchy, comfort, modern look,
      color, typography, animation, keyboard flow.
9. Iterate until the user says they are satisfied. Gate 2. Commit.

## Phase 3: Implementation

### Step 1: Contract

Before any UI code:

1. List everything the backend can do: functions, data models, events,
   errors, long-running operations.
2. Map each approved screen to the calls and data it needs.
3. Include what multiple windows and tabs need: shared state between
   windows, concurrent requests, saving and restoring sessions.
4. Write `docs/interface-contract.md`. Per call: name, inputs, outputs, error
   cases, sync or async, progress and cancel behavior where relevant.
5. Mark each call *existing*, *changed* or *new*. Flag every changed or new
   call that looks risky or expensive.
6. Gate 3. Commit.

### Step 2: Frontend first

1. Build the design tokens, motion tokens included, and the shared
   components with their animations built in. Build every screen only from
   those.
2. Build the window and tab system next; every screen lives inside it.
3. Build the full UI to the approved mockups and keyboard map: all themes,
   font scaling, multiple windows and tabs, the help system.
4. The UI talks to the backend only through the contract. No calls into
   backend internals.
5. Implement the contract as a stub layer returning realistic data,
   including errors, empty results and slow responses, so every UI state
   can be tested.
6. When the UI needs something the contract lacks, stop and propose a
   contract change. Never work around it.
7. Gate 4: show the finished frontend. Commit.

### Step 3: Backend second

1. Implement or adapt the backend to fulfill the contract exactly.
2. Write contract tests that run the same checks against the stub and the
   real backend.
3. Replace the stubs once the tests pass. Commit.

### Step 4: Verify

01. Write automated UI tests that drive every workflow with simulated key
    presses only, wherever the framework allows.
02. What cannot be automated goes in `docs/keyboard-checklist.md`, one entry
    per workflow. Run through it.
03. Run tests and checklist on macOS and Linux.
04. Test windows and tabs: many tabs, moving tabs between windows, closing
    with unsaved work, restoring after restart.
05. Check the layout at the largest font size and at 200% OS scaling.
06. Check animations on both platforms: no dropped frames, never blocking
    input, matching `docs/motion-spec.md`, reduced when reduce motion is on.
07. Consistency and polish pass: compare all screens side by side. Fix
    misaligned elements, off-scale spacing, duplicate component variants,
    missing interaction states, crowded areas, inconsistent labels and terms.
08. Keep existing functionality. List anything removed or changed.
09. Confirm existing settings and data load or migrate, and no stub code is
    left in the production path.
10. Tick every item in [references/done.md](references/done.md). Commit.

## Rules

1. Write no UI code before gates 2 and 3.
2. Every requirement in
   [references/requirements.md](references/requirements.md) applies to the
   mockups and the code alike.
3. Spacing, sizes, colors and motion come only from tokens.
4. Report a failed test or skipped check as it is; never call a phase done
   with one open.
