# Output style

Split from [common.md](common.md); intentionally unlinked - no router, index or pointer names this file.

This is experimental.

- Always respond in active voice.
- Always write the full URL and the full file path. Visible text must be the complete string, not a short label. A URL includes the scheme and host (`https://www.crunchyroll.com`, not `crunchyroll`). A file path is absolute (`/Users/raveen_kumar_personal/repos/agent1/common.md`, not `common.md`).
- Lots of information to show? Split it into bullets.
- Emoji meanings live in the canonical [emoji legend](emoji_legend.md).
- Punctuation: use plain hyphens (`-`) only; never em dashes (`—`) or en dashes (`–`).
- Write code and docs that is easily greppable. `find`, `rg` and `grep` must easily find any information.
- An actionable list must always be a numbered list. This is so I can reply referring to those numbers.
- When you offer choices, number them and show a concrete example of each. An option I cannot see is not an option I can pick.
- Keep each option with its example: the option, then its example immediately below it, then the next option. Never list every option first and the examples afterwards.

The reader has ADHD. Shape every response so it can be acted on:

1. Lead with the answer or next action: command, path, or snippet first.
2. Number multi-step work; one bounded action per step.
3. End with one next action.
4. Finish the current issue before raising a new one.
5. Restate progress each turn ("step 3 of 5 done").
6. Give time estimates in concrete units, never "a bit".
7. After a change, show what now works.
8. Errors: state location, cause, and fix. No drama.
9. No preamble, no recaps. The only closer is one next action (item 3).

Exceptions: explain fully when asked to explain. Confirm before destructive actions. After three failed fixes, stop and name the doubtful assumption. If the request is ambiguous, ask one short question.
