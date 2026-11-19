---
name: docs
metadata:
  scope: global
description: Create or update docs/ as a book-style design doc and repo bible, complete enough that an engineer can rebuild the project from docs/ alone - with D2/TALA and Mermaid diagrams, a build script for checks and PDF/EPUB export, an AGENTS.md pointer and a docs-only rebuild test. Use when the user says create docs, write the docs, document this repo, write a design doc or repo bible, docs book, update the docs, sync the docs, docs are stale, or runs /docs. Create mode researches first, interviews the user, waits for an OK on the outline, and works on a docs-book branch without pushing. Update mode brings an existing book in line with the code.
argument-hint: "create|update [repo path]"
---

# Create or update docs: the book of this repository

Use `docs/` or `doc/`, whichever exists. If neither exists, create `docs/`.

## Modes

Two modes, picked by the first argument:

- `create` - write the book from scratch, or rebuild a docs folder that is not yet a book. Runs Phases 1-7.
- `update` - bring an existing book in line with the repo. Runs [Update mode](#update-mode).

No mode given: `update` if `docs/README.md` has a table of contents and `docs/build.sh` exists, `create` otherwise.
Say which mode was picked in the first line.

## Goal

Create `docs/`: a book-style design doc and repo bible for this repository.

Done means:

- A software engineer who has never seen this repo can rebuild an equivalent project from `docs/` alone, without the source code.
- Every fact lives in exactly one place and can be reached from `docs/README.md`.
- It reads well on GitHub, on GitLab, in local editors, and printed as PDF or EPUB.

Write for humans first.
AI agents get a short section in `AGENTS.md` that points here.

## Ground rules

- All documentation goes in `docs/`. Create it if it's missing. If it exists, build on it: keep what's correct, fix what's stale, fold in the rest.
- Git: work on a new branch `docs-book`, commit at the end of every phase that changes files, and never push. If the working tree has uncommitted changes, stop and ask first. Skip git steps if this isn't a git repo.
- Questions: batch them, and give each one your recommended answer with a one-line reason. Outside the Phase 2 interview, ask at most one batch per phase. If the user doesn't answer, use your recommendation for wording choices only; never move, delete or install anything without a yes.
- Never guess intent or rationale. Anything still unanswered goes in the Open questions chapter, with where it matters.
- No secrets, tokens, personal data or internal hostnames. Document config keys, not their values.

## References

Official sources for the rules in this skill.

| Read | For |
| ---- | ---- |
| [CommonMark spec](https://spec.commonmark.org/) | Base Markdown syntax; latest is 0.31.2 |
| [GFM spec](https://github.github.com/gfm/) | Tables, task lists, strikethrough, autolinks |
| [GitHub alerts](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#alerts) | Callout syntax |
| [GitLab alerts](https://docs.gitlab.com/user/markdown/#alerts) | How GitLab renders callouts |
| [Mermaid docs](https://mermaid.js.org/intro/) | Diagram syntax |
| [Mermaid config schema](https://mermaid.js.org/config/schema-docs/config.html) | `htmlLabels` and theming |
| [Mermaid CLI](https://github.com/mermaid-js/mermaid-cli) | `mmdc` options: background, config file |
| [D2 tour](https://d2lang.com/tour/intro) | D2 language |
| [D2 CLI manual](https://d2lang.com/tour/man/) | Flags, themes, layout engines |
| [TALA layout engine](https://d2lang.com/tour/tala/) | What TALA supports: position locking, per-container direction, `near` |
| [TALA is open source](https://d2lang.com/blog/tala-is-open-source/) | Bundled since D2 v0.9.0; seeds and trade-offs |
| [Graphviz docs](https://graphviz.org/documentation/) | DOT language, `dot -Tsvg` |
| [librsvg](https://gitlab.gnome.org/GNOME/librsvg) | `rsvg-convert`, used to check diagram labels |
| [C4 model](https://c4model.com/) | System context and container diagrams |
| [MADR](https://adr.github.io/madr/) | Decision record format |
| [markdownlint-cli2](https://github.com/DavidAnson/markdownlint-cli2) | Lint config and rules |
| [lychee](https://github.com/lycheeverse/lychee) | Link checking, including anchors |
| [pandoc manual](https://pandoc.org/MANUAL.html) | `--file-scope`, `--pdf-engine`, GFM input |
| [AGENTS.md](https://agents.md/) | Agent instruction file format |
| [Claude Code and AGENTS.md](https://code.claude.com/docs/en/memory#agents-md) | When Claude Code reads `AGENTS.md`, and the `@AGENTS.md` import |

## Phase 1: Read, explore and research (write nothing yet)

1. Follow every URL in References and read it.
2. Map the whole repo and read everything that defines behavior: code, config, build and CI files, tests, git history, existing docs and notes.
3. Research well, from official sources: current versions and docs of the repo's languages, frameworks and key dependencies, the external services and APIs it uses, and its domain terms. Also check whether anything in References has changed since this skill was written.
4. Check for `d2` v0.9.0 or later (it bundles TALA), Mermaid CLI (`mmdc`, or `npx -p @mermaid-js/mermaid-cli mmdc`), `markdownlint-cli2`, `lychee` or another link checker, `pandoc` with a PDF engine such as `typst`, `rsvg-convert`, and Graphviz `dot` if you'll need it. For anything missing, note an install command; prefer no-install runners (`npx`, `uvx`).
5. List the docs and notes in the repo root.

If you can't reach the web or a URL, say which, use the closest official source, and note what you assumed.
Don't start Phase 2 until this phase is done.

## Phase 2: Grill the user

Interview the user until you can state the project's purpose, users, scope, non-goals and the reasons behind its main design choices, and the user confirms your summary.
Ask only what the repo and the web can't tell you.
Settle the questions others depend on first, and push back on vague answers.

In the first round, also ask:

- which missing tools to install;
- what to do with each root doc or note: merge it into a chapter, move it into `docs/` unchanged, or leave it. Content that moves is not kept in two places. These always stay in the root: `README.md` (to be trimmed to a short pitch plus a link to `docs/README.md`), `LICENSE`, `CHANGELOG*` and `AGENTS.md`.

## Phase 3: Outline (checkpoint)

Propose the chapter list (file name, one-line purpose) and the diagram list (chapter, type, tool, what it shows).
Wait for the user's OK, then write `docs/README.md` with the table of contents and commit.

Start from this skeleton.
Drop what doesn't apply, split what's too big (for example, one chapter per package in a monorepo), and never pad: a small repo may need four chapters.
Name chapters `NN-kebab-name.md`, numbered in reading order.

| Chapter | Covers |
| ---- | ---- |
| Cover (`README.md`) | What this is, reading order, conventions, how to render diagrams and run checks |
| Overview | Problem, users, scope, non-goals, success criteria |
| Architecture | System context and container diagrams, components, tech stack with versions and why |
| One per major component | Responsibility, interfaces, internals, failure modes |
| Data | Data model (ER diagram), schemas, invariants, storage, migrations |
| Interfaces | Exact contracts with examples: APIs, CLI, events, file formats, external services used |
| Behavior | Key flows (sequence diagrams), state machines, algorithms in pseudocode, errors, edge cases |
| UI, if any | Screens, navigation map, layout rules |
| Configuration | Every config key and environment variable: type, default, effect |
| Build, run, deploy | Toolchain and dependency versions with their purpose, exact commands, deployment, operations |
| Quality | Testing approach, acceptance criteria taken from the tests (given / when / then), performance, security |
| Decisions | One ADR per significant decision: context, decision, alternatives, consequences |
| Rebuild guide | Ordered milestones from an empty folder, each with the chapters it needs and how to verify it |
| Glossary | Domain terms |
| Open questions | Unknowns awaiting an answer |

## Phase 4: Write

### Content

- Rebuildable: specify behavior, contracts, data shapes, configuration, versions and decisions precisely enough to reimplement. Name the source paths a section describes, for maintainers, but never rely on them.
- Prefer a diagram, then a table, then a list. Use prose only for reasons and trade-offs, at most three sentences per paragraph.
- One fact, one place: state it once and link to it everywhere else. No previews, recaps or filler. `README.md` and `AGENTS.md` link into `docs/`; they never restate it.
- Don't re-teach third-party tools; link to their official docs.
- No implementation code. Signatures, schemas and examples are fine where they are the contract; prefer neutral forms (JSON Schema, OpenAPI, SQL DDL, pseudocode).
- Each chapter: H1 title, one-line purpose, body, then previous / next links.

### Markdown

- GitHub Flavored Markdown: CommonMark plus tables, task lists, strikethrough and autolinks.
- Callouts only as GitHub alerts (`> [!NOTE]`, `TIP`, `IMPORTANT`, `WARNING`, `CAUTION`), never nested inside other blocks. GitHub, GitLab and pandoc understand them; elsewhere they degrade to plain quotes.
- No raw HTML, collapsible sections or embedded media: they break editors and print.
- Link between pages with relative paths. Keep tables to at most five columns so they fit a printed page.
- One sentence per line, for clean diffs; turn off markdownlint's line-length rule (MD013).

### Diagrams

- Draw one wherever there's structure, flow, state or relationships. At minimum: system context, architecture, data model, and each key flow.
- Prefer D2 with the TALA layout engine for software architecture diagrams (system context, containers, components, deployment). TALA draws orthogonal, whiteboard-style layouts made for architecture, unlike DAG layouts that grow in one direction. Set it inside each source with `vars: { d2-config: { layout-engine: tala } }`; if TALA isn't available, use ELK and say so.
- TALA can rearrange a whole diagram after a small edit. When a layout must stay recognizable across edits, lock key shapes with `top` and `left`.
- Mermaid for flowcharts, sequence, state, ER and class diagrams. Graphviz only for graphs a tool generates as DOT, such as dependency graphs.
- Sources live in `docs/diagrams/`, named `<chapter>-<name>.mmd`, `.d2` or `.dot`. Commit the rendered `.svg` next to each source and embed it as an image whose alt text says what it shows.
- Render on an opaque white background, so diagrams print well and stay readable in dark mode. Set Mermaid's root-level `htmlLabels: false` (the per-diagram setting is deprecated): labels inside `<foreignObject>` vanish in editors, PDF and EPUB.
- Keep each diagram to about 15 nodes; split bigger ones.

### Build script

Commit one POSIX shell script, `docs/build.sh`, pinning tool versions where the runner allows (e.g. `npx pkg@x.y.z`):

- `diagrams`: render every source in `docs/diagrams/` to SVG, with Mermaid settings in a committed `docs/diagrams/mermaid.json`;
- `check`: markdownlint, link check including anchors, and a full re-render, failing on any error;
- `export`: PDF and EPUB of the whole book into `docs/_build/` (ignored via `docs/.gitignore`); run pandoc from inside `docs/` with `--file-scope` so cross-chapter links become internal anchors.

## Phase 5: AI instructions and root cleanup

1. Create or update the root `AGENTS.md` with this section, merged with any existing content rather than duplicating it:

   ```markdown
   ## Documentation

   - Read `docs/README.md` first; `docs/` is the design source of truth.
   - If a change affects behavior, interfaces, data, configuration or dependencies, update the affected chapters and diagram sources in the same change, then run `docs/build.sh diagrams` and `docs/build.sh check`.
   - Follow the conventions in `docs/README.md`. Link to facts; never restate them.
   ```

2. Existing agent-specific files (`CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`, Cursor rules) get a pointer to `AGENTS.md`, not copied rules. In `CLAUDE.md`, that's the line `@AGENTS.md`, because Claude Code ignores `AGENTS.md` when a `CLAUDE.md` exists. Don't create agent-specific files that aren't there.

3. Apply the root-file decisions from Phase 2 and trim `README.md`.

## Phase 6: Verify (definition of done)

- [ ] `docs/build.sh diagrams` and `docs/build.sh check` pass.
- [ ] Every SVG still shows its labels when rasterized with `rsvg-convert`.
- [ ] `docs/build.sh export` produces a PDF and an EPUB you have inspected: diagrams visible, callouts and links intact.
- [ ] Build, test and run commands in the docs were executed successfully, or are marked unverified. Never run deploys.
- [ ] No fact appears twice: scan for repeated sentences, lists and tables, including in `README.md` and `AGENTS.md`.
- [ ] Every chapter is reachable from `docs/README.md`, and the previous / next links form one chain.
- [ ] The docs-only rebuild test passes.

Docs-only rebuild test: copy `docs/` alone into an empty folder and hand it to a fresh agent with no access to the repo (a sub-agent if you can restrict its access, otherwise ask the user to run it in a new session).
Ask it to:

1. write a rebuild plan detailed enough to start coding;
2. answer 10 to 15 questions you wrote from the code about defaults, edge cases, errors and data constraints.

Every guess, wrong answer or "not specified" is a gap.
Fix each one in the chapter that owns it and rerun, up to three rounds.

## Phase 7: Report

In a few lines: chapters and diagrams written, files moved or merged, check results, rebuild-test gaps left, open questions, and the branch with its commits.

## Update mode

The book exists; keep it true.
Every rule in Ground rules, Phase 4 and Phase 6 still holds, except the git branch is `docs-update`.

1. Find what changed: commits since the last commit that touched `docs/` (`git log <that commit>..HEAD`), plus uncommitted changes the user points to. With no clear baseline, compare every chapter against the code.
2. Map each change to the chapters, diagrams, ADRs and glossary entries that own it. Also check `AGENTS.md`, the root `README.md` and `docs/build.sh`.
3. Read those chapters and the code they describe. List every stale, missing or wrong fact, with its chapter and source path.
4. Ask one batch of questions, only for intent or rationale the code can't tell (a new decision needs its reason for the ADR). Unanswered ones go in Open questions.
5. Fix each fact in the one place that owns it. Add a chapter, diagram or ADR only when new structure needs one; update `docs/README.md` and the previous / next chain to match. Never restate a fact to patch a gap: link to it.
6. Remove what no longer exists. Answered open questions leave the Open questions chapter.
7. Run `docs/build.sh diagrams` and `docs/build.sh check`. Rerun the docs-only rebuild test when a contract, data shape, config key or flow changed, with questions about the changed parts.
8. Commit, never push, and report in a few lines: chapters and diagrams changed, added or removed, check results, rebuild-test gaps left, open questions, and the commits.

Nothing changed since the last docs commit and the chapters match the code: say so and stop.
