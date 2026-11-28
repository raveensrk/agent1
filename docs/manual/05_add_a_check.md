# Add a check

First find the mistake by hand: a rule that says it, and a real violation today.
Then drop an executable file in `harness/checks/` with the header:

```python
#!/usr/bin/env python3
# harness-check: {"id": "my_check", "applies": ["*.py", "!**/vendor/**"],
#                 "quadrant": "feedback/computational"}
```

It reads file paths on stdin, prints `path:line: message` per finding (end the
message with the fix) and exits 0. The full contract is in
[Harness checks](../design/04_harness_checks.md#the-lint-command). Nothing else
needs to change: the lint finds it. A check for this machine only goes in
`~/repos/agent2/harness/checks/` instead.

Add a test for it in `harness/tests/test_lint.py`.

## Commands

```
python3 harness/lint.py                 # this repo: tracked + untracked files
python3 harness/lint.py --changed       # only changes against HEAD, plus untracked
python3 harness/lint.py FILE...         # only those files
python3 harness/lint.py --repos         # every git repo under ~/repos
python3 harness/lint.py --list          # the checks, their quadrant and scope
python3 harness/lint.py --check ID      # one check only
python3 harness/lint.py --json          # for scripts and the trigger
python3 harness/tests/test_lint.py      # the checks' own tests
node --experimental-strip-types harness/tests/test_command_guard.ts
bash harness/self_check                 # every suite, then the full lint
```

Exit 0 clean, 1 findings, 2 a check failed to run. `lint.py help` has the rest.

______________________________________________________________________

[Previous: Add a skill](04_add_a_skill.md) · [Next: Publish the books](06_publish_books.md)
