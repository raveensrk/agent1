---
last_reviewed: 2026-11-02
---

# Scripts

Scripts meant to be run are executable: a line-1 shebang naming an installed
interpreter (`python3` is 3.14; `python3.12` and `python3.14` are installed
too), then `chmod +x`. Library files meant to be imported or sourced are exempt.
[interpreter_resolves.py](../harness/checks/interpreter_resolves.py) and
[script_exec_bit.py](../harness/checks/script_exec_bit.py) decide the hard half.
