---
id: "pn9s54gesj"
title: "Create elimination life skill - scan computer and life for things to remove"
state: "done"
due: ""
priority: "C"
tag: ["skills", "declutter"]
repeat: ""
effort: ""
postpone: 0
created: "2026-10-06"
closed: "2026-10-08T22:52"
---

- Skill for AI agents (pi), like declutter: scans and finds what to REMOVE, not what to add.
- Two scans in one skill:
  1. Whole computer - find things to remove. declutter skill already covers unused GUI apps, brew casks and Library leftovers; decide whether to extend declutter or build a broader skill (files, caches, duplicates, downloads, disk hogs).
  2. Life - find things to remove: commitments, habits, subscriptions, recurring tasks, projects that stopped earning their keep.
- Candidate names: eliminate, elimination-audit. Agent Skills format: kebab-case dir, name+description frontmatter (harness checks enforce both).
- Skill lives in ~/.agents/skills (where declutter and find-skills live).
- Design question to settle at build time: one skill with two modes, or skill + a life-audit companion? Ask Raveen.
Implemented as project skill ~/repos/notes/.agents/skills/elimination-life/ (SKILL.md, state.yaml, session-log.md; Dr Sean Maguire persona at ~/repos/agent1/personas/sean_maguire.md), built 2026-10-08
