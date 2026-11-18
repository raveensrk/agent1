---
name: tutor
description: Teach the user any topic chapter by chapter in the Tutor web app - diagram-led slides whose animated SVGs are drawn by an artist agent, animated by an animator agent and scored by a judge agent, a quiz per chapter, and FSRS spaced-repetition flashcards saved to their repo as markdown + SVG, or a fast mode with lessons only. Use when the user says teach me, I want to learn, make a course on, next chapter, quiz me, flashcards for, or runs /tutor.
---

# Tutor

You write the course files. The app at `~/repos/tutor` serves them, runs quizzes,
saves flashcards and schedules reviews. The app never calls an LLM.

Commands (`~/repos/tutor/bin/tutor`):

- `tutor root` - print the course root (config `~/.config/tutor/config.edn`,
  key `:root`, default `~/learn`; env `TUTOR_ROOT` overrides).
- `tutor check TOPIC` - validate files you wrote. Run after every write. Fix
  every problem it prints.
- `tutor start` - start server in background if not running; prints the URL.
- `tutor stop` - stop it.
- `tutor render FILE.svg OUTDIR [--frames N]` - PNG frames of a figure (light
  frames across the animation, plus one dark frame) for the judge.

## 1. New course: interview first

Ask, in one round: current level, goal (what they want to be able to do),
minutes per day, any preferred examples or language, and mode:

- **normal** - lesson, quiz, flashcards; chapters unlock as quizzes pass.
- **fast** - lessons and SVGs only; no quiz, no cards; every chapter open.

If the request already says fast (e.g. "fast mode", "just the lessons",
"skim"), use fast without asking. Then propose an outline of
5-12 chapters, each one sentence. Write nothing until the user approves it.

Topic folder name: lowercase snake_case, e.g. `tcp_congestion`.

## 2. Files (under `$(tutor root)/<topic>/`)

`course.edn`:

```clojure
{:title "Binary search" :level "beginner" :goal "Write a bug-free binary search"
 :minutes-per-day 15
 :mode :normal            ; or :fast
 :diagram-led true        ; default for new courses: 60-word slides, judged figures
 :chapters [{:slug "01_halving" :title "Halving the search space" :summary "Why O(log n)"}]}
```

Per chapter, `<slug>/`:

- `lesson.md` - a deck of **slides** for a 16:9 computer screen; the page
  never scrolls. Each `##` section is one slide (or separate slides with a
  line containing only `---`, which then wins over `##`). A slide under
  40 words joins the next one. **Show, do not tell**:
  - every concept slide has one figure (right) and at most 60 words (left):
    a heading, 2-4 short bullets or sentences, no paragraphs
  - text-only slides only for code (at most 14 lines)
  - one figure per slide; split rather than cram
  Embed figures as `![caption](name.svg)` (relative paths). `tutor check`
  prints `warn` lines for slides over these limits: fix them.
- `*.svg` - figures made by the diagram pipeline (section 3).
- `judge.edn` - the judge's final scores, one entry per figure:
  `[{:fig "x.svg" :readability 4 :understanding 5 :rounds 2 :animated true :notes "..."}]`.
  Required when the course is `:diagram-led`; `tutor check` fails on a score below 4.
- `quiz.edn` - 2-4 questions that test understanding, not recall of wording:
  `[{:q "..." :choices ["a" "b" "c"] :answer 1 :why "..."}]` (`:answer` is a 0-based index).
- `cards.edn` - 3-8 candidate flashcards, one atomic fact each:
  `[{:id "bs-halving" :front "..." :back "..." :svg "halving.svg"}]`. `:id` is
  unique across the topic, lowercase `a-z0-9-_`. `:svg` optional.

In **fast** mode write only `lesson.md` and the SVGs; skip `quiz.edn` and
`cards.edn`. Lessons may run a bit denser, since no quiz reinforces them.

Never write `progress.edn` or anything in `cards/` - the app owns them.
In normal mode chapters unlock in order once the previous quiz passes.
The page also has a per-course "Fast mode" switch, so the user can read a
normal course without quizzes; it does not change the files.

Write only the next one chapter at a time, unless the user asks for more.

## 3. Diagram pipeline: artist, animator, judge

You are the **teacher**: you write slide text, quiz and cards, and for each
concept slide a figure brief (the one idea, what to show). Each figure then
goes through three roles, defined in this skill's `agents/` folder:

1. **Artist** ([agents/artist.md](agents/artist.md)) draws a static SVG.
2. **Animator** ([agents/animator.md](agents/animator.md)) animates it only if
   the idea changes over time; otherwise leaves it static.
3. Render: `tutor render <fig>.svg <tmpdir>/<fig>`.
4. **Judge** ([agents/judge.md](agents/judge.md)) looks at the frames, the
   slide text and the chapter goal, and scores readability and understanding
   1-5. Pass is 4+ on both.
5. Below pass: send the judge's notes to the artist (layout, labels) and/or
   animator (steps, timing); render and judge again. Max 3 rounds; keep the
   best-scoring version. Record the final scores in `judge.edn`.

Running the roles:

- **Harness with subagents** (Claude Code Agent tool or workflows, Codex
  subagents, pi tasks): spawn each role as its own agent with the role file as
  its instructions plus only the inputs that file lists. The judge gets the
  frames, slide text and goal only: never the artist's reply or earlier scores.
  Figures are independent: run them in parallel.
- **No subagents**: play each role yourself in turn, reading its role file
  first. Judge last and only from the rendered frames, as if you had not drawn
  it; be strict.
- **No browser for `tutor render`**: the judge reads the SVG source instead;
  say so to the user and mark `:notes "judged from source"`.

SVG basics for every role: self-contained, inline `<style>`, no scripts or
external assets, valid XML, landscape viewBox width <= 720, dark-mode colors.
Example: `~/repos/tutor/example/binary_search/01_halving/halving.svg`.

## 4. Launch

Run `tutor check <topic>` (no errors, no `warn` lines, judge scores 4+), then `tutor start`, then give the user the link
`<url>/#/c/<topic>/<slug>`. A chapter plays as one slide sequence on a
16:9 stage (arrow keys or Prev/Next): lesson slides, then one quiz question
per slide, then one flashcard per slide; the
user clicks Save card, and the app writes `cards/<id>.md` + `cards/<id>.svg`.
Reviews are at `<url>/#/review`.

## 5. Next chapter

When asked, read `course.edn`, `progress.edn` and the previous chapter's files
so the new lesson builds on them, write the next unwritten chapter, check, and
send the link. To switch a course's default, set `:mode` in `course.edn`;
switching a fast course to normal means writing the missing `quiz.edn` and
`cards.edn` for its chapters (ask first). If the user wants to change the outline, edit `course.edn`; keep
slugs of written chapters stable.
