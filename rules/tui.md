---
last_reviewed: 2026-11-02
---

# TUI

Every TUI app I write has a help keybind, `?`, shown in the footer of the main
screen. It opens a help page that carries:

1. What the app is for, in a few sentences, and where its data lives.
2. Every keybind, grouped by screen or mode, each with a one-line description.
3. General help: how prompts behave, what colors and symbols mean, how to
   cancel, how to quit.

The help page moves like `less`, with vim keys:

| Key              | Does                                                           |
| ---------------- | -------------------------------------------------------------- |
| `j` `k`, `↓` `↑` | One line down, up                                              |
| `space` `f`, `b` | One page down, up                                              |
| `d`, `u`         | Half a page down, up                                           |
| `g`, `G`         | Top, bottom                                                    |
| `/`              | Search: type a pattern, `enter` jumps to the first match below |
| `n`, `N`         | Next, previous match, wrapping around                          |
| `esc`            | Clear the search, then leave the help page                     |
| `q`              | Leave the help page                                            |

Every match on screen is highlighted while a search is active, the current
match more strongly, and the footer shows `match 3 of 7` or `no match`.
Search ignores case unless the pattern has a capital letter, as in vim's
`smartcase`.
