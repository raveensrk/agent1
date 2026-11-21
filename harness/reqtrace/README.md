# reqtrace

Lint, trace and list a repo's org requirements.
Requirements: [requirements.org](requirements.org), RT-1 to RT-15.

```sh
reqtrace list --ready           # every requirement, grouped; only approved and open
reqtrace list --all --json      # every repo under ~/repos, for an AI
reqtrace next-id M              # the next free id, as M-15
reqtrace trace RT-3             # one requirement's links, tests and commits
reqtrace list -p ~/repos/arcadia_docs -p ~/repos/agent1   # named projects, from any folder
reqtrace lint --staged          # what the pre-commit hook runs
```

- `reqtrace --help` is the short help, `reqtrace help` the long one; each command takes both.
- `reqtrace` is a Bash launcher for `reqtrace.el`, run by `emacs -Q --script`.
- `install` puts a wrapper on PATH as `~/.local/bin/reqtrace`.
- `run_tests` runs the ERT tests in `reqtrace_tests.el`, each in its own Emacs, 8 at a time.
- `lint`, `commit-msg` and `trace` read files whose header has `#+REQTRACE_TESTS:`.
  `list` and `next-id` read every requirements file.
- The global hooks in `harness/githooks` call it: `pre-commit` runs
  `lint --staged --no-tests`, `commit-msg` runs `commit-msg`. A repo with no
  opted-in file never starts Emacs.
- `harness/checks/reqtrace_lint.py` runs `lint --no-tests` on each opted-in
  `.org` file an agent edits.
