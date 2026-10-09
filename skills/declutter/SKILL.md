---
name: declutter
description: >-
  Find and delete unnecessary apps on macOS - unused GUI apps, brew formulae
  and casks, leftover Library dirs from uninstalled apps. Builds a dark,
  self-contained HTML report; the user picks what goes via checkboxes
  (exports declutter-selection.json); the skill deletes safely:
  brew uninstall for brew items, everything else moved to ~/.Trash, never rm.
  Logs verified program removals in ~/dot_local/app_cleanup.yaml and checks
  every run for reinstalls, asking the user Keep or Remove when one returns.
  Use when the user asks to clean up their Mac, delete unused apps,
  free disk space, declutter, or find apps they do not use.
metadata:
  invocation_hint: "[--scan | --delete ~/Downloads/declutter-selection.json]"
---

# declutter

Scan, report, user decides, delete safely. The skill judges nothing on its own:
badges are suggestions, checkboxes are the user's decision, Trash is the undo.

## Run

Before each run, check the persistent program log:

```sh
python3 scripts/ledger.py check
```

Read `reinstalled` before proceeding, even for programs hidden by the ignore list.
For each returning program, ask **Keep** or **Remove**, with its installed path or
Homebrew token. Never infer Remove from an earlier uninstall. Record the answer:

```sh
python3 scripts/ledger.py decide ID --choice keep
python3 scripts/ledger.py decide ID --choice remove
```

Keep records an allowed installation, preserving its removal history and avoiding
repeat prompts. Remove records intent only: add the currently installed item to
the selection and use the dry-run/confirmation flow below. An inventory failure
is unknown, not proof of absence; resolve it before claiming verification.
`scan.py` also includes this check in its JSON as `reinstall_check`.

1. Scan + build report (read-only):

   ```sh
   mkdir -p ~/tmp/declutter
   python3 scripts/scan.py > ~/tmp/declutter/scan.json
   python3 scripts/report.py ~/tmp/declutter/scan.json -o ~/tmp/declutter/report.html
   open ~/tmp/declutter/report.html
   ```

   Requirements: macOS, python3 3.9+, PyYAML, Homebrew (optional except when
   checking or removing previously logged Homebrew packages).
   Scan needs Spotlight (`mdls`) for last-used dates; missing dates show as "unknown".

2. Tell the user: review the report, tick rows, press **Export selection**
   (lands in `~/Downloads/declutter-selection.json`). They may instead just
   tell you which rows to drop.

   Rows can also be marked **ignore** (link in the name column) - ignored rows
   stop appearing in future scans. If the export has an ignore list, apply it
   before anything else:

   ```sh
   python3 scripts/delete.py ~/Downloads/declutter-selection.json --save-ignore
   python3 scripts/scan.py > ~/tmp/declutter/scan.json   # re-scan, ignores now hidden
   python3 scripts/report.py ~/tmp/declutter/scan.json -o ~/tmp/declutter/report.html
   ```

3. Dry run (always first, never skip):

   ```sh
   python3 scripts/delete.py ~/Downloads/declutter-selection.json
   ```

4. Show the dry-run output, ask for explicit confirmation.

5. Only after a clear "yes, delete": `python3 scripts/delete.py ... --execute`.
   Program removals are logged automatically in `~/dot_local/app_cleanup.yaml`
   only after app/path and Homebrew checks verify absence. Dry runs and failed
   removals never enter the program log. Re-run `python3 scripts/ledger.py check`
   and compare the installed inventory with the scan from before removal.
   Then remind them to empty the Trash once happy.

## What the report shows

- Headline cards: items scanned, JUNK count, reclaimable bytes.
- Top-10 size bars.
- Sortable, filterable table: badge (KEEP/MAYBE/JUNK), name, size, last used,
  kind (app / formula / leftover). Locked rows: running apps, brew formulae
  other formulae need. Duplicate installs flagged.
- Badge rules: JUNK = unused 90+ days or never opened, MAYBE = 31-90 days,
  KEEP = used in the last 30 days.

## Safety rules

- Never run `--execute` without showing dry-run output and getting explicit
  user confirmation of that output.
- Deletion routes: brew cask -> `brew uninstall --cask`, brew formula ->
  `brew uninstall` (refused if any installed formula depends on it), manual
  apps and leftovers -> moved to `~/.Trash` (recoverable, never `rm`).
- `delete.py` refuses paths outside `/Applications`, `~`, Caskroom, Cellar.
- Leftover rows are heuristic (substring match) - tell the user to eyeball
  them before selecting.

## Phase 2 - files (built)

`scan.py` also scans regenerable file junk, same report and flow:
Xcode DerivedData (per project), CoreSimulator caches, brew/pip/yarn
caches, `~/Library/Logs`, and `node_modules` dirs (home-wide find,
depth 5). Sub-1MB crumbs are skipped. Age = directory mtime, so a
cache used today shows KEEP. All file rows go to Trash, things rebuild
on next use.
