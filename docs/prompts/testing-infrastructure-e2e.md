# Build testing infrastructure and end-to-end tests

Build the testing infrastructure for this desktop app and cover it with
end-to-end tests. The app may ship a CLI, a TUI, a GUI, or several of them,
with or without a shared core. It runs on macOS and Linux. No Windows.

**Goal: when every test passes, I trust the app works for a real user.** Tests
drive the app the way a user does: the real binary, real keystrokes, real
clicks, real files on disk. Mocks only where the real thing is out of reach.

## Phase 1: survey, then wait for approval

Read the code before writing anything. Then give me:

1. **App inventory.** Every app in the repo: kind (CLI, TUI, GUI), language,
   toolkit, platforms, how it is built and launched.
2. **Feature list.** Every user-facing feature of each app. This becomes the
   e2e coverage checklist.
3. **Existing tests.** What exists, what runs, what passes, what is dead.
   Ask me what to do with each existing test setup before replacing it.
4. **Stack choices.** For each app kind, the test runner and driver you pick,
   and why. Prefer tools native to the app's language and toolkit. Name the
   alternatives you rejected.
5. **Data and side effects.** Every file, directory, env var, network call,
   clock read, git repo or system service the app touches. On macOS include
   `~/Library/Application Support`, `~/Library/Preferences`, `NSUserDefaults`,
   the Keychain and caches.
6. **Platforms.** Where the Linux tests run (a VM, a container, CI or another
   machine) and where the macOS tests run. If you have no Linux environment,
   ask me.
7. **CI.** Whether the repo has CI and runners for macOS and Linux. If it has
   none, ask me. Don't set CI up unasked.
8. **Time budgets.** Your estimate of run time per layer, and two budgets you
   propose: one for the default command (run many times a day, for example
   under 30 s) and one for the full suite. I approve both.

Don't start Phase 2 until I approve.

## Phase 2: infrastructure

- **Layers.** Unit tests for the app's logic, integration tests for its
  internal API (the core, if the app has one), end-to-end tests for every app.
  Write the tests for every layer, not only the setup. Each layer runs on its
  own and all together.
- **One command per platform.** One entry point (for example `./test` or
  `make test`) covers every app on that platform. Exit code is non-zero on
  any failure.
  - Bare, it runs the fast layers (unit, integration, CLI e2e).
  - A flag runs the full suite, slow layers (TUI, GUI) included. CI runs that.
  - Flags select a layer, an app, a single test, or only the tests related to
    the files changed.
- **Development speed first.** Tests must not get in the way of day-to-day
  work.
  - Unit tests finish in seconds. The default command and the full suite stay
    within their approved budgets; flag anything that pushes one over.
  - No slow test runs in a git hook or blocks a commit unless I ask for it.
  - Every run prints its slowest tests with their times.
  - Low upkeep: tests assert behavior, not implementation details, so a
    refactor doesn't break them. Use snapshots and goldens sparingly, and keep
    them one command to update. A new feature adds tests; it doesn't force
    rewrites of old ones.
- **Isolation.** Every test runs in a fresh temp directory with its own `HOME`,
  `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME` and app config. No test
  reads or writes my real data, config, keychain or git repos. Before and
  after the suite, snapshot the real data and config locations (file list and
  modification times) and fail if they changed.
- **macOS isolation.** Env vars don't redirect `~/Library` paths,
  `NSUserDefaults` or the Keychain, and an app started through `open` or
  LaunchServices ignores the test's env. Add an explicit override to the app
  (a flag or env var for its data, config and defaults domain). Launch the app
  in a way that passes that override: the binary directly, or the GUI driver's
  launch API (for example `XCUIApplication`'s `launchEnvironment` and
  `launchArguments`). Tests never touch the real locations.
- **Determinism.** Fixed clock, fixed random seed, fixed locale (`LANG=C.UTF-8`)
  and timezone (`TZ=UTC`), fixed terminal size. No real network: use local fake
  servers or recorded fixtures. Tests pass in any order. Unit, integration, CLI
  and TUI tests run in parallel; GUI tests may run one at a time, since they
  share one desktop, focus and front window.
- **Fixtures.** Test data and app state live in fixture files, one copy shared
  by every layer and every app. Each language gets one builder that loads
  them.
- **Artifacts on failure.** Keep stdout, stderr, logs, the sandbox directory,
  and for TUI and GUI a screen capture of the failing moment. Print their
  paths.
- **No duplication.** One copy of every helper, driver, fixture and config.
  Helpers shared across apps in the same language live in one place.

## Phase 3: end-to-end tests per app kind

Cover every item on the feature list, the happy path and the main failure
paths. Check each feature off when its tests pass.

### CLI

- Every command keeps a set of tests that run the built binary as a
  subprocess. When startup is slow (a JVM, for example), the bulk input cases
  may call the CLI entry point in process, so the default command stays within
  budget.
- Assert exit code, stdout and stderr separately.
- Cover `-h`, `--help`, `help`, bad flags, missing args, bad input, empty
  state, large input, and piped stdin and stdout (no TTY).
- Golden files for long output, with one command to update them. Review every
  golden diff before accepting it.
- Compare files the command writes exactly. Where they hold timestamps, IDs or
  other run-specific values, normalize those fields first, then compare.

### TUI

- Run the real binary in a pseudo-terminal with a fixed size.
- Send real keystrokes, including control keys, arrows, resize and `Ctrl-C`.
- Assert on the rendered screen (a terminal emulator parses the output), not
  on raw escape codes. Snapshot screens where layout matters.
- Wait on screen content with a timeout. No fixed sleeps.
- Cover the `?` help screen, every keybind, every view, quit, and the terminal
  restored after a normal exit, a panic or uncaught error, and `SIGTERM`.

### GUI

- Launch the real built app. Drive it through the accessibility tree, or the
  toolkit's own UI test framework where it is the more reliable driver.
  Pixel-coordinate clicks only as a last resort.
- Give every interactive widget a stable accessibility identifier. Add them to
  the app where missing.
- macOS: name the driver you chose (for example XCUITest for SwiftUI and
  AppKit, or the Accessibility API from a script) and the permissions it needs.
  Tell me every permission I must grant by hand.
- Linux: run headless under a virtual display (Xvfb, or a headless Wayland
  compositor) and drive the app through AT-SPI or the toolkit's test API.
- Wait on UI state with a timeout. No fixed sleeps.
- Cover every window, menu, shortcut, dialog, light and dark mode, window
  resize, and quit with unsaved state.
- Screenshot snapshot tests only where layout regressions matter, with a
  tolerance and one command to update them.

### Cross-app

- Where apps share data, one test writes through one app and reads through
  another.
- If a previous release exists, data it wrote still loads.

## Phase 4: CI and docs

- If the repo has CI (or I approved adding it), CI runs the full suite on macOS
  and Linux on every push, GUI tests included. If a GUI layer cannot run in CI
  on one platform, tell me why and what runs instead.
- A `TESTING.md` (or the repo's existing docs) explains: how to run each
  layer, how to run one test, how to update goldens and snapshots, how to debug
  a failure from its artifacts, and how to add a test for a new feature.

## Rules

- Tests find a bug: don't change app behavior. Mark the test as an expected
  failure that names the bug, and keep going. At the end of the phase, report
  every bug with its failing test and ask me which to fix. Don't wait for my
  answer: carry on with the next phase, and fix a bug only after I pick it.
- Testability changes (accessibility ids, a data or config path override, an
  injectable clock) are fine without asking; list them in the final report.
- Flaky tests are bugs. Never add blind retries. Find the cause and fix it; if
  you can't, quarantine the test, mark it, and tell me.
- Commit at the end of each phase that changes files. Ask before creating a
  branch or pushing.
- Done means: every feature on the checklist covered, the full suite green on
  macOS and Linux (expected failures aside), within the approved budgets, run
  three times in a row with no flake.
- If something in this prompt conflicts with what you find in the code,
  **stop and ask**. Don't guess.

## Final report

- The feature checklist with each test that covers it.
- Test counts and run time per layer and per platform.
- Every bug found, with its expected-failure test.
- Every app change made for testability.
- Gaps: what is not covered, and why.
