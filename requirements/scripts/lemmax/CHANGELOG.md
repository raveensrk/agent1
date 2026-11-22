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
- Reads only files that can hold lemmas, once a run.
- `list` and `trace` run no repo command unless given `--run-tests`.
- `lemmax publish` and `lemmax archive`; id: links in link properties and `migrate --links`;
  `:ORDERED:` and `:BLOCKER:` read by lint; `:LOGBOOK:` is not text.
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
