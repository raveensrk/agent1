---
id: "mzq8tw9asj"
title: "Add natural language input to the todo CLI"
state: "obsolete"
due: ""
priority: "C"
tag: ["todo"]
repeat: ""
effort: ""
postpone: 0
created: "2026-10-04"
closed: "2026-10-08T20:47"
---

Asked for 2026-10-03, deferred the same day: keep the CLI deterministic, exact and accurate first.

Decisions already made, so a later attempt starts from them:
  - the CLI parses the sentence itself: a deterministic grammar in Emacs Lisp, no model, no network, instant, testable in scripts/test
  - a ref may be loose: case-insensitive, unique prefix or word match (bike -> Clean bike); an ambiguous match refuses and lists the candidates
  - loose dates on the strict verbs too: tomorrow, next friday, in 3 days
Open question: which verbs a sentence reaches - the 13 sayable ones, all 24, or the write verbs only.

Shape wanted, for reference: todo say "postpone cut nails to tomorrow"
Obsolete: Dropped by Raveen on 2026-10-08, no reason given
