# The plugin and the pi package

Each harness has its own way to load code from a folder. agent1 uses each one's
native way, so nothing is copied or linked and the clone is the only copy.

## pi: a local package

The repo is a pi package. Its package manifest carries the `pi-package` keyword
and a `pi` key with three lists:

- `extensions`: every extension in the harness extensions folder, except the
  model picker, which is opt-in.
- `skills`: the skills folder, except its index page.
- `prompts`: the prompts folder, [docs/prompts](../prompts/README.md). pi turns
  each file name into a slash command, so prompt files keep their names
  (hyphens allowed) and the folder's contents page is left out.

pi's settings list the clone under `packages`; pi then loads it live on every
start. The extensions run in process.

## Claude Code: a directory plugin

The repo is also a Claude Code plugin marketplace with one plugin. The
marketplace manifest names the marketplace `raveen-agents` and its one plugin
`agents`, rooted at the repo itself; the plugin manifest gives the plugin's name,
description and version. Claude reads a directory plugin live from the
checkout: an edit loads at the next session start or `/reload-plugins`, with no
update step. Skills appear as `agents:<skill>`.

Install also copies the plugin root, minus `.git`, into Claude's plugin cache
under the marketplace, plugin and version. That copy is not what loads and goes
stale: only a version bump plus an update writes a new one. It still costs disk,
so a plugin root is kept small (measured with claude 2.1.293 and 2.1.294,
2026-10-09).

## The hook wiring

Claude Code does not run pi extensions. Instead the plugin's hook file wires
each Claude hook event to one command-line entry point, which reads the event
JSON on stdin and calls the same exported functions the pi extensions use:

| Claude event                        | Entry point command | pi extension it shares code with |
| ----------------------------------- | ------------------- | -------------------------------- |
| `SessionStart`                      | `rules`             | rules context, telegraph         |
| `PreToolUse` on Bash and Edit       | `guard`             | command guard, edit guard        |
| `PostToolUse`, `PostToolUseFailure` | `nudge`             | failure nudge                    |
| `Stop`                              | `lint`              | harness lint                     |

A fifth command, `telegraph on|off|status`, flips the shared voice switch from a
shell. The rule lives in the extension; the entry point only translates the
event, so changing a rule changes it in both harnesses.

The entry point's contract: exit 0 allows, with the hook's JSON on stdout when
it has something to say; exit 2 blocks (guard), stderr is the reason; exit 1 is
a usage error. `HOME` locates every path; it reads no other environment
variable. For the Stop hook it finds the edited files by reading the
transcript for Edit, Write and NotebookEdit tool calls. Each hook costs about
0.1 s of startup (measured 2026-10-08). Claude's own `/telegraph` command is
archived.

## Codex

Codex has no import syntax and no wiring yet; it reads its instruction file
verbatim, so a project tells it in words to read the rules entry page. See the
[manual](../manual/01_install.md#codex).

______________________________________________________________________

[Previous: Git hooks](05_git_hooks.md) · [Next: Install and uninstall](07_install_and_uninstall.md)
