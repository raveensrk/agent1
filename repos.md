# Repos

Split from [common.md](common.md); routed by [rules_context.ts](harness/extensions/rules_context.ts).

Loaded only when `~/repos` exists - the condition is a filesystem test decided in [rules_context.ts](harness/extensions/rules_context.ts).

Never use a nested git repo for my projects, and never a symlink to one. A clone from the internet is the
exception: it goes in the allowlist that [nested_git_repo](~/repos/agent1/harness/checks/nested_git_repo.py)
reads, and the check decides the rule. The check is public; the allowlist is private, at
`~/repos/agent2/harness/data/nested_repo_allow.txt`. The walker lints nested repos and prints their findings as warnings,
never as findings, and never changes the exit code - it does nothing to a repo that is not mine. A symlink
to a repo is a finding either way: the check reports one inside a repo, the walker reports one in a folder
that no repo owns.
