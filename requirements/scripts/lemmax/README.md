# lemmax

Lint, trace and list a repo's org requirements.
Requirements: [requirements.org](requirements.org), RT-1 to RT-15.

<!-- lemma: 01a20336-cb25-779d-9e80-e04a22bd235d -->

Runs on macOS and Linux; on Windows through WSL or Git Bash, not natively.
Needs Emacs 29 or newer, git and Bash; `run_tests` also needs Perl.

```sh
lemmax list --ready           # every requirement, grouped; only approved and open
lemmax list --all --json      # every repo under ~/repos, for an AI
lemmax next-id M              # the next free id, as M-15
lemmax trace RT-3             # one requirement's links, tests and commits
lemmax trace --dot | dot -Tsvg > lemmas.svg   # the lemma graph
lemmax list -p ~/repos/arcadia_docs -p ~/repos/agent1   # named projects, from any folder
lemmax lint --staged          # what the pre-commit hook runs
```

- `list` and `trace` never run a repo's test command unless given `--run-tests`:
  the command is the repo's own code. `lint` runs it unless `--no-tests`.
- Every day lemmax reads or writes is a UTC day: today, and the commit days of `trace`.
- `lemmax --help` is the short help, `lemmax help` the long one; each command takes both.
- `lemmax` is a Bash launcher for `lemmax.el`, run by `emacs -Q --script`.
- `install` puts a wrapper on PATH as `~/.local/bin/lemmax`.
- `run_tests` runs the ERT tests in `lemmax_tests.el`, each in its own Emacs, 8 at a time.
  `golden/` pins `trace` and `list` output (`LEMMAX_UPDATE_GOLDEN=1` rewrites it);
  a seeded test parses 200 generated files; the mutation test turns each lint
  rule off in turn (`LEMMAX_MUTATE`) and needs a test to fail.
- `lint`, `commit-msg` and `trace` read files whose header has `#+LEMMAX_TESTS:`,
  or that `lemmax/config.eld` names (see Config).
  `list` and `next-id` read every requirements file.
- The global hooks in `harness/githooks` call it: `pre-commit` runs
  `lint --staged --no-tests`, `commit-msg` runs `commit-msg`. A repo with no
  opted-in file never starts Emacs.
- `harness/checks/lemmax_lint.py` runs `lint --no-tests` on each opted-in
  `.org` file an agent edits.

## Code markers

A comment line whose first words are `lemma:` and ids links code to its lemmas.
`lemmax trace ID` lists each `code:` and `test:` location, `lemmax list` counts
them, and `lemmax lint` refuses a marker naming no lemma or a dropped one, and a
lemma done from 2026-11-22 on with no code marker. `lemmax list --unmarked`
shows older done lemmas without one. Test paths default to `test/`, `tests/`,
`e2e/`, `_test.`, `-test.`, `.spec.` and `_tests.`; `#+LEMMAX_TEST_PATHS:`
replaces them.

## Config

`lemmax/config.eld` at a repo's root holds its settings by folder, so lemmas
may be headings in one file or one lemma per `.org` file, with no header:

```elisp
(:folders
 (("requirements/" :tests "./run_tests --addresses" :code ("src/")
   :test-paths ("tests/") :markers-in ("../code"))))
```

- Top-level keys, beside `:folders`: `:markers-required-from "YYYY-MM-DD"` makes
  a DONE lemma implemented on or after that day need a `lemma:` code marker
  (no key: none needs one); `:repos "DIR"` is the folder `list --all` and
  cross-project `trace` read (else `LEMMAX_REPOS`, else `~/repos`).
- A file takes the entry with the longest folder that holds it; `""` is the root.
- A file with any `#+LEMMAX_*` line of its own uses only its header.
- It is read as data with `read-eval` off and never run; `lint` reports a form
  that does not read, an unknown key, or a folder with no tracked file.
- The hooks and `lemmax_lint.py` treat a repo with the file as opted in.

## Lemma files

A file whose top property drawer has `:ID:` is one lemma, as an org-roam file
node: `#+title:` is its title, `:STATE:` its OPEN, DONE or DROPPED, and
headings in it are body, not lemmas. Every rule for a heading lemma holds.

```org
:PROPERTIES:
:ID:          01a2...
:STATE:       OPEN
:CREATED:     2026-11-22
:LAST_EDITED: 2026-11-22
:END:
#+title: Bar does the thing

Body text.
```

## Links

`[[id:ID]]` links a lemma by its `:ID:`; lint refuses one to an unknown or
DROPPED id. `trace ID` prints `linked from:` for each lemma, and each other
`.org` file and line, that links to it; `list --json` gives `linked_from`.
`list --unlinked` prints each `FILE:LINE: ID` where an `.org` file names an id
in plain text, as org-roam's unlinked references; lint never reports it.

## Aliases and refs

- `:ALIASES: ID...` keeps old ids working: markers, `:NEEDS:`, `id:` links,
  commit messages and `trace ID` that name an alias count as the lemma. lint
  refuses an alias two lemmas share, or one that is a lemma's `:ID:`.
- `:REFS: URL...` names the issues, PRs or specs a lemma came from; `trace`
  prints them and `list --json` gives them as `refs`.

## References and inspirations

- [org-roam](https://github.com/org-roam/org-roam) and Org's own
  [org-id](https://orgmode.org/manual/Handling-Links.html): file nodes,
  `id:` links, backlinks, aliases, refs, unlinked references and the graph
  view; lemmax borrows each as a read-only check.
- [Doorstop](https://github.com/doorstop-dev/doorstop): requirements as one
  file per item in version control, settings per folder, and suspect links
  when a parent changes.
- [StrictDoc](https://github.com/strictdoc-project/strictdoc): a plain-text
  requirements format with parent links and traceability to source and tests.
- [OpenFastTrace](https://github.com/itsallcode/openfasttrace): tags in code
  and tests that trace to requirements, and a report of what is not covered;
  the idea behind `lemma:` markers.

## Licence

MIT; see [LICENSE](LICENSE). Changes by release: [CHANGELOG.md](CHANGELOG.md).

## CI

`.github/workflows/lemmax.yml` runs the tests and `lemmax lint` on every push
and pull request, on Emacs 29.4 and 30.1. `lint` runs the repo's own test
command, so in CI a pull request's code runs: the workflow has a read-only
token and no secrets, as GitHub gives `pull_request` from a fork. Never run
lemmax under `pull_request_target`, which has the base repo's secrets.

## Output and exit codes

These are stable from 1.0.0:

- A finding is one line on stderr: `lemmax: FILE:LINE: ID: WHY; FIX`, with `-`
  for no id. `lint --json` prints them instead as
  `{"version": 1, "findings": [{"file", "line", "id", "why", "fix"}]}` on stdout.
- Exit 0: clean. Exit 1: a finding, or lemmax could not do what was asked.
  Exit 2: lemmax cannot run here (no Emacs, or one older than 29).
