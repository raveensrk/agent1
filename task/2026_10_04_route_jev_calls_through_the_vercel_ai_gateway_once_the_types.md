---
id: "xxjywte2sk"
title: "Route Jev calls through the Vercel AI Gateway once the TypeSafe prepaid credit runs out"
state: "todo"
due: ""
priority: "C"
tag: []
repeat: ""
effort: ""
postpone: 0
created: "2026-10-04"
closed: ""
---

Trigger: the TypeSafe prepaid balance on https://console.typesafe.ai/usage reaches zero. Check that page by hand; TypeSafe publishes no balance API.
Route: point every Jev caller at https://ai-gateway.vercel.sh/typesafe/v1/systemone with a Vercel AI Gateway key and model id typesafe-ai/jev.
Callers to change: /Users/raveen_kumar_personal/dot/script/bookmark, /Users/raveen_kumar_personal/.pi/agent/extensions/voice_score.ts, /Users/raveen_kumar_personal/.pi/agent/extensions/call_score.ts, and pi's typesafe-ai skill.
Balance then comes from GET https://ai-gateway.vercel.sh/v1/credits (balance, totalUsed). Do not add a TypeSafe key under BYOK - that makes the gateway balance stop tracking Jev.
