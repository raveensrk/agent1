---
name: pi-release-upgrade
description: Check latest published Pi version against installed version, analyze intervening releases, and apply required compatibility updates to Bash aliases, scripts, functions, completions, Pi config, packages and extensions. Use when asked to check latest Pi release or upgrade readiness, update Pi setup, or run pi-release-upgrade.
---

# Pi release upgrade

## Goal

Every invocation checks the latest published stable Pi version, compares it with the installed version, and determines whether release changes require upgrading Pi or adapting this machine's Pi setup. Apply justified local compatibility fixes; report when no changes are needed. No blanket package upgrades.

## 1. Set scope

- Measure installed version using `command pi --version`; bypass shell wrappers that update before launching.
- Fetch latest stable version from official Pi release/package metadata with a bounded request. Confirm package identity from the installed installation. Use official changelogs for every intervening release, including the installed release's compatibility changes when not previously checked. If already current, still inspect relevant current-release changes against local setup.
- Latest stable is default; an explicit historical version narrows release analysis but still report installed and latest versions. If network lookup fails, say latest is unverified; do not treat installed version as latest.
- Resolve the requested release from context. "One version before" means preceding changelog entry, not guessed version arithmetic.
- Invoking this skill authorizes required non-destructive local compatibility fixes. An explanation-only or read-only request overrides that default. Ask before upgrading the Pi installation itself or installing/removing packages; show installed version, target version, reason and expected effects. A newer release alone does not prove an upgrade is required.
- Check existing Git status before edits. Preserve unrelated staged and unstaged changes.

## 2. Read release evidence

- Locate the running installation and read its changelog entries for the exact requested scope. Read matching installed docs and linked API references before implementing changes.
- For latest-version questions or missing release evidence, use official Pi sources; distinguish installed from available version. Do not silently upgrade to discover version information.
- Give a concise numbered changelog summary, separating new features, breaking changes and fixes. Cite the changelog path or official URL.

## 3. Inspect local integration

Read dotfile repository instructions before searching tool config. Follow actual startup sources and symlinks instead of assuming directory layout.

Inspect only relevant paths:

1. Bash login and interactive startup files and their sourced config; Pi aliases and functions, including wrappers that run `pi update --all`.
2. Pi launch scripts, completion source and generator. Check whether new flags already complete before regenerating anything. Never hand-edit generated completion files.
3. Pi settings, tool selection, model/provider references, MCP config and keybindings. Edit canonical stow source when live config is a symlink.
4. Configured and installed packages, disabled package extensions, custom extensions and local patches. Check release-specific APIs, provider renames and installation-layout assumptions.

Map each release item to an inspected integration point and one verdict: required change, compatible already, or not applicable. Feature availability alone is not reason to create an alias or dependency.

Keep scans bounded with `rg`; exclude sessions, caches, node_modules and generated build directories. Do not dump auth.json, API key files or whole startup files that might contain secrets: inspect credential provider key names and narrowly selected non-secret fields. Never include tokens in chat, logs or skill files. Report an incidental exposed credential without repeating it; rotation requires user involvement.

## 4. Apply required changes

- When application is authorized, add, edit or remove only integrations required by the release or explicitly requested features. No change is a valid result.
- Trace callers and startup flow before fixing shared wrappers. Preserve intentional modes such as bare Pi, which already disables extensions, and stock Pi with a separate agent directory.
- Read exact text before edits; batch disjoint edits per file. Validate JSON and shell syntax. Use existing generators for completion updates.
- Before package installation/removal, read local Pi package instructions. Ask before missing dependencies, irreversible changes, credential migration or choices with multiple valid architectures. Follow existing removal rules and show per-file plans for bulk changes.
- Do not update every package merely because Pi has a new release. Check compatibility evidence and apply only justified updates.

## 5. Verify and report

- Test changed shell integrations through their real startup/entry point. Avoid accidentally invoking auto-update wrappers during read-only probes. Separate isolated syntax/completion tests from real-entry-point verification; neither substitutes for the other.
- Test completion using the existing completion function and expected candidate; test codemode by actually calling a harmless tool from a script, not by checking a settings flag.
- New non-trivial executable logic needs one runnable regression check. Keyboard/UI claims need an observed real or synthetic event; otherwise say unverified.
- After installing/removing Pi packages, run `timeout 90 pi -p "reply with just: ok"` and inspect stderr for warnings, subject to local job-duration rules. If startup loads unrelated resources or mutates state, explain and ask before the probe.
- For changed Pi config/extensions, verify real Pi startup and diagnostics with a bounded probe; do not claim active-session activation from JSON parsing alone. Tell user to run `/reload` for discoverable config/skill changes. Installation updates may require restart.
- Re-scan repeated questions; do not reuse stale measurements.
- Finish with numbered items: release/version, changes applied with full paths, checks and observed results, compatible/not-applicable items, unresolved risks. Explicitly say when files were unchanged.

## Session-derived examples

- Pi 1.0.4 introduced tool wildcards and `--no-mcp`; existing completion already included `--no-mcp`, so no change was needed. Quote patterns such as `'mcp__radius__*'` to prevent shell expansion.
- Pi 1.0.3 renamed Azure provider `azure-openai-responses` to `azure`; migration applies only where old provider references exist. Its image persistence and terminal fixes did not require new Bash aliases.
- Codemode enablement uses `"defaultTools": ["+codemode"]`, preserving existing selection; append to an existing array instead of replacing it. `/reload` enables newly configured tools. Verify with a real harmless codemode call.

Examples are historical, not current compatibility verdicts. Re-measure each invocation.
