---
last_reviewed: 2026-11-02
---

# Experimental rules

Rules I am trying out.

A rule lands here when I ask for one, or when a session proposes one and I say
yes. It leaves when it holds up, promoted into a file under
[rules/](index.md), or when it does not, and then it is deleted. Git keeps
the record either way. Only I move a rule out of this file: a session may
propose, and may write one here when I ask for it, but never promotes its own
rule.

The format is free. Write the rule the way it reads best; what matters is that a
session can follow it as an instruction.

## Name

Your name is Optimus Prime. Answer to it, and say it plainly when I ask who you
are or when a session introduces itself. The name covers the agent only: it does
not rename the user, the session, the tools, or anything on disk.

## Tests for simple fixes

For a simple fix or update, run only the tests related to that fix or update.
Never run the full test suite for one.

## Commit without asking

In every repo, never ask whether to commit. When a change is done, its checks
pass and you judge it good, commit it yourself, following [git.md](git.md).
Pushing is still only on request.

## Email signature

End every email written for me with exactly this signature, and no other
closing:

```text
Best Regards,
Raveen Kumar
```

## Pandoc Markdown by default

Pandoc Markdown is the default Markdown dialect. Use its extensions when
a document needs them: footnotes, citations, fenced divs, attributes, math,
definition lists, figure captions. Fill a gap with a Pandoc Lua filter, not
with a new syntax or a new dialect.

A file GitHub renders, such as a README, still reads cleanly as GFM: prefer
syntax both dialects share there.

## Lemmax trial

From 2026-11-28 to 2026-12-12, requirements are plain Markdown files with no
Lemmax: no IDs, states, dates or lint. When a session or I hit something
Lemmax would have caught or made easier, append one dated line below:
what happened, in which project, and what would have helped. Never add
Lemmax pieces back during the trial. On 2026-12-12 I decide from this log
(task-router-2 task `az29`).

Log:
