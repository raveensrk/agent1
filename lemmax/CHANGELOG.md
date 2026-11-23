# Changelog

lemmax follows [semantic versioning](https://semver.org/). `list --json`
and `lint --json` carry their own `version`, the number of their shape.

## 1.0.0 - unreleased

The first public release.

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
- `lemmax publish` and `lemmax archive`; id: links in link properties and `migrate --links`;
  `:ORDERED:` and `:BLOCKER:` read by lint; `:LOGBOOK:` is not text.
- `lemmax plan` prints the steps to rebuild a project, one lemma at a time,
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
  `:USES:` for theorems, and `lemmax migrate`. Old files still read.
- `:VERIFY:`, `:NEEDS:` and `:USES:` are no longer part of a requirement's
  text: changing them no longer reopens a DONE requirement or makes its
  children suspect.
- Attachments: any heading's files, in the folder `org-attach-dir` gives; lint
  checks the `:ATTACH:` tag, untracked links and orphans; `trace` shows
  `files:`, `list --json` a `files` array.
