---
description: Estimate tokens and USD to complete a task with the active model
argument-hint: "[task]"
---

Estimate the additional tokens and USD to complete ${@:-the most recent unfinished task discussed before this command}. Do not perform the task.

Identify the active provider, model, and thinking level. Check pricing from the actual billing provider, including cache rates and context-size tiers. Ground the estimate in bounded, read-only inspection and recent session usage; never invent a missing rate.

Give a range and midpoint for generated output tokens (including reasoning), total billed tokens across calls (including cached input), and additional USD. State the likely number of model calls, measured basis, largest uncertainty, and pricing source URL. Do not double-count reasoning or confuse already-spent cost with the estimate. For a subscription, distinguish marginal spend from API-equivalent cost.

If no task is identifiable, ask which task to estimate.
