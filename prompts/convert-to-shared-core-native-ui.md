# Convert an existing app to a shared core + CLI + native apps

Migrate this existing codebase to a **shared core with a CLI and a native macOS GUI**, plus optional extra apps. You don't need to keep a working app or version during the migration. Breakage is acceptable. The final version must be well tested and working.

- **Targets.** CLI app and native macOS GUI app. Both are mandatory and both use the shared core. The mandatory macOS GUI must use a native macOS toolkit; a cross-platform GUI does not count.
- **Optional.** Any number of extra apps on the same core: a TUI, a native Linux GUI, more GUIs on the same platform (for example a Swift, a Clojure and a Rust app on macOS), or cross-platform apps. Extra apps may use any toolkit. After both mandatory targets are done and tested, ask me which extra apps to build.
- **Full feature parity.** Before starting, list the current app's features. Each GUI and TUI app you build must have every feature. The CLI must have every feature that fits a command; list the features it skips and why. Check each feature off when it works.
- **Tests.** Unit tests for `core`, integration tests for the CLI, UI tests for every other app you build. A cross-platform app is tested on each platform it supports. On each platform, one command runs every test for the apps `apps.rec` lists for that platform, and all must pass.
- **Stack choices.** You choose the core language, the CLI language, the macOS UI framework and the bridge to `core`. Tell me each choice and why before starting. For each extra app, you also choose its language and toolkit; tell me those choices and why when I approve building it.
- **One repo.** All apps and the core live in the same repo, even when they use different programming languages. Layout at the repo root:
  - `core/`: shared logic with one public API.
  - `core/bindings/<lang>/`: one binding per language, shared by every app in that language.
  - `apps/<name>/`: one folder per app, named for the app, not the platform (for example `cli`, `tui`, `macos-swift`, `macos-clojure`, `linux-gtk`). A cross-platform app has one folder.
  - `apps.rec`: a GNU recfile with one record per app: name, language, toolkit, platforms, mandatory or optional. The test command reads it.
- **Existing apps.** If the repo already contains apps, ask me what to do with each one before starting.
- **Never duplicate.** No copy of any code, test helper, build script, config or doc; keep one copy and share it. Code used by more than one app lives in `core`; code used by more than one app in the same language lives in that language's binding. Keep each app thin.
- **Approval.** Wait for my approval after the feature list, the stack choices and the existing-app questions. Don't start work until I approve.
- If something in this prompt conflicts with what you find in the code, **stop and ask**. Don't guess.
