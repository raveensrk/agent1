# lemmax

Lint, trace and list a repo's org theories.
lemmax was reqtrace until 2026-11-21; `#+REQTRACE_*` keywords still read.

<!-- lemma: 01a20336-cc5d-70ae-878b-b241ecc9ef61 -->

Theory: [theory.org](../theories/lemmax/theory.org).

<!-- lemma: 01a20336-cb25-779d-9e80-e04a22bd235d -->

Runs on macOS and Linux; on Windows through WSL or Git Bash, not natively.
Needs Emacs 29 or newer, git and Bash; `run_tests` also needs Perl.
The Org parts it loads all ship with Emacs: `org`, `org-element`, `org-attach`,
`org-archive`, `org-id` and `ox-publish`.

In Emacs, load `lemmax.el` and run `M-x lemmax-lint`, or any command as
`M-x lemmax-COMMAND`. It runs `lmx` in the buffer's folder and shows the same
output in `*lmx*`, where each finding links to its line.

```sh
lmx list --ready           # every statement, grouped; only approved and open
lmx list --all --json      # every repo under ~/repos, for an AI
lmx plan                   # the steps to rebuild the project: environment, then one lemma at a time
lmx next-id M              # the next free id, as M-15
lmx trace RT-3             # one statement's links, tests and commits
lmx trace --dot | dot -Tsvg > lemmas.svg   # the lemma graph
lmx list -p ~/repos/arcadia_docs -p ~/repos/agent1   # named projects, from any folder
lmx lint --staged          # what the pre-commit hook runs
```

- `list` and `trace` never run a repo's test command unless given `--run-tests`:
  the command is the repo's own code. `lint` runs it unless `--no-tests`.
- Every day lemmax reads or writes is a local day: today, and the commit days of `trace`. `TZ` picks the zone.
- `lmx --help` is the short help, `lmx help` the long one; each command takes both.
- `lemmax` is a Bash launcher for `lemmax.el`, run by `emacs -Q --script`.
- `install` puts a wrapper on PATH as `~/.local/bin/lemmax`; then, in each repo,
  `lmx install-hooks` writes `.git/hooks/pre-commit` and `commit-msg` to
  call it. A hook already there is kept as `NAME.local` and run after.
- `run_tests` runs the ERT tests in `lemmax_tests.el`, each in its own Emacs, 8 at a time.
  A test runs lemmax in its own Emacs (`rt-run`); a few run the real launcher
  (`rt-run-proc`) for the CLI wrapper and the hooks.
- A run sets `org-modules` to nil: Org's link modules took half a run to load.
  `golden/` pins `trace` and `list` output (`LEMMAX_UPDATE_GOLDEN=1` rewrites it);
  a seeded test parses 200 generated files; the mutation test turns each lint
  rule off in turn (`LEMMAX_MUTATE`) and needs a test to fail.
- `lint`, `commit-msg` and `trace` read files whose header sets `LEMMAX_TESTS`
  (see File settings), or that an old `lemmax/config.eld` names (see Config).
  `list` and `next-id` read every theory file.
- The global hooks in `harness/githooks` call it: `pre-commit` runs
  `lint --staged --no-tests`, `commit-msg` runs `commit-msg`. A repo with no
  opted-in file never starts Emacs.
- `harness/checks/lemmax_lint.py` runs `lint --no-tests` on each opted-in
  `.org` file an agent edits.

## Conjectures, proofs, lemmas and theorems

<!-- lemma: 01a20369-38d2-7202-8b53-6e296aaac489 -->

Conjecture + proof = lemma. A conjecture is a statement not yet proven: what it
says, ideas and design. A proof is a heading in `FILE.proofs.org` beside it:

```org
* PASSED Proof: lint reads states
:PROPERTIES:
:ID:          01a20369-...
:PROVES:      01a20369-38d2-7202-8b53-6e296aaac489
:TEST:        ert/lemmax-math-states
:END:
```

- Conjecture states: `CONJECTURE THESIS | LEMMA THEOREM REFUTED`; proof states: `OPEN | PASSED`.
  A `THESIS` is a conjecture the owner accepted to prove; `list --ready`
  lists them.
- A `LEMMA` has a proof, and every proof of it is `PASSED`. An `OPEN` proof is
  a counterexample until it passes: lint refuses the lemma.
- A theory, `theories/PROJECT/`, has one `THEOREM`, its whole claim; lint
  refuses a second. It reaches every statement of the theory through
  `:USES:`, and lint refuses one it does not reach. A `LEMMA` may `:USES:`
  other lemmas; each it uses must be proven. A `THEOREM` that reaches an
  unproven statement, a new or reopened one, is refused until it is `THESIS`
  again; the project is finished only when its theorem is proven.
  `lmx migrate --theorem ID` makes every other `THEOREM` of ID's theory a
  `LEMMA`, names in ID's `:USES:` each statement it does not reach (the
  roots only), and sends a proven ID that now reaches an unproven statement
  back to `THESIS`. Old `:NEEDS:` pointed child to parent, so `migrate`
  inverts it: the parent gets `:USES:`.
- A statement's text is its title and body. Its link properties, `:USES:`,
  `:PROVES:`, `:FOR:`, `:ABOUT:`, `:FOLLOWS:`, `:TEST:`, `:ALIASES:` and
  `:ROAM_REFS:` (and the old `:VERIFY:`, `:NEEDS:` and `:REFS:`), are not:
  changing one sends nothing back. A changed `:USES:` still makes it
  suspect, and `trace` says so.
- A statement is a heading, never a whole file: lint refuses a file whose top
  drawer holds `:STATE:`.
- A proof may prove many conjectures; a conjecture may have many proofs.
- A passing test is evidence, not proof: tests can refute a conjecture, never
  prove it. What makes a lemma hold is the owner's or judge's review of each
  conjecture and proof pair.

| Term       | Meaning                                                                                                                               |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Conjecture | A statement not yet proven                                                                                                            |
| Proof      | A heading in `FILE.proofs.org` that names tests in `:TEST:`                                                                           |
| Test       | Code that checks a conjecture. If it fails, the conjecture is wrong. If it passes, that supports the conjecture but does not prove it |
| Lemma      | A conjecture whose proofs all pass and whose pair is reviewed                                                                         |
| Theorem    | A lemma built on smaller proven lemmas named in `:USES:`                                                                              |
| Refuted    | A conjecture disproven or given up, kept with the reason                                                                              |

Example. The conjecture under test is a claim about lint: *lint refuses any
lemma that has an `OPEN` proof.* Its test feeds lint a sample file with one
lemma and one `OPEN` proof, and lint refuses it. The test passes.

Now suppose lint has a bug: it reads only the first proof of each lemma. Give it
a sample lemma whose first proof is `PASSED` and whose second is `OPEN`, and
lint lets it through. The claim about lint is false, yet the test still passes,
because the test never tried a lemma with two proofs.

A failing test shows a real case where the claim breaks. A passing test shows
only that the cases tried held. Review asks whether the tests cover the cases
that matter: no proofs, two proofs, one `PASSED` and one `OPEN`.

- Old files (`OPEN | DONE DROPPED`, `:NEEDS:`, `:VERIFY:`, `:APPROVED:`,
  `:PROVEN:`, `:IMPLEMENTED:`, `:LAST_EDITED:`) still read.
  `lmx migrate FILE` prints the move as a diff; `--write` makes it.

## Dates

<!-- lemma: 01a20e7b-c7c0-77fc-bc53-bc963ab4843f -->

Org's log dates a statement; lmx keeps no date of its own (see Created day).

```org
#+TODO: CONJECTURE(c) THESIS(h!) | LEMMA(l!) THEOREM(t!) REFUTED(r!)
#+STARTUP: logdrawer

* LEMMA Lint reads states
:PROPERTIES:
:ID:          01a20369-38d2-7202-8b53-6e296aaac489
:END:
:LOGBOOK:
- State "LEMMA"      from "THESIS"     [2026-11-24 Tue 11:00]
- State "THESIS"     from "CONJECTURE" [2026-11-23 Mon 09:30]
:END:
```

- The accepted day is the newest log line into `THESIS`; the proven day the
  newest into `LEMMA` or `THEOREM`.
- The last-edited day is the day of the newest commit that changed the
  heading's text, or today for a staged or unstaged change: one `git log` a
  file. The bible and manual warning and `archive` read it.
- A text change to a `THESIS`, `LEMMA` or `THEOREM` sends it back: lint
  refuses it until it is `CONJECTURE` and the owner accepts it again.
- A file in this form, with `THESIS` in its `#+TODO:` or `logdrawer` in its
  `#+STARTUP:`, needs no `:LAST_EDITED:`. Lint refuses a heading with both a
  log line and the property it replaces, `:APPROVED:`, `:PROVEN:` or
  `:IMPLEMENTED:`.
- `migrate` moves `:APPROVED:` and `:PROVEN:` into log lines dated as they
  were, newest first, makes each approved `CONJECTURE` a `THESIS`, deletes
  `:LAST_EDITED:`, writes the `#+TODO:` where the file reads it, a setup file
  too, and adds `logdrawer` to `#+STARTUP:`.

## Created day

<!-- lemma: 01a20ee1-7637-7169-820a-751b3c636847 -->

A heading's created day is read from its id or from git; lmx keeps no
`:CREATED:`.

- A UUIDv7 id's first 48 bits are its creation time, Unix milliseconds; lmx
  reads the day in the local zone (`TZ`).
- Any other id, as `RT-5`, takes the day of the first commit that has it, or
  today when no commit has it yet.
- `plan` puts older first by this day; a heading with no day sorts last.
  `trace` prints `created: DAY`; `list --json` gives `created`.
- Lint requires no `:CREATED:`. An old one still reads and wins; `migrate`
  deletes it from every heading, tasks and notes files too.

## Tasks, notes, axioms and definitions

<!-- lemma: 01a2038d-cc5f-7324-8de8-1b067284e640 -->

Four kinds need no proof:

- A task is a dev chore in `FILE.tasks.org`: `TODO | DONE CANCELLED`, an `:ID:`,
  dates, and `:FOR:` with the ids it serves. A commit may name its id.
- A note is text in `FILE.notes.org`: an `:ID:`, no state, `:ABOUT:` any ids.
- An `AXIOM` heading is a rule accepted without proof; agent1's are in
  `theories/agent1/axioms.org`. A proof may not prove one; a theorem may use one.
- A `DEFINITION` heading names a term, accepted without proof; Lemmax's are in
  [theory.definitions.org](../theories/lemmax/theory.definitions.org). A proof may not prove one; any statement
  may use one.

`list` groups each kind apart; lint checks their links.

## id: links in link properties

<!-- lemma: 01a203a6-a702-71c0-8239-e0d41380d2dd -->

`:USES:`, `:PROVES:`, `:FOR:`, `:ABOUT:` and `:FOLLOWS:` take bare ids and
`[[id:X][label]]` links, mixed. `lmx migrate --links` writes links.

## ORDERED and BLOCKER

<!-- lemma: 01a203a6-a716-738e-a95b-18086050d5eb -->

Lint reads Org's blocking properties and stays the authority: under
`:ORDERED: t`, a child may not be proven before an earlier sibling not yet
proven or refuted. Lint refuses `:BLOCKER:`: `:USES:` says what a statement
waits for; `migrate` deletes it.

## LOGBOOK

<!-- lemma: 01a203a6-a729-7420-980a-1702a0de05ad -->

With `#+STARTUP: logdrawer`, Emacs logs state changes to `:LOGBOOK:`, and lmx
reads its days (see Dates). The drawer is not a heading's text, so a log makes
nothing suspect. "Changed on" lines are still required.

## Archive

<!-- lemma: 01a203a6-a73d-7772-a4cb-fc4917fefd50 -->

`lmx archive FILE` lists REFUTED conjectures, CANCELLED tasks and DONE
tasks 30 days old (`--days N`); `--write` moves them with `org-archive-subtree`
to `NAME_archive.org` (`NAME_archive.tasks.org` for tasks). Lint reads archives,
so links resolve and ids stay unique.

## Attachments

<!-- lemma: 01a2090e-8591-756c-a9f1-dd473d9c3ce4 -->

Any heading with an `:ID:` may have files, kept as `org-attach` keeps them: in
the folder `org-attach-dir` gives, `:DIR:` or `data/` plus the id. Link them
with `attachment:NAME`, or any repo file with `file:`. Lint refuses an
`attachment:` link on a heading without the `:ATTACH:` tag, a linked file git
does not track, and a tracked file in an attach folder that nothing links; a
linked file over 5 MB is a warning. Web links, linked `.org` files and files
outside the repo are references. `trace` prints `files:`; `list --json` gives
`files`.

## Publish

<!-- lemma: 01a203a6-a752-75ed-8359-a8147e95a33d -->

`lmx publish` writes every listed lemmax file to HTML with `ox-publish`;
id: links become page links. Pages go to `.lemmax/html/` (git ignores it
through `.lemmax/.gitignore`), or `--out DIR`.

<!-- lemma: 01a2090e-8b52-7173-947b-d882b237ad05 -->

Pages are HTML5 with inline images: a linked PNG, GIF or SVG shows in place.
Every linked file is copied beside the pages with `org-publish-attachment`. A
video is a `#+begin_video` block under `#+ATTR_HTML: :src FILE :controls t`;
lint refuses a video linked any other way.

## Book

<!-- lemma: 01a20927-9aac-7817-8e46-8635aa0ae127 -->

`lmx book` writes the whole theory as one HTML file, `.lemmax/book.html`
or `--out FILE`. It joins every theory file and companion with `#+INCLUDE:`
in `.lemmax/book/book.org`, in rebuild order: definitions and axioms first,
each lemma before what uses it. `id:` links point inside the page, and every
image and video is packed in as a `data:` URI, so the file opens offline alone.

## theories/

<!-- lemma: 01a20930-0aba-7005-8442-d1dc3269c487 -->

Every repo keeps all its Lemmax data in `theories/`, one subfolder per
project, as `theories/lemmax/`, each with a `setup.org` its files read with
`#+SETUPFILE:`. Lint refuses a theory file outside it.
`publish` writes a page per file and a book per project under
`theories/_site/`, which git ignores; `book --all` adds one book for the repo.

<!-- lemma: 01a20caa-4660-77a9-bf48-db8448f75366 -->

A project's main theory file is `theory.org`, with companions such as
`theory.proofs.org`. Lint refuses any file named `requirements.org`,
`requirements.X.org` or `requirements_X.org`, and names the file to use.

<!-- lemma: 01a20d28-cb41-760a-a477-e1704807a2a8 -->

A finished project's bible and manual, `theories/PROJECT/PROJECT.bible.html`
and `PROJECT.manual.html`, are written by an agent running the `/docs` skill,
never by lmx. `lint` warns, and never refuses, when one is missing or older than
the theory.

<!-- lemma: 01a20a84-971d-767f-8a26-c98f6d132b7f -->

A move that rewrites a statement's file link to name the same file, as moving
a theory into `theories/` does, is no text change: `lint --staged` reads each
relative link as the repo file it names, after the staged renames.

<!-- lemma: 01a20c8e-872d-75b3-97fe-22718d4b809b -->

A link, or a `:FOLLOWS:` path, that named a file now gone may be mended to
name any file: that is no text change either.

## SETUPFILE

<!-- lemma: 01a203a6-a766-76c6-9931-753ee75e9318 -->

`#+SETUPFILE: lemmax.setup` brings in `#+TODO:`, `#+TAGS:`, `#+STARTUP:` and
`#+PROPERTY:` lines, as Org reads them; a relative path is read from the
file's folder in the work tree. `org-enforce-todo-dependencies` is an Emacs
setting, so a setup file cannot turn it on.

## Footnotes

<!-- lemma: 01a203a6-a779-73fc-8abf-99f8c8816867 -->

Footnotes and citations may stand in a body and count as its text. Lint
refuses a `[fn:NAME]` with no `[fn:NAME] text` line in the file; org-cite is
left to export.

## Tags

<!-- lemma: 01a2039c-9e67-74bb-9ac4-63eac14f1e7c -->

Every heading takes org tags. A file declares them in `#+TAGS:`, and lint
refuses any other. Group tags nest them: `#+TAGS: [ cli : list trace ]`.
A heading's tags include its ancestors' and `#+FILETAGS:`. Tags are not a
heading's text. `lmx list --tag cli` and `lmx trace --tag cli` show
headings tagged `cli` or a tag under it; `--tag` again means AND.

## Code markers

A comment line whose first words are `lemma:` and ids links code to its lemmas.
`lmx trace ID` lists each `code:` and `test:` location, `lmx list` counts
them, and `lmx lint` refuses a marker naming no lemma or a dropped one, and a
lemma done from 2026-11-22 on with no code marker. `lmx list --unmarked`
shows older done lemmas without one. Test paths default to `test/`, `tests/`,
`e2e/`, `_test.`, `-test.`, `.spec.` and `_tests.`; the `LEMMAX_TEST_PATHS`
setting replaces them.

## File settings

<!-- lemma: 01a20eb5-f066-7481-9fd1-9ac7705ef6b2 -->

A file's settings are Org `#+PROPERTY:` lines, read as Org reads them, through
`org-keyword-properties`:

```org
#+PROPERTY: LEMMAX_TESTS lemmax/run_tests --addresses
#+PROPERTY: LEMMAX_CODE lemmax/
#+PROPERTY: LEMMAX_CODE+ harness/checks/lemmax_lint.py
```

- The settings: `LEMMAX_TESTS` (the test command; it opts the file in),
  `LEMMAX_CODE`, `LEMMAX_TEST_PATHS` and `LEMMAX_MARKERS_IN`.
- A `#+PROPERTY:` line in a `#+SETUPFILE:` counts; `NAME+ value` adds to the
  value, Org's rule.
- Settings are file-level only: lint refuses a `LEMMAX_` property in a
  heading's `:PROPERTIES:` drawer.
- The old `#+LEMMAX_TESTS:` keywords still read; lint refuses a file, with what
  its setup file brings in, that sets one setting both ways. `lmx migrate`
  moves each keyword into a `#+PROPERTY:` line in place, in a theory file, its
  setup file, a setup file or a proofs file given alone.
- The hooks and `lemmax_lint.py` treat a file with a `#+PROPERTY: LEMMAX_TESTS`
  line as opted in, as they do the old keyword.

## Config

<!-- lemma: 01a20ed2-d34b-71f9-a19a-04bb7cc6cf6e -->

Repo-wide settings are `#+PROPERTY:` lines in `theories/setup.org`, and each
project's `setup.org` reads it with `#+SETUPFILE: ../setup.org`; Org brings
its lines in, as it does any setup file, nested too:

```org
#+title: Repo settings
# Repo-wide lmx settings; each project's setup.org reads this with #+SETUPFILE: ../setup.org.
#+PROPERTY: LEMMAX_MARKERS_REQUIRED_FROM 2026-11-22
#+PROPERTY: LEMMAX_COVERAGE_REQUIRED_FROM 2026-11-22
#+PROPERTY: LEMMAX_REPOS ~/repos
```

- `LEMMAX_MARKERS_REQUIRED_FROM YYYY-MM-DD` makes a done lemma proven on or
  after that day need a `lemma:` code marker (none set: none needs one).
- `LEMMAX_COVERAGE_REQUIRED_FROM YYYY-MM-DD` makes lint refuse code above a
  file's first `lemma:` marker in code files changed on or after that day
  (`lmx list --uncovered` lists every such file).
- `LEMMAX_REPOS DIR` is the folder `list --all` and cross-project `trace`
  read (else the `LEMMAX_REPOS` variable, else `~/repos`); they read it from
  `theories/setup.org` at the repo root, with no file at hand.
- A folder's settings are its project's own `#+PROPERTY:` lines (see File
  settings). A theory file gets settings only through its header: a lemma
  file with no header and no `#+SETUPFILE:` has none.
- The hooks and `lemmax_lint.py` treat a repo as opted in by a
  `#+PROPERTY: LEMMAX_TESTS` line.

An old `lemmax/config.eld` still reads, as data with `read-eval` off, never
run, until it is migrated; while it names a `:tests` it opts the repo in, and
its `:folders` entries still give a file with no settings of its own the
entry of the longest folder that holds it:

```elisp
(:markers-required-from "2026-11-22"
 :folders (("theories/lemmax/" :tests "lemmax/run_tests --addresses" :code ("lemmax/"))))
```

- Lint reports a form that does not read, an unknown key, or a folder with no
  tracked file, and refuses a setting set both there and by a `#+PROPERTY:`
  line: a folder entry's key and a file's header, or a top key and a
  repo-wide line.
- `lmx migrate lemmax/config.eld` prints the move as a diff; `--write` makes
  it: the top keys go to `theories/setup.org` (made with a `#+title:` and a
  comment), each `:folders` entry to its folder's `setup.org` unless that
  already sets the key, each `theories/PROJECT/setup.org` gets
  `#+SETUPFILE: ../setup.org`, and the config is deleted.

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
- `:ROAM_REFS: URL...`, as org-roam reads it, names the issues, PRs or specs
  a lemma came from; `trace` prints them and `list --json` gives them as
  `refs`. An old `:REFS:` still reads; `migrate` renames it.

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

`.github/workflows/lemmax.yml` runs the tests and `lmx lint` on every push
and pull request, on Emacs 29.4 and 30.1. `lint` runs the repo's own test
command, so in CI a pull request's code runs: the workflow has a read-only
token and no secrets, as GitHub gives `pull_request` from a fork. Never run
lemmax under `pull_request_target`, which has the base repo's secrets.

## Output and exit codes

These are stable from 1.0.0:

- A finding is one line on stderr: `lmx: FILE:LINE: ID: WHY; FIX`, with `-`
  for no id. `lint --json` prints them instead as
  `{"version": 1, "findings": [{"file", "line", "id", "why", "fix"}]}` on stdout.
- Exit 0: clean. Exit 1: a finding, or lemmax could not do what was asked.
  Exit 2: lemmax cannot run here (no Emacs, or one older than 29).
