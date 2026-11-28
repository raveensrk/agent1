# Agent brief header

Put this at the top of every brief handed to a subagent or a parallel agent,
then write the task below it. The task may tighten these rules, never loosen
them.

## Safety

- Never touch the user's real data. Run commands only on throwaway copies under
  `~/tmp` (a copy of `samples/`, a fresh file, a temp repo). Unset or override
  the environment variables that point at real data (`MY_DIARY_DATA`,
  `*_FILE`, `TASK_ROUTER_CONFIG` with `TASK_ROUTER_SANDBOX=1`), and check the
  override took before anything writes.
- Never run a command that writes to an outside service or the user's live
  stores (Contacts, Reminders, a sync that pushes) unless the task says so.
- Do not launch or drive the user's installed apps; read the code instead, or
  start a fresh build in the background.
- Edit only the repos the task names. Temp files go under `~/tmp`.

## Git

- Commit when the work is done and checked, following
  [git.md](../rules/git.md); never push.
- No AI co-author or attribution lines.
- Never `--no-verify`; hooks only lint, so a hook that refuses is a real
  problem to fix.

## Tests and checks

- Tests run only when the task asks for them; then only the tests related to
  the change, never the full suite.
- Syntax and help checks are fine: `bash -n`, `python3 -m py_compile`,
  `x -h`.
- Run `~/.local/bin/mdformat` on changed Markdown; check that relative links
  and heading anchors resolve.

## Asking and reporting

- Ask nothing; decide, and list open doubts in the report.
- Report short: what changed, checks run and their results, commit ids, doubts.
  Say plainly what was not checked.
