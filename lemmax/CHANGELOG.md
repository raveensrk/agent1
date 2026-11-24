# Changelog

lemmax follows [semantic versioning](https://semver.org/). `list --json`
and `lint --json` carry their own `version`, the number of their shape.

## Unreleased

- Repo-wide settings are `#+PROPERTY:` lines in `theories/setup.org`:
  `LEMMAX_MARKERS_REQUIRED_FROM`, `LEMMAX_COVERAGE_REQUIRED_FROM` and
  `LEMMAX_REPOS`, read through each project's `#+SETUPFILE: ../setup.org`.
  An old `lemmax/config.eld` still reads; lint refuses a setting set both
  there and by `#+PROPERTY:`. `lmx migrate lemmax/config.eld` moves it and
  deletes it. A config opts a repo in only while it names `:tests`.
- File settings are Org `#+PROPERTY:` lines: `#+PROPERTY: LEMMAX_TESTS CMD`,
  `LEMMAX_CODE`, `LEMMAX_TEST_PATHS` and `LEMMAX_MARKERS_IN`, read as Org reads
  them, from a `#+SETUPFILE:` too, `NAME+` appending. Lint refuses one in a
  heading's drawer, and a setting set both as a property and an old
  `#+LEMMAX_*:` keyword, which still reads. `migrate` moves each keyword into
  a `#+PROPERTY:` line; the hooks and `lemmax_lint.py` opt such a file in.
- A new state, `THESIS`, between `CONJECTURE` and the done states: a
  conjecture the owner accepted to prove.
  `#+TODO: CONJECTURE(c) THESIS(h!) | LEMMA(l!) THEOREM(t!) REFUTED(r!)` with
  `#+STARTUP: logdrawer` makes Org log each change in `:LOGBOOK:`.
  `list --ready` lists the theses.
- The accepted day is the newest log line into `THESIS`, the proven day the
  newest into `LEMMA` or `THEOREM`. The last-edited day is git's: the newest
  commit that changed the text, or today for a change not committed; the
  bible and manual warning and `archive` read it.
- In the logged form lint needs no `:LAST_EDITED:`, refuses a text change to a
  `THESIS`, `LEMMA` or `THEOREM` until it is `CONJECTURE` again, and refuses a
  log line beside its `:APPROVED:` or `:PROVEN:`. Old files read as before.
- `migrate` moves `:APPROVED:` and `:PROVEN:` into log lines, makes each
  approved `CONJECTURE` a `THESIS`, deletes `:LAST_EDITED:`, and writes the
  new `#+TODO:`, in a setup file when the file reads it there.

## 1.0.0 - unreleased

The first public release.

- Every command is an M-x command, `M-x lemmax-lint` and the others; each
  runs `lmx` and shows its output in `*lmx*`.
- `lint`, `commit-msg`, `trace`, `list`, `new-id`, `next-id` over org
  requirements ("lemmas"), as headings or one lemma per file.
- Settings in `lemmax/config.eld`, by folder, read as data and never run.
- `[[id:]]` links, backlinks, `:ALIASES:`, `:REFS:`, `list --unlinked` and
  `trace --dot`, after org-roam and org-id.
- `lemma:` code markers, checked both ways.
- `list` and `next-id` read `theory.org` and `theory/` by name, beside
  `requirements.org` and `requirements/`.
- Today and commit days are local days; `TZ` picks the zone. They were UTC.
- A LEMMA or THEOREM records its day in `:PROVEN:`; `:IMPLEMENTED:` is still read, and
  `migrate` renames it.
- `DEFINITION` headings name terms, accepted without proof; `definitions.org`
  holds Lemmax's.
- Messages, help and internal names say "statement" for an item and "theory
  file" for a file of them, not "requirement". `requirements.org` is still read.
- Reads only files that can hold lemmas, once a run.
- `list` and `trace` run no repo command unless given `--run-tests`.
- `#+SETUPFILE:` keywords; footnote definitions checked.
- `lmx publish` and `lmx archive`; id: links in link properties and `migrate --links`;
  `:ORDERED:` and `:BLOCKER:` read by lint; `:LOGBOOK:` is not text.
- `lmx plan` prints the steps to rebuild a project, one lemma at a time,
  in `:USES:` order; ties by priority, then age, then id; `--json` too.
- Coverage: with `:coverage-required-from DAY`, lint refuses code above a
  file's first `lemma:` marker in files changed from DAY; `list --uncovered`
  lists them. A proof's id marks its tests, never other code.
- `FILE.env.org`: Toolchain (`:VERSION:`), Data, Setup and Secrets (`:WHERE:`
  only); lint checks them and `plan` prints them as its first steps.
- Tags: declared in `#+TAGS:`, nested by group tags, inherited; `list --tag`
  and `trace --tag`. Tags are not a heading's text.
- Tasks (`FILE.tasks.org`), notes (`FILE.notes.org`) and `AXIOM` headings,
  which need no proof; a commit may name a task id.
- The math names: conjectures (`CONJECTURE | LEMMA THEOREM REFUTED`),
  proofs in `FILE.proofs.org` (`OPEN | PASSED`, `:PROVES:`, `:TEST:`),
  `:USES:` for theorems, and `lmx migrate`. Old files still read.
- `:VERIFY:`, `:NEEDS:` and `:USES:` are no longer part of a requirement's
  text: changing them no longer reopens a DONE requirement or makes its
  children suspect.
- Attachments: any heading's files, in the folder `org-attach-dir` gives; lint
  checks the `:ATTACH:` tag, untracked links and orphans; `trace` shows
  `files:`, `list --json` a `files` array.
- `publish` shows images in place, copies linked files and writes video
  blocks as `<video>`.
- `lmx book` writes the theory as one self-contained HTML file.
- `theories/`: every repo keeps its theory there, a subfolder per project;
  lint refuses a theory file outside it; `publish` and `book` write to
  `theories/_site/`. agent1's own theory moved there.
- A move that rewrites a link to name the same file is no text change: a
  proven statement stays proven.
- Mending a link, or a `:FOLLOWS:` path, to a file that is gone is no text
  change either.
- Lint refuses a theory file named `requirements*.org`; every repo names it
  `theory.org`.
- The program is `lmx`, so it is never confused with LemmaX, the workflow;
  `lemmax` stays on PATH as an alias.
- `lint` warns when a finished project has no bible or manual, or one is
  older than the theory; the `/docs` skill's agent writes them.
