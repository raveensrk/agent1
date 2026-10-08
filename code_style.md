# Code Style

How to write code. Loaded from [common.md](common.md) at session start.

## Naming Enforcement

- Use single word names by default for new locals, params, and helper functions.
- Multi-word names are allowed only when a single word would be unclear or ambiguous.
- Do not introduce new camelCase compounds when a short single-word alternative is clear.
- Before finishing edits, review touched lines and shorten newly introduced identifiers where possible.
- Good short names to prefer: pid, cfg, err, opts, dir, root, child, state, timeout.
- Examples to avoid unless truly required: inputPID, existingClient, connectTimeout, workerPath.

## Avoid else statements

Prefer early returns over else. After an `if` that returns/throws, the else is redundant.

## GUI Apps

- GUI apps you implement must be easily debuggable and navigable from the agent
- Never measure anything off-screen. Render the content correctly, bring it to foreground and measure it.

## CLI and GUI Apps

- Use structured logs. Never log secrets.

## Structure

- Keep things in one function unless composable or reusable

## Code habits

From <https://fabiensanglard.net/agent.md/index.html>.

- Avoid magic numbers and strings by extracting recurring or meaningful values into descriptive constants (const) or enums. Keep self-explanatory, one-off values inline to avoid clutter. If a value comes from a spec (e.g. HTTP 200 OK), use a constant regardless.

- Let the reader of the code breathe. Add empty lines between logical blocks of code.

- Add a small, to the point, comment to explain *what* the block does and *why*. Use examples when possible. Propose ASCII drawings to explain complete systems.

- Don't touch blocks of code unrelated to the feature you implement. e.g. Don't add comments to a block of code if you did not create it or modify it. As much as possible try to minimize the number of changed lines when implementing a feature.

- If the prompt is a high-impact or regression-prone bugfix, write a failing test first, then the fix, then confirm the test passes. Skip this for tiny obvious fixes.
