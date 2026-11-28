# Remove agent1

```bash
~/repos/agent1/uninstall.py           # dry run: show the plan
~/repos/agent1/uninstall.py --apply   # unregister
```

This drops the clone from pi's packages and uninstalls the Claude Code plugin and
its marketplace. Then, by hand:

- Remove the rules line from your `CLAUDE.md` and `AGENTS.md` files.
- Unset the git hooks: `git config --global --unset core.hooksPath`.
- Restart pi and Claude Code.
- Move the clone to the Trash if you no longer want it.

______________________________________________________________________

[Previous: Publish the books](06_publish_books.md) · [Back to contents](README.md)
