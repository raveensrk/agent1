# Skills

Agent skills in the [Agent Skills](https://agentskills.io) format. Install them
by registering this repo with [install.py](../install.py).

- [add-requirement](./add-requirement/SKILL.md) - Adds a requirement only after proving it can be built and tested, offering alternatives when it cannot.
- [ask-simple](./ask-simple/SKILL.md) - Asks the user clear questions in simple language, as if they are new to the topic.
- [determinize](./determinize/SKILL.md) - Turns a directory's agent rules into checks, guards and git hooks, then thins the instructions to decisions and routing.
- [detective-ant](./detective-ant/SKILL.md) - Checks a change against its task, issue or plan and finds real bugs, each with a cause and fix plan: by hand, or as Ishikari's detective ants.
- [docs](./docs/SKILL.md) - Creates or updates `docs/`, run by hand after a task: a book-style design doc complete enough to rebuild the repo from.
- [investigator-ant](./investigator-ant/SKILL.md) - Investigates a task, proves it can be built, then plans it: in the session by hand, or as specs and plans for Ishikari.
- [ishikari](./ishikari/SKILL.md) - Runs the Ishikari ant workflow on a task: review, plan, parallel build, check, fix, test together and merge, stopping only to ask.
- [janitor-ant](./janitor-ant/SKILL.md) - Cleans only the code a change added or touched, with no change in behaviour: by hand after a yes, or as Ishikari's janitor ant.
- [judge-ant](./judge-ant/SKILL.md) - Scores code 0-10 against a spec's behaviours and invariants, id by id, with gaps and bugs: by hand, or as Ishikari's judge and juror ants.
- [maintain](./maintain/SKILL.md) - Maintains a project: dead code, bloat, redundancy, large blocks and helper scripts, planned first, applied one verified step at a time.
- [next](./next/SKILL.md) - Asks "What next?" after a task, lists up to 5 next steps best first, and does the one the user picks.
- [port-app](./port-app/SKILL.md) - Plans a port of an app to a new language or toolkit by asking very simple questions, then writing the plan.
- [redesign-gui](./redesign-gui/SKILL.md) - Redesigns a desktop app's GUI in four gated phases: brief, SVG mockups, contract, then build and verify.
- [relayout](./relayout/SKILL.md) - Checks a repo's layout and keeps a good
  one; otherwise plans moves and renames, applied on a branch after a yes.
- [shop](./shop/SKILL.md) - Finds a product across Indian stores and lists the top 5 (more on request) by review-weighted rating, with pictures, prices and links.
- [test-cua-driver-with-freeform](./test-cua-driver-with-freeform/SKILL.md) - Smoke-tests cua-driver by drawing a house on a new Freeform board and reports each capability as pass or fail.
- [trim](./trim/SKILL.md) - Finds features too complex for the project's goal and reports each with its lines of code and a simpler way.
- [ux](./ux/SKILL.md) - Plans a GUI, CLI or TUI as a UX brief, or reviews one from code and reports ranked findings, citing Laws of UX and clig.dev.
- [task-router-2](~/repos/task-router-2/resources/skills/task-router-2/SKILL.md) - Tasks as one Markdown file each, written by the `task-router-2` CLI. Lives in the task-router-2 repo; `task-router-2 skill install` installs it.
- [tutor](~/repos/tutor/resources/skills/tutor/SKILL.md) - Teaches any topic in the Tutor web app: diagram-led 16:9 slides with judged animated SVGs, quizzes and FSRS flashcards. Lives in the tutor repo; `tutor skill install` installs it.
