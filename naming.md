# Naming

How to name programs, commands, skills, functions, variables, files and folders.

Status: alpha. These rules change as I work. Follow them for new names, but when a rule seems wrong for a real case, say so instead of forcing it.

## Every name

1. A name says what the thing is or does, explicitly. Short is fine; vague is not.
2. Read the name alone, without its help or context: if it could mean two things, rename it.
3. A name is easy to say and easy to read.
4. Any abbreviation is allowed (`pdf`, `ls`, `cmds`, `cfg`), as long as rule 2 still holds.
5. Join words with underscores: `code_style.md`, `,ls_comma_cmds`. No hyphens, no camelCase.

## Programs, commands, skills and functions

These do something, so the name is an action.

1. If it belongs to one tool, the tool's name comes first: `,mutt_…`, `,git_…`. This groups them under tab completion.
2. Then verb + object: `add_sender_to_spam`, `ls_comma_cmds`.
3. With no tool, start with the verb.
4. A bare noun or a generic verb does not count (`,path`, `,l`, `,update`).
5. Keep the connecting words that carry meaning (`to`, `from`, `as`, `in`), and drop articles (`the`, `a`). `convert_md_to_pdf` says which file becomes which; `convert_md_pdf` does not.

## Files and folders

These hold something, so the name is a noun phrase for what is inside: `naming.md`, `spam_rules.md`, `task/`. No verb. A tool prefix comes first when there is one: `mutt_spam_rules.md`.

Folders are singular: `doc/`, `note/`, `script/`, `task/`. The exception is a name a tool requires, such as `docs/` for GitHub Pages, `node_modules/` or `.github/workflows/`.

## Existing names

New names follow these rules. Rename an old name that breaks them only when you are already changing that thing for another reason.

## Examples

| Bad | Good | Why |
|---|---|---|
| `,mutt_spam_add_sender` | `,mutt_add_sender_to_spam` | Tool first, then verb + object. |
| `,comma_cmds_ls` | `,ls_comma_cmds` | No tool, so the verb comes first. |
| `,convert_md_pdf` | `,convert_md_to_pdf` | `to` shows the direction. |
| `,update` | `,update_brew_packages` | A generic verb alone could mean anything. |
| `define_naming.md` | `naming.md` | A file holds something; it does not act. |
| `code-style.md` | `code_style.md` | Underscores, not hyphens. |
| `notes/` | `note/` | Folders are singular. |
