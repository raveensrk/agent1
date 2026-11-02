# Common Archive

## Agent context files

- Pi loads `CLAUDE.md` and `CLAUDE.MD` alongside `AGENTS.md`. Never rename or convert `CLAUDE.md` for pi.

## Racket

Before any Racket work (writing, reviewing or debugging `.rkt` or `.scrbl` files,
or answering a Racket question), read the relevant parts of the Markdown Racket
docs in [Racket docs](~/.local/share/doc/racket). Start from the Guide for
concepts and the Reference for exact bindings, and find a binding with `rg`
instead of reading a whole manual. When the folder is missing,
`~/dot/install.sh --apply` builds it (`raco setup --doc-markdown`); say so
instead of working from memory.

## Verification

For multi-step, ambiguous, or high-impact work, say how you could verify it before starting. Skip it for small, well-defined changes.

- Verify a config change through the real entry point - the alias, the full startup - not a minimal load. A minimal load skips startup options and hides the failure until I hit it.
- A mechanism whose only real test is me pressing a key or looking at a window: ask for that one probe before building the rest of it. An Automator service passed `automator run`, then did nothing for three real key presses, and the route cost 25 minutes.
- Never report a keybind, hotkey or shortcut as working from a log line that merely correlated with my press. The evidence is the press, or a mechanism that answers to a synthetic event in the same session - skhd fires on `osascript -e 'tell application "System Events" to key code 105'`, a service shortcut never does.
- A poll loop that finds no process is not evidence that nothing fired. After a negative poll, read the target's own artifact (its log file) and say "not observed", not "did not fire".
- When a value you display mirrors one the vendor's own UI shows, fetch the endpoint that reproduces that exact number and compare it before shipping the field. A plausible field name is not the number.
- Run a new checker or validator over the whole existing population, not only the target it was written for. Its first run must pass on every instance, or it is reporting its own bugs.
- Error paths are verified by the offline unit tests. A live network command is for the happy path, once, bounded with a limit flag; a live call to prove a rejection costs a full fetch and an interruption.

After installing or removing pi packages, verify with `timeout 90 pi -p "reply with just: ok"` and check stderr for warnings.

## Documentation

Keep `doc/` and `AGENTS.md` in sync with the code. Cite sources when you can. Suggest new guidelines worth adding.

- Follow code-as-doc wherever practical: use clear code and keep small program-specific documentation in the program itself (docstrings, comments, or `--help`). Ask me before creating a separate documentation file.

- Before removing a path or a symlink, search the docs that reference it and update them in the same change.

## Repeatability

Every session must reconstruct identical context from this repo alone, across pi and any future harness. Store durable rules, conventions, context, and memories in version-controlled files. Never in agent-private memory. If it is worth remembering, commit it. Agent-private memory may hold only pointers back to the repo.

## Effort level

High effort is the default. Before executing **any** prompt:

1. Analyse the prompt and task.
2. Determine the best effort level for it (low / medium / high / extra / max).
3. Proceed at that level. Do not wait for confirmation.

## Plan mode and Brainstorming

Remind me to brainstorm and plan depending on the prompt and task. Decide based on your best judgement - for multi-step, ambiguous, or high-impact work; skip it for small, well-defined changes.

## AGENTS.md and `.agents/`

1. Agent instructions follow https://agents.md: plain Markdown in `AGENTS.md`,
   no required fields, one at the repo root and more in subprojects, the
   nearest file wins. `CLAUDE.md` is a one-line `@AGENTS.md` pointer and holds
   no rules of its own.
2. Skills follow https://agentskills.io/specification for what goes inside a
   skill, and the `.agents/skills/` convention for where it lives:
   `<project>/.agents/skills/<name>/SKILL.md` for one project,
   `~/.agents/skills/<name>/SKILL.md` for every project (see
   https://agentskills.io/client-implementation/adding-skills-support.md). Not
   in a client-only path like `.claude/skills/` or `.codex/skills/`. A repo that
   ships skills as a package, like this one's `skills/`, keeps its own layout.

## Output style: Telegraph

The rule moved out of this file, and now travels with its own switch:

- Rule text: `harness/extensions/telegraph.md`
- Injector: `harness/extensions/telegraph.ts`, `/telegraph on|off`
- Jev score line that reads it: `harness/extensions/voice_score.ts`, `/voice-score` for the last turn, `/voice-score -0` for the session

`/telegraph off` drops the section from the next request. Nothing to edit here.
