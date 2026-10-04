# External systems and accounts

Split from [common.md](common.md); routed by [rules_context.ts](harness/extensions/rules_context.ts).

- A probe of an external system is one script taking the query as an argument; a
  second near-identical script is a rewrite, not a probe. Six CDP probe scripts
  were copied one per question on 04 Oct 2026, and the command analyzer missed
  all six because each had a different filename.

- A live external account is real data. Before the first write to one - a playlist, a mailbox, a third-party API - ask once and name what changes, then prototype on a scratch resource you create rather than the user's own. The real account is only touched by a command the user asked for by name.

- A credential materialized to disk - a browser cookie jar, a copied cookie
  database, a browser profile holding a live session - is deleted in the same tool
  call that stops needing it, never left across tool calls. A console session
  cookie sat in `~/tmp` for 50 minutes beside three copied browser profiles.
