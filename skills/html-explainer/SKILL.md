---
name: html-explainer
description: Explain anything (concept, config, error, code diff, data) as a self-contained dark-mode HTML page in ~/tmp/ with a live feedback loop. Use when the user asks for an html explanation, says "explain visually", "make an html page", "I don't understand", or when the agent senses confusion and proactively offers one.
---

Explain things as self-contained dark-mode HTML pages in `~/tmp/`, iterate on feedback. The user is not a terminal-native reader; pages are the communication channel when words in chat are not landing.

## When to build

1. Explicit asks: "make an html page", "explain as html", "show me visually".
2. Proactive: when the user asks "what is X" twice, or a reply of yours visibly didn't land (they re-ask, misread, or say "I don't know what you mean"). Propose: "Want this as an html page?" then build on yes. Never silently spam files.

## Workflow

1. **Topic**: one topic per page. Split sprawling topics into multiple pages.
2. **File**: `~/tmp/explain-<topic-slug>-NN.html`, NN starting at 01. Check existing files with `ls ~/tmp/explain-*` and use the next number for that topic. Never overwrite.
3. **Template**: read `template.html` next to this SKILL.md. It contains the CSS kit, page grammar, and the feedback machinery. Copy it, replace `{{TITLE}}` and add content sections. Inline everything; no CDN, no external assets, no build step.
4. **Open**: run `open ~/tmp/explain-<topic>-NN.html` and tell the user the path.
5. **Iterate**: user replies with section numbers, pasted feedback, or a downloaded file path. If a file path is given, read it — feedback embedded via the page's save button appears as `<script type="application/json" id="feedback-data">`. Address every item, then write the next NN file (copy forward their prior answers when relevant).

## Page grammar (mandatory structure)

1. Header: title + one-line "what this page is about".
2. TL;DR box: max 3 bullets. If the reader stops here, they still get the point.
3. One primary visual: flow diagram, before/after, or annotated code — the single most clarifying picture.
4. Numbered sections (`2.1`, `2.2`…): the detail. Each starts with one bold sentence, then expands. Wrap long detail in `<details class="more">` so the page reads compact but expands on demand.
5. Glossary table for jargon, if any term might be unknown.
6. Q&A block: predefined "you might ask" questions with answers.
7. Feedback block (from template): yes/no "Did you understand?" question above the buttons, optional multi-select questions (author fills the `QUESTIONS` array - empty renders nothing; more than one choice can be picked per question, the last question always gets an exclusive `None of the above` choice and every question gets an optional note box), text areas per section + one general box, "Copy feedback" and "Save & download updated page" buttons.

## Visual kit rules

- Dark only (`#17181c` background family from template). No light mode.
- Colors: accent `#2d77e0`, success `#89d281`, warning `#febc38`, error `#ff5b5b`, muted `#8b919b`. Callouts use these.
- Diagrams: pure HTML/CSS boxes and arrows (flex + `→` glyphs or borders). SVG only when necessary. No JS chart libraries.
- Code/config blocks: `<pre><code>`, monospace, with inline `<mark>` or comment-style callouts for annotations. Before/after: two columns side by side.
- Every page must render correctly at ~800–1400px width; test mentally for narrow windows.

## Feedback protocol

- Page embeds `data-page-id="explain-<topic>-NN"`.
- The "Did you understand?" yes/no answer is included in feedback (`understood: yes|no`). If the answer is "no" with no section comments, ask which section lost them.
- MCQ answers ride along as `q <id> (<question>): <choice>` lines, with multiple choices joined by `, ` (and `answers` in the embedded JSON, where each `answer` is an array). The last question always gets an exclusive `None of the above` choice, and each question has an optional note box collected as `q <id> note: <comment>`. Questions with no answer and no note are simply omitted.
- "Copy feedback" copies a plain-text block: page id, then `understood:` line, then `q ...:` lines, then `section: comment` lines and `Q:` lines. User pastes it into chat.
- "Save & download" embeds the same data as JSON into the downloaded file. When the user later hands you such a file, parse that block first, answer each item, and produce the next NN.
- Always acknowledge feedback items explicitly ("2.2: fixed — X was wrong because…"). Never silently edit.

## Failure modes to avoid

- Wall-of-text page with no visuals — split into sections with diagrams instead.
- Overwriting a previous page — always increment NN.
- Building a page when the user just wanted a one-line chat answer — the proactive rule requires a proposal first.
- External resources (fonts, CDN JS) — page must work offline, forever.
