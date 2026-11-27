# Standard layouts

Where each kind of file usually lives. [relayout](../SKILL.md) compares a repo
with this file. A repo's own Layout section in its `AGENTS.md` wins over it.

## Every repo

1. The root holds `README.md`, `AGENTS.md`, a license, the build files and
   config dotfiles. Any other loose file needs a reason, like being the one
   entry point.
2. Helper scripts live in one folder, `script/` or `scripts/`; the repo's own
   choice wins. Two folders doing that one job is a finding.
3. Docs beyond the README live in `docs/`, as
   [rules/docs.md](../../../rules/docs.md) names it.
4. Generated output (`target/`, `dist/`, `build/`, `.build/`) is gitignored,
   never tracked.
5. Real user data stays out of the code repo, in a sibling data repo like
   `<app>-data`. Test data is invented and lives with the tests.
6. Core and UI stay apart
   ([agent1.org](../../../rules/agent1.org) section Architecture): `core/` for
   the core, then one folder per UI, like `cli/` and `app/`.

## Clojure (`deps.edn`)

1. Code in `src/`, tests in `test/`, classpath files in `resources/`, REPL
   helpers in `dev/`.
2. A namespace matches its path, dashes as underscores: `my-app.core` lives
   in `src/my_app/core.clj`.
3. A move renames the `ns` form and every `:require` of it.
4. Tests mirror `src/`: `test/my_app/core_test.clj` holds `my-app.core-test`.

## Rust (Cargo)

1. The binary in `src/main.rs`, the library in `src/lib.rs`, more binaries in
   `src/bin/`.
2. Integration tests in `tests/`, benchmarks in `benches/`, examples in
   `examples/`. Unit tests sit in the file they test, in a
   `#[cfg(test)] mod tests` block.
3. A module follows its file: `mod foo;` loads `src/foo.rs` or
   `src/foo/mod.rs`. A move updates `mod` lines and `use` paths.
4. A workspace lists its members in the root `Cargo.toml`. A renamed member
   folder is renamed there too.

## Swift (SwiftPM)

1. `Package.swift` at the root, code in `Sources/<Target>/`, tests in
   `Tests/<Target>Tests/`.
2. A target's folder name is its name in `Package.swift`. A rename edits
   both.
3. Files move freely inside one target. A move to another target changes the
   module, so imports change.
4. An `.xcodeproj` lists every file by path in `project.pbxproj`. Move those
   files only with that file updated, or leave them.

## Go

1. `go.mod` at the root, and one `cmd/<app>/main.go` per binary.
2. `internal/` holds packages only this module may import. A move in or out
   of `internal/` changes who may import the package.
3. A package's folder is its import path. A move rewrites the imports.
4. Tests sit beside the code: `foo_test.go` next to `foo.go`.

## Python

1. `pyproject.toml` at the root, the package in `src/<pkg>/` or `<pkg>/`.
2. Tests in `tests/`, named `test_*.py`.
3. A module's path is its file path. A move rewrites the imports.
4. A script meant to be run has a shebang and the exec bit
   ([rules/scripts.md](../../../rules/scripts.md)).

## TypeScript and JavaScript

1. `package.json` at the root, code in `src/`.
2. Tests in `test/`, or beside the code as `*.test.ts`.
3. A move breaks relative imports, and paths in `package.json` and
   `tsconfig.json`. Update all of them.

## Docs and notes

1. One folder per topic. A folder with many files gets an index file, like
   `index.md`.
2. Images sit next to the doc that shows them, or in `assets/`.
3. A move breaks relative links. Fix them
   ([rules/markdown.md](../../../rules/markdown.md)).

## Agent skills

1. `skills/<name>/SKILL.md`, where the folder name is the skill's `name`
   ([skill_frontmatter.py](../../../harness/checks/skill_frontmatter.py)
   checks it).
2. Helper scripts in `scripts/`, long docs in `references/`, tests in
   `tests/`.

## The Layout section

relayout records the result in the repo's `AGENTS.md`: one line per top
folder, a link, then what it holds.

```markdown
## Layout

- [`src/`](src/) - the core: parsing and storage, no UI.
- [`script/`](script/) - `install` and `build_app`.
- [`test/`](test/) - tests, mirroring `src/`.
```
