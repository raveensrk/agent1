---
name: ask-simple
metadata:
  scope: global
description: Ask the user clear questions in simple language, as if they are new to the topic, so each one is easy to answer. Use when the user says ask simple questions, assume I am a newbie, keep it simple, explain like I am new, I do not understand your question, or runs /ask-simple. Also use whenever a task needs the user's decision and they have asked for plain words.
argument-hint: "[topic to ask about]"
---

# Ask simple questions

The user is new to the topic.
Every question must be easy to read and easy to answer.

## 1. Look first

Find what you can on your own before you ask: read the files, the docs and
the conversation. Never ask what you can look up, or what the user already
said.

## 2. Write each question

- One question asks one thing. Never two in one.
- One short sentence. Aim for 15 words or fewer.
- Everyday words. No jargon, no acronyms, no tool names the user did not use
  first. If a technical word cannot be avoided, explain it in a few plain
  words right after it.
- It stands alone: it names the thing it asks about.
- Say why it matters in one plain line, when that helps the user choose.
- Give two to four answers. Each is a few words, plus one line on what it
  means for the user.
- Put your recommended answer first and mark it `(Recommended)`.
- Use yes or no when that is enough.
- Add "Not sure - you pick" when a newbie may not know.
  Then pick the recommended answer and say so.

Bad: "Should the CLI use argparse subcommands or a click group with lazy
loading?"

Good: "How should people start the tool?"

- Type one command, like `tool add` (Recommended) - easiest to learn.
- Pick from a menu - no commands to remember.
- Not sure - you pick.

## 3. Ask

- Use the harness's question tool when it has one (Claude Code:
  `AskUserQuestion`).
- Otherwise print numbered questions with lettered answers, so the reply can
  be `1a 2b`.
- Ask at most four at once. Ask the next round once those are answered.
- Ask the most important question first.

## 4. After the answers

- Repeat the answers back, one plain line each.
- If an answer is unclear, ask again in simpler words. Do not guess.
- Then do the work.

## Rules

- Never make the user feel slow. No "as you know", no "obviously".
- Never ask what the code, the docs or an earlier answer already settled.
- Short beats complete. Leave out detail the user does not need to choose.
