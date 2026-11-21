# lemmax

Lint, trace and list a repo's org requirements.
Requirements: [requirements.org](requirements.org), RT-1 to RT-15.

```sh
lemmax list --ready           # every requirement, grouped; only approved and open
lemmax list --all --json      # every repo under ~/repos, for an AI
lemmax next-id M              # the next free id, as M-15
lemmax trace RT-3             # one requirement's links, tests and commits
lemmax list -p ~/repos/arcadia_docs -p ~/repos/agent1   # named projects, from any folder
lemmax lint --staged          # what the pre-commit hook runs
```

- `lemmax --help` is the short help, `lemmax help` the long one; each command takes both.
- `lemmax` is a Bash launcher for `lemmax.el`, run by `emacs -Q --script`.
- `install` puts a wrapper on PATH as `~/.local/bin/lemmax`.
- `run_tests` runs the ERT tests in `lemmax_tests.el`, each in its own Emacs, 8 at a time.
- `lint`, `commit-msg` and `trace` read files whose header has `#+LEMMAX_TESTS:`.
  `list` and `next-id` read every requirements file.
- The global hooks in `harness/githooks` call it: `pre-commit` runs
  `lint --staged --no-tests`, `commit-msg` runs `commit-msg`. A repo with no
  opted-in file never starts Emacs.
- `harness/checks/lemmax_lint.py` runs `lint --no-tests` on each opted-in
  `.org` file an agent edits.
