# Pi packages

Split from [common.md](common.md); routed by [rules_context.ts](harness/extensions/rules_context.ts).

- Manual npm commands in `~/.pi/agent/npm` need `--legacy-peer-deps`; without it npm fails with ERESOLVE. Pi's own package manager passes the same flag.
- `pi uninstall npm:<pkg>` only removes sources listed in `settings.json`. For installed-but-not-enabled packages, `npm uninstall --legacy-peer-deps <pkg>` in `~/.pi/agent/npm`; a reconcile (`pi install`, `pi uninstall`, `pi update --extensions`) also prunes them, and `pi list` shows what is configured.
- A `node_modules` entry absent from `settings.json` is not dead: an enabled package may depend on it. Check `grep -rl "<pkg>" node_modules/*/package.json` and `package-lock.json` before calling it an orphan.
- Any `pi install` or `pi uninstall` reconciles the npm dir to `settings.json` and can silently prune other installed packages. Snapshot `~/.pi/agent/npm/package.json` first and expect collateral removals.
- The host-dependency warning (host-provided packages in `dependencies`) fires only for enabled extensions. Before acting, scan every installed package that declares `pi.extensions` for host-provided deps in `dependencies`.
- Host-provided packages (`@earendil-works/pi-ai`, `pi-agent-core`, `pi-coding-agent`, `pi-tui`, `typebox`) belong in `peerDependencies` with a `"*"` range, never in `dependencies`.
