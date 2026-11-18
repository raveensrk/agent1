---
name: tutor
description: Teach the user any topic chapter by chapter in the Tutor web app - animated SVG lessons, a quiz per chapter, and FSRS spaced-repetition flashcards saved to their repo as markdown + SVG, or a fast mode with lessons only. Use when the user says teach me, I want to learn, make a course on, next chapter, quiz me, flashcards for, or runs /tutor.
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
 :chapters [{:slug "01_halving" :title "Halving the search space" :summary "Why O(log n)"}]}
```

Per chapter, `<slug>/`:

- `lesson.md` - short sections, one concept each, sized to minutes-per-day.
  Embed figures as `![caption](name.svg)` (relative paths).
- `*.svg` - animated figures (rules below).
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

## 3. Animated SVG rules

- Self-contained: inline `<style>`, no scripts, no external fonts or images.
  Animate with CSS `@keyframes` or SMIL `<animate>`; loop with `repeatCount="indefinite"`.
- Set `viewBox`, width <= 720. Text >= 12px. Must be valid XML (escape `<`, `&`).
- Show the mechanism step by step (a state changing over time), with a caption
  line per step. Add `@media (prefers-color-scheme: dark)` colors.
- One idea per figure. Example: `~/repos/tutor/example/binary_search/01_halving/halving.svg`.

## 4. Launch

Run `tutor check <topic>`, then `tutor start`, then give the user the link
`<url>/#/c/<topic>/<slug>`. Lesson -> quiz -> cards happens in the page; the
user clicks Save card, and the app writes `cards/<id>.md` + `cards/<id>.svg`.
Reviews are at `<url>/#/review`.

## 5. Next chapter

When asked, read `course.edn`, `progress.edn` and the previous chapter's files
so the new lesson builds on them, write the next unwritten chapter, check, and
send the link. To switch a course's default, set `:mode` in `course.edn`;
switching a fast course to normal means writing the missing `quiz.edn` and
`cards.edn` for its chapters (ask first). If the user wants to change the outline, edit `course.edn`; keep
slugs of written chapters stable.
