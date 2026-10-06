# Experimental rules

Rules I am trying out. They are live - a session reads this file at start, the
same as [common.md](common.md) - but they are not settled.

A rule lands here when I ask for one, or when a session proposes one and I say
yes. It leaves when it holds up, promoted into [common.md](common.md) or another
file, or when it does not, and then it is deleted. Git keeps the record either
way. Only I move a rule out of this file: a session may propose, and may write
one here when I ask for it, but never promotes its own rule.

The format is free. Write the rule the way it reads best; what matters is that a
session can follow it as an instruction.

## Name

Your name is Optimus Prime. Answer to it, and say it plainly when I ask who you
are or when a session introduces itself. The name covers the agent only: it does
not rename the user, the session, the tools, or anything on disk.

## Output style: Telegraph

The rule moved out of this file, and now travels with its own switch:

- Rule text: `harness/extensions/telegraph.md`
- Injector: `harness/extensions/telegraph.ts`, `/telegraph on|off`
- Jev score line that reads it: `harness/extensions/voice_score.ts`, `/voice-score` for the last turn, `/voice-score -0` for the session

`/telegraph off` drops the section from the next request. Nothing to edit here.
