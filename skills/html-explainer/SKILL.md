---
name: html-explainer
description: Explain anything (concept, config, error, code diff, data) as a self-contained dark-mode HTML page in ~/tmp/. Use when the user asks for an html explanation, says "explain visually", "make an html page", "I don't understand", or when the agent senses confusion and proactively offers one.
---

Explain things as self-contained dark-mode HTML pages in `~/tmp/`. Feedback is optional and stays in chat, not in the HTML page. The user is not a terminal-native reader; pages are the communication channel when words in chat are not landing.

## When to build

1. Explicit asks: "make an html page", "explain as html", "show me visually", "explain visually with Mermaid". Build offline HTML and open Firefox; chat-only Mermaid source does not fulfill these asks.
2. Proactive: when the user asks "what is X" twice, or a reply of yours visibly didn't land (they re-ask, misread, or say "I don't know what you mean"). Propose: "Want this as an html page?" then build on yes. Never silently spam files.

## Workflow

1. **Topic**: one topic per page. Split sprawling topics into multiple pages.
2. **Diagram format**: before drawing, use `ask_user` to explicitly ask whether the user prefers direct SVG (recommended) or Mermaid (fallback). Ask even when you have a recommendation; wait for their choice before drawing. The format choice must not change the diagram type: preserve the requested flowchart, timeline, sequence, or infographic. If the user has no preference, use direct SVG. Before changing diagram type or format, explain why and ask permission.
3. **File**: `~/tmp/explain-<topic-slug>-NN.html`, NN starting at 01. Check existing files with `ls ~/tmp/explain-*` and use the next number for that topic. Never overwrite.
4. **Template**: read `template.html` next to this SKILL.md. Write a JSON object mapping its fields to locally authored HTML strings: `TITLE`, `PAGE_ID`, `TLDR`, `SECTION_TITLE`, `ONE_BOLD_SENTENCE`, `EXPLANATION`, `EXPANDED_DETAIL`, `TERM`, `MEANING`, `QUESTION`, `ANSWER`. The builder supplies `DIAGRAMS`, escapes title and page ID, and rejects missing or unresolved fields. Inline everything; no CDN or external assets.
5. **Build and open**: from this skill's directory, run `python3 scripts/build.py ~/tmp/fields.json -d ~/tmp/topic.svg -o ~/tmp/explain-topic-NN.html --no-open`. Use `.mmd` only when Mermaid is chosen; repeat `-d` for multiple or mixed diagrams. After a successful build, follow `~/repos/agent1/browser.md` to maximize the browser and open an existing Firefox tab. Never overwrite; tell the user the output path.
6. **Revise only when requested**: if the user gives feedback in chat, address it and write the next NN file. No feedback forms, buttons, or feedback JavaScript in the default page.

## Page grammar (mandatory structure)

1. Header: title + one-line "what this page is about".
2. TL;DR box: max 3 bullets. If the reader stops here, they still get the point.
3. One primary visual: flow diagram, before/after, or annotated code — the single most clarifying picture.
4. Numbered sections (`2.1`, `2.2`…): the detail. Each starts with one bold sentence, then expands. Wrap long detail in `<details class="more">` so the page reads compact but expands on demand.
5. Glossary table for jargon, if any term might be unknown.
6. Q&A block: predefined "you might ask" questions with answers.

## Visual kit rules

- Dark only (`#17181c` background family from template). No light mode.
- Colors: accent `#2d77e0`, success `#89d281`, warning `#febc38`, error `#ff5b5b`, muted `#8b919b`. Callouts use these.
- Diagrams: directly authored inline SVG by default, in the user-confirmed diagram type. Mermaid is an approved fallback when automatic layout better serves a complex graph; branches, loops, or node count alone do not force it.
- No JS chart libraries, no CDN, no external assets: the page opens offline, forever.
- Code/config blocks: `<pre><code>`, monospace, with inline `<mark>` or comment-style callouts for annotations. Before/after: two columns side by side.
- Every page must render correctly at ~800–1400px width; test mentally for narrow windows.

## Direct SVG (preferred)

Write trusted, locally authored SVG to `~/tmp/<topic>.svg` and pass it with `-d`.
The builder embeds it verbatim; SVG-only builds need no Mermaid, Node, or Chromium.

- Use an `<svg>` root, `viewBox`, readable labels, and accessible `<title>` / `<desc>`.
- Prefix IDs and CSS classes per diagram; authored SVG IDs must not repeat across diagrams.
- Keep assets inline. No scripts, event handlers, external resources, or untrusted downloaded SVG.
- Draw the confirmed flowchart, timeline, sequence diagram, or infographic; keep its arrows, ordering, and meaning explicit.

## Mermaid fallback

After the user chooses Mermaid, write `.mmd` files and pass them to `scripts/build.py`.
The builder renders and embeds SVG; the page carries pictures, not a runtime library.

1. Write the source to `~/tmp/<topic>.mmd`:

   ```
   flowchart TD
     A["Session edits markdown"] --> B{"Which mdformat?"}
     B -->|"brew: no plugin"| C["frontmatter mangled"]
     B -->|"pipx: plugin + config"| D["frontmatter intact"]
   ```

2. The builder preflights `mmdc`, resolves its installed Puppeteer dependency, and
   awaits Puppeteer's browser path. An executable `PUPPETEER_EXECUTABLE_PATH`
   overrides that path. Do not guess Chrome locations or Puppeteer internal paths.

3. It renders dark SVG on a transparent background and assigns each diagram a
   unique `--svgId`. Multiple diagrams are allowed; keep one primary visual.

4. Source is retained in `script.mermaid-source` JSON blocks. Do not put Mermaid
   arrows in HTML comments: `-->` ends the comment. The template scales SVGs.

5. Labels carry the words, arrows carry the logic. Six words per node keeps it
   legible at 800px.

Verified here: Mermaid CLI 12.0.0 with Puppeteer 25.12.0 (05 Oct 2026). For Mermaid
input, a missing renderer or Chromium stops the build; ask before installation or
download. The builder prints the replacement command. SVG-only input bypasses this
preflight. No browser launch occurs on build failure.
Run checks with `timeout 60 python3 scripts/test_build.py` from this skill directory.

## Optional revisions

- Page embeds `data-page-id="explain-<topic>-NN"` for identification.
- No feedback is required to finish an explanation. Do not add feedback UI to the page.
- If the user gives feedback in chat, acknowledge each item and create the next numbered page.
- When the user confirms they understood, delete the pages this conversation created, unless they ask to keep them. Never touch other files in `~/tmp/`.

## Failure modes to avoid

- Wall-of-text page with no visuals — split into sections with diagrams instead.
- Overwriting a previous page — always increment NN.
- Building a page when the user just wanted a one-line chat answer — the proactive rule requires a proposal first.
- External resources (fonts, CDN JS) — page must work offline, forever.
