# How rules load

A rule that a session may skip is not a rule. Two measurements shaped this
chapter. On 2026-10-03, of the six files the rules entry page named for session
start, two were never read and the git rules only when the first commit came up;
the misses matched the session's costs. On 2026-10-04 a fresh session asked its
name answered with the harness's name, because the trial rules file was only
named, not loaded. pi reads its instruction file verbatim and does not expand
`@path` imports, so a file that is only named stays optional.

So agent1 puts the rules into the prompt itself.

## At session start

When a session starts, the rules context step builds one block of text:

1. A heading saying the rules come from the entry page, then the whole entry
   page, [docs/rules/README.md](../rules/README.md).
2. A list of the topic files - git, long jobs, external systems, browser use,
   macOS, CLI apps, Markdown, pi, removal - each with one line saying when to
   read it, so skipping one is a decision, not an oversight. The nested-repo
   policy is listed only when the `~/repos` folder exists; that is a filesystem
   test, decided by code, not by the model.
3. The whole trial rules file,
   [experimental.md](../rules/experimental.md), after the entry page so the
   precedence reads in order.
4. When the voice switch is on, the telegraph voice rule.

pi runs this step as an extension in process on every request. Claude Code runs
it once per session through the SessionStart hook, which returns the block as
additional context. Both call the same code, so the text is the same.

The cost is the whole entry page on every run, about 270 lines. If a token
report ever shows that cost, trim it to the rules that actually get missed.

## Trial rules

[experimental.md](../rules/experimental.md) holds rules being tried. A rule
lands there when the user asks, or when a session proposes it and the user says
yes. Only the user moves a rule out: promoted into a topic file when it holds
up, deleted when it does not. One trial rule names the agent Optimus Prime and
asks it, at the end of each task, for one improvement to agent1, logged in
[self_improvement.md](../notes/self_improvement.md).

## The telegraph voice

The voice rule (short, telegraph-style replies) lives in its own text file next
to its switch, not in the trial rules, so turning it off never means editing a
rules file. The switch is one small state file under
`~/.local/state/agent1/`, shared by every harness. `/telegraph on`, `off` and
`status` flip or show it; pi applies it on the next request, Claude Code on the
next session.

## When the agent stops

The Stop step lints the files the session edited and hands new findings back to
the agent; it is described with the checks in
[Harness checks](04_harness_checks.md#the-trigger). Per-session state for it
(findings already reported, nudges used, the failure streak) is one JSON file
per session under `~/.local/state/agent1/sessions/`.

______________________________________________________________________

[Previous: What agent1 is](01_what_agent1_is.md) · [Next: Skills](03_skills.md)
