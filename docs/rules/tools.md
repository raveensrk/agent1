---
last_reviewed: 2026-11-02
---

# Tools

- Repo layout (`docs/`, `scripts/`, `inbox.md`, …) lives in that repo's
  `AGENTS.md`.
- Tool configs live in `~/dot/config`, installed by `~/dot/install.sh`
  (no symlinks). Read `~/dot/AGENTS.md` before searching for a tool's config.
- Tool list: read [Dev Tools](../notes/dev_tools.md) before choosing a tool and
  prefer a tool listed there over an unlisted one.
- Shared Rust code goes in `~/repos/lib`, as a crate in its Cargo
  workspace, and apps fetch it by git tag. Never copy shared code from one
  app into another: move it into a lib crate, tag a release, and point every
  app at the tag.
- The user also works with org-mode text sometimes.
