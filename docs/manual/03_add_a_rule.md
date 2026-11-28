# Add a rule

A rule is plain Markdown in [docs/rules](../rules/README.md). Before you write
one, ask whether a program could decide it; if so, write a check instead
([Add a check](05_add_a_check.md)) and keep only the judgement in prose.

## Try it first

New rules start in [experimental.md](../rules/experimental.md). Ask a session to
add one, or say yes when a session proposes one. Every session loads the file
whole, so the rule is live at once. Only you move it out:

- It holds up: move it into the topic file it belongs to.
- It does not: delete it. Git keeps the record.

## Make it permanent

- Put it in the topic file it fits: `git.md` for commits, `markdown.md` for
  Markdown, and so on. Rule files keep topic names, not numbers.
- A new topic file needs a line in the [rules entry page](../rules/README.md)
  saying when to read it. If it must be read at session start, add it to the
  topic list in the rules context extension too, so the prompt names it.
- Machine-specific rules go in the private agent2 repo, not here.

Start a new session to load it.

______________________________________________________________________

[Previous: Daily use](02_daily_use.md) · [Next: Add a skill](04_add_a_skill.md)
