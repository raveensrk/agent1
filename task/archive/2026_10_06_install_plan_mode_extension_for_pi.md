---
id: "nysm9d5rwb"
title: "Install plan mode extension for pi"
state: "done"
due: ""
priority: "C"
tag: ["pi"]
repeat: ""
effort: ""
postpone: 0
created: "2026-10-06"
closed: "2026-10-10T14:30"
---

Copy/install examples/extensions/plan-mode (index.ts, utils.ts) per docs/extensions.md; toggle via /plan or Ctrl+Alt+P

## Log

- done 2026-10-10 14:30: Copied plan-mode index.ts and utils.ts to ~/dot/config/pi/extensions/plan_mode and listed it in config/pi/package.json. pi --help shows --plan. timeout 50 pi --no-session -p exited 0, stderr empty, stdout ok.
