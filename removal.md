# Removal and uninstall

Split from [common.md](common.md); routed by [rules_context.ts](harness/extensions/rules_context.ts).

- Check `~/dot/script` for an existing tool before writing a scanner. The AI data scrub prompt in [prompts.md](prompts.md) lists each AI harness's folders, what to keep, and the uninstall tiers.
- Print the numbered per-file plan first, then apply. Removals are destructive.
- Removals go to Trash by default. The plan names anything that deletes permanently (`brew uninstall`, `npm uninstall -g`, keychain deletes, TCC paths that need `sudo rm`) and gets explicit confirmation for it. Empty the Trash only on explicit request; report what it holds and print the one-line purge command.
- Verify a removal by re-running the same scan that found the items and diffing the result. If the scan was ad hoc, save it before removing anything.
- Remove browser extensions through the browser UI (`chrome://extensions`), not by deleting profile directories; a direct delete is not recorded in sync and the extension can return at the next sign-in. Verify again after signing in.
- After removing a harness, grep update, install and doctor scripts for its commands and drop the dead entries.
- Uninstall casks one at a time: a multi-cask `brew uninstall --cask` stops at the first failure. Use `--force` per cask, then check `brew list --cask`.
- `--zap` removes a directory only when it is empty. Re-list each top-level harness directory after the cask uninstall.
- Expect TCC-protected leftovers (Containers, sharedfilelist, root-owned symlinks). Collect them into one sudo list and hand it to the user at the end.
