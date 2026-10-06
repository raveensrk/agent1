# Harness wiring

One guard script, one contract, N thin configs. The contract is already shared
by four harnesses: **JSON on stdin, exit 2 blocks the tool call, stderr is the
reason the model reads.** That is what makes the layer harness-agnostic - only
the wiring below is per harness.

Verify the block after wiring it: run the command by hand and confirm the agent
is refused. A guard nobody watched fire is a guess.

Each `command` below writes the guard's own path as `GUARD`: substitute yours.

## Claude Code

Project hooks: `.claude/settings.json`. User scope: `~/.claude/settings.json`.
Exit code 2 blocks and feeds stderr to the model.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$GUARD\""
          }
        ]
      }
    ]
  }
}
```

Known gap: `PreToolUse` exit 2 has leaked on `Write`/`Edit` (anthropics/claude-code
#13744) and caused an idle halt rather than a reaction to stderr (#24327). Return
JSON with `permissionDecision` when tool-level nuance matters, and keep the git
floor.

## Codex

`.codex/hooks.json` at the git root, or `[hooks]` tables in `.codex/config.toml`.
The same decision can also be returned as JSON on stdout instead of exit 2.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "^Bash$",
        "hooks": [
          {
            "type": "command",
            "command": "/usr/bin/python3 \"$GUARD\"",
            "statusMessage": "Checking the command"
          }
        ]
      }
    ]
  }
}
```

Repo-local hooks load only in a trusted project, and Codex records trust against
the hook's hash: a new or edited hook is skipped until trusted. Review it with
`/hooks`. Hooks also need `[features] hooks = true`, or `--enable hooks`.

## Cursor

`.cursor/hooks.json` for the project, `~/.cursor/hooks.json` for the user.
`matcher` is a regex against the shell command, so the guard runs only when git
is in the command. Exit 2 blocks; any other nonzero code fails open.

```json
{
  "version": 1,
  "hooks": {
    "beforeShellExecution": [
      {
        "command": "python3 \"$GUARD\"",
        "matcher": "git",
        "timeout": 30
      }
    ]
  }
}
```

## Gemini CLI

`.gemini/settings.json`. `matcher` is a regex against the tool name, and
`run_shell_command` is the shell tool. Exit 2 blocks and stderr is the reason.

```json
{
  "hooks": {
    "BeforeTool": [
      {
        "matcher": "run_shell_command",
        "hooks": [
          {
            "name": "guard",
            "type": "command",
            "command": "python3 \"$GUARD\""
          }
        ]
      }
    ]
  }
}
```

## pi

Pi loads these extensions live from this repo as a local package: `package.json`
declares `harness/extensions/*.ts` under the `pi` key, and `settings.json` in the
dotfiles repo lists `"~/repos/agent1"` under `packages`. No symlinks in either
repo. `command_guard.ts` is the working version, with its test in
`harness/tests/test_command_guard.ts`.

## opencode

A plugin in `.opencode/plugin/`. Throwing from `tool.execute.before` blocks the
tool call.

## The reactive half

The guard blocks before the work; the checks report after it. pi wires
`harness_lint.ts` itself. The same `lint.py --changed` call goes into each
harness's end-of-turn hook, where the documented semantics differ:

| Harness | Event | How findings reach the model |
| --- | --- | --- |
| Claude Code | `Stop` | exit 2, stderr is the feedback |
| Codex | `Stop` | `{"decision":"block","reason":"..."}`, or exit 2 with stderr |
| Gemini CLI | `AfterAgent` | exit 2 retries the turn with stderr |
| Cursor | `stop` | JSON on stdout `{"followup_message": "..."}`, so it needs a wrapper |
| pi | extension | `harness_lint.ts` ships and does this |

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$HOME/repos/agent1/harness/lint.py\" --changed"
          }
        ]
      }
    ]
  }
}
```

`lint.py --changed` looks only at files this session touched, because a repo
full of old findings would otherwise nag on every turn.
