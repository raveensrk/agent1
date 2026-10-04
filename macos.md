# macOS

Split from [common.md](common.md); routed by [rules_context.ts](harness/extensions/rules_context.ts).

- iTerm2: to open a tab that runs a command, create a plain tab, then `write text "cd DIR && cmd"`. `create tab with default profile command "..."` skips the login shell, so PATH misses `/opt/homebrew/bin` and the tab dies. While pi is open, address the bash window by `id`, never `current window`: `current window` is the pi TUI and the text becomes a user message. Do not `write text` into a tab that is waiting at a password prompt, and never redirect that prompt's stderr; the tab looks hung and the first characters are eaten as the answer.

- `zcat` fails on `.gz` files (BSD `zcat` expects `.Z`). Use `gunzip -c` or `gzip -dc`.

- BSD `sed` fails with `parentheses not balanced` when `|` is both the delimiter and an alternation (`s|(a|b)|x|`). Use another delimiter, for example `#`.

- BSD `cat` has no `-A`. Use `cat -v -e`, or `sed -n l` to show line ends and tabs.
  The guard refuses `cat -A` and prints both forms.

- `pgrep` on macOS has no `-c`. Count with `pgrep ... | wc -l`.

- `defaults write` cannot take a preference key containing spaces or parentheses, which is every pbs.plist service entry. Use `/usr/libexec/PlistBuddy` for those.

- A screenshot path under `/var/folders/.../TemporaryItems/NSIRD_screencaptureui_*` is deleted within minutes. Copy it into `~/tmp` before referring to it.

- A hung process names its own wait: `sample <pid> 2` prints its stack. For an
  Emacs daemon that is normally `select-safe-coding-system-interactively` ->
  `completing-read`, a prompt nobody can answer, so bound the run instead.
