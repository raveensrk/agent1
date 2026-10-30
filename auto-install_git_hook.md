# Auto-Install Git Hook

**Goal:** On macOS, the GUI apps of one target repo stay current in `~/Applications/My_Apps` after commits and pulls. The target is the repo I name, or the current repo (the git root of the working directory) if I don't name one.

**Scope:**
- Put `post-commit`, `post-merge` and `post-rewrite` in the target repo only, in a tracked `.githooks/` folder, enabled with `git config --local core.hooksPath .githooks`. git has no post-pull hook.
- Don't touch `agent1/harness/githooks` or any other repo.
- Make the hooks self-contained: copy the coalescing and notification logic into the repo rather than sourcing it from the harness.
- If the target currently uses the harness through `core.hooksPath`, carry every harness hook it relies on into `.githooks/`, and list them.
- Reuse the repo's existing path filter and build command. If either is missing, derive it from the project, state what you chose, and ask before going further.
- Commit `.githooks/` and the change to how hooks are enabled in one commit; don't push. Add a line to the README that a fresh clone needs `git config core.hooksPath .githooks`.

**Triggers:**
- Install when HEAD moves on the default branch and the diff from old HEAD to new HEAD touches the app's paths.
- The default branch is `origin/HEAD`. If that's unset, run `git remote set-head origin -a`. If it's still unset, fall back to `main`.
- This one rule covers commits, amends, merges (pulled or local), fast-forwards, and rebases (pulled or manual).
- Do nothing if HEAD didn't move ("already up to date") or the branch isn't the default branch.
- Dedupe by target SHA. One commit may fire several hooks.

**Build:**
- Build the committed tree (not the working tree) in the background, with coalescing (latest commit wins) and macOS notifications for success and failure.
- Stamp the source SHA into Info.plist during the build, before signing. If the build can't do that, re-sign afterwards (`codesign --force --deep -s -`) and verify with `codesign --verify`.

**Install:**
- Stage each build in `~/Library/Caches/My_Apps/staging/<App>.app`. Newer builds replace older staged ones. Create `~/Applications/My_Apps` if it doesn't exist.
- If the app isn't running, swap it in right away.
- If it is running, never quit it. A detached waiter swaps the staged build in once the app exits. Every hook run also swaps in any staged build whose app has stopped running, so a reboot can't strand an update.
- Exception: background helpers get quit, swapped, and relaunched right away. A helper is an app whose Info.plist sets `LSUIElement` or `LSBackgroundOnly`, or that a plist in `~/Library/LaunchAgents` launches. Restart LaunchAgent-managed helpers with `launchctl kickstart -k`; relaunch the others with `open`.

**Migrate existing installs (one-time, target repo only):**
- Find copies of the target repo's apps outside `My_Apps`, in `/Applications` and `~/Applications` (including subfolders). Match by bundle ID, not by name.
- Move each one into `~/Applications/My_Apps`. If `My_Apps` already has a copy, keep the one with the newer stamped SHA or version, and move the other to `~/Library/Caches/My_Apps/old/` instead of deleting it.
- Never move a running app. Queue it for the waiter, which moves it once the app quits.
- If a move needs admin rights, stop and ask me; never use `sudo` on your own.
- Update Dock items, Login Items and LaunchAgent plists that point at the old path. Then reload the changed LaunchAgents (`launchctl bootout` / `bootstrap`) and restart the Dock (`killall Dock`).
- If you aren't sure an app came from this repo (a bundle ID clash, or a copy from the App Store or a download), ask before touching it.
- Don't touch apps from other repos.

**Safety:**
- Hooks always exit 0 and never block or fail the git operation.
- On non-macOS, hooks do nothing.
- `MY_APPS_DIR` overrides the install destination, for tests only.

**Verify:**
- In a scratch clone of the target repo, with `MY_APPS_DIR` set to a temp folder, test:
  - fast-forward, merge, pull-rebase and manual rebase
  - already up to date, a non-default branch, and an amend
  - a commit that doesn't touch the app
  - an install while the app is running: it stays open, and the new build lands after you quit it
  - a helper restart, if the repo has a helper
- Confirm `codesign --verify` passes on the installed bundle.
- Confirm other repos' hook setup is unchanged.
- After migration, confirm no copy of the target's apps remains outside `My_Apps`, apart from ones left for the waiter or skipped as uncertain.
- Then do one real pull in the target repo. If it has no new commits, skip that step and say so.
- Confirm the installed bundle's stamped SHA equals HEAD.

**Report:** Hooks added, harness hooks carried over, path filter and build command used, apps and helpers found, apps migrated (old path → new path) and any skipped or left for the waiter, test results, and final install paths.

