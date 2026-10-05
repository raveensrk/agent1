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
2. **Diagram format**: if the requested page needs a diagram, use `ask_user` to explicitly ask whether the user prefers direct SVG (recommended) or Mermaid (fallback). Ask even when you have a recommendation; wait for their choice before drawing. The format choice must not change the diagram type: preserve the requested flowchart, timeline, sequence, or infographic. If the user has no preference, use direct SVG. Before changing diagram type or format, explain why and ask permission. Skip this step for Q&A-only forms or other pages with no diagram.
3. **File**: `~/tmp/explain-<topic-slug>-NN.html`, NN starting at 01. Check existing files with `ls ~/tmp/explain-*` and use the next number for that topic. Never overwrite.
4. **Content passes**: draft the explanation first. Then independently draft useful, likely reader follow-up Q&A; do not merely turn each detail heading into a question or repeat the body. Include only questions that add value, with clear standalone answers. Keep Q&A on the same page.
5. **Template**: read `template.html` next to this SKILL.md. Write a JSON object mapping its fields to locally authored HTML strings: `TITLE`, `PAGE_ID`, `TLDR`, `SECTION_TITLE`, `ONE_BOLD_SENTENCE`, `EXPLANATION`, `EXPANDED_DETAIL`, `TERM`, `MEANING`, `QA_ITEMS`. Put one or more numbered question-and-answer blocks in `QA_ITEMS`. The builder supplies `DIAGRAMS`, escapes title and page ID, and rejects missing or unresolved fields. Inline everything; no CDN or external assets.
6. **Interactive Q&A**: if readers should answer questions, use separate `template-qa.html`, not the default explainer template. Fill its `TITLE`, `PAGE_ID`, `INTRO`, and `QUESTIONS` fields. Group each question with `<fieldset class="question">` and `<legend>`, and use stable `name` values. Put normal text/radio/checkbox answers in `.answer-options`. For a text answer, include a checked `data-text-mode` radio choice with value `custom` (“Write my answer”) and a textarea; choosing an alternative disables and clears that textarea, while choosing the custom radio re-enables it. After a visible separator, every question gets one `.answer-alternatives` radio group. Give all four radios the same question-specific `name` and values `all-of-the-above`, `none-of-the-above`, `i-dont-know`, `you-decide`. The template makes alternatives mutually exclusive with each other and normal answers. Yes/No questions use Yes/No as normal radio options, plus the same alternative group. The page has no server or JSON download: readers can copy all question-and-answer pairs as plain text.
7. **Build and open**: standard page: `python3 scripts/build.py ~/tmp/fields.json -d ~/tmp/topic.svg -o ~/tmp/explain-topic-NN.html --no-open`. Interactive Q&A page: `python3 scripts/build.py ~/tmp/fields.json --template template-qa.html -o ~/tmp/explain-topic-NN.html --no-open` (no `-d`). Use `.mmd` only when Mermaid is chosen; repeat `-d` for multiple or mixed diagrams. After a successful build, follow `~/repos/agent1/browser.md` to maximize the browser and open an existing Firefox tab. Never overwrite; tell the user the output path.
8. **Revise only when requested**: if the user gives feedback in chat, address it and write the next NN file. No feedback forms, buttons, or feedback JavaScript in the default page.

## Default explainer page grammar (mandatory structure)

This structure applies to standard explanation pages. Interactive Q&A-only forms use `template-qa.html` and consist of a title, introduction, and answerable questions; they do not need the explainer diagram or detail sections.

1. Header: title + one-line "what this page is about".
2. TL;DR box: max 3 bullets. If the reader stops here, they still get the point.
3. One primary visual: flow diagram, before/after, or annotated code — the single most clarifying picture.
4. Numbered sections (`2.1`, `2.2`…): the detail. Each starts with one bold sentence, then expands. Wrap long detail in `<details class="more">` so the page reads compact but expands on demand.
5. Glossary table for jargon, if any term might be unknown.
6. Q&A block: independently drafted, useful likely follow-up questions with standalone answers; include on same page.

## Visual kit rules

- Dark only (`#17181c` background family from template). No light mode.
- Colors: accent `#2d77e0`, success `#89d281`, warning `#febc38`, error `#ff5b5b`, muted `#8b919b`. Callouts use these.
- Diagrams: directly authored inline SVG by default, in the user-confirmed diagram type. Mermaid is an approved fallback when automatic layout better serves a complex graph; branches, loops, or node count alone do not force it.
- No JS chart libraries, no CDN, no external assets: the page opens offline, forever.
- Code/config blocks: `<pre><code>`, monospace, with inline `<mark>` or comment-style callouts for annotations. Before/after: two columns side by side.
- Every page must render correctly at ~800–1400px width; test mentally for narrow windows.

## Maintained maps

- `architecture.svg` shows how the standard and interactive templates flow through `scripts/build.py` to HTML.
- `workflow.svg` shows when/how the skill builds, opens, revises, and cleans up pages.

Update both in the same change whenever workflow, templates, CLI/build validation, diagram rendering, output behavior, or interactive Q&A behavior changes. `scripts/test_build.py` checks both maps remain valid and cover the current routes.

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
