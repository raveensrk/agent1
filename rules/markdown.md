---
last_reviewed: 2026-11-02
---

# Markdown

1. Real file references use Markdown links. Inline and fenced code are for
   literal text and syntax examples, not navigable file references. A link label
   may use inline code: `` [`guide.md`](doc/guide.md) ``.
2. Prefer relative link destinations inside repo documents. For spaces, use
   `%20` or an angle-bracket destination: `[Guide](<doc/my guide.md>)`.
3. Markdown does not expand `~`, `$VAR` or `${VAR}` in link destinations. Do not
   assume a renderer does; use them only when the consuming tool explicitly
   supports expansion. A leading `/` is a root-relative URL, not universally
   a filesystem path.
4. Keep every line you write or edit to 80 columns or fewer, tables included.
   Exempt: YAML frontmatter, and a line whose only overflow is one unbreakable
   token, such as a URL or a link. Do not rewrap lines you did not otherwise
   change.
5. Always align Markdown tables: pad cells so every column lines up.

Do : `[File Name](/path/to/file_name.md)`
Don't : `/path/to/file_name.md`

Same goes for images and media. For images and media use links with preview
`![]()`.

In replies, write the full URL and the full absolute file path. Use relative
paths only when writing documents inside a repo. For `@` imports in agent
startup instruction files (CLAUDE.md, AGENTS.md), use a `~/` path. Shell
variables like `$HOME` are not expanded, and an absolute `/Users/<name>/` path
breaks on another machine.
