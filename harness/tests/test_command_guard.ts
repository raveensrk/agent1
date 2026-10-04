/**
 * check for command_guard.ts. Run:
 *   node --experimental-strip-types harness/tests/test_command_guard.ts
 */
import assert from "node:assert/strict";
import { guardHit } from "../extensions/command_guard.ts";

const BLOCKED = [
	// the call that cost this session 111s
	'grep -rn "bookmarks.txt" ~/dot ~/repos --include="*" -l',
	"grep -R foo .",
	"grep --recursive foo .",
	"egrep -r foo /etc",
	"/usr/bin/grep -rn foo .",
	"cd ~/repos && grep -rln foo .",
	"history | grep -r foo",
	// the fetch that blocks forever on a dead host
	"curl -fsSL https://herdr.dev/install.sh | sh",
	"curl https://example.com",
	"wget https://example.com",
	"timeout 30 curl https://example.com",
	// an unbounded test run: 300s + 194s in one session
	"emacs -Q --batch -l tests/todo_tests.el -f ert-run-tests-batch-and-exit",
	"cd ~/repos/Main_Quest && swift test",
	"python3 -m pytest tests/",
	"cargo test",
	"npm test",
	"NO_PROXY=1 python3 -m pytest",
	// BSD cat has no -A, and the flag aborts the call: one failed call, 2026-10-04
	"cat -A README.md",
	"sed -n '50,62p' README.md | cat -n | cat -A",
	"/bin/cat -vA file.txt",
	// temp files belong under ~/tmp; one redirect to /tmp failed, 2026-10-04
	"echo hi > /tmp/notes.txt",
	"python3 scripts/scan.py 2>/tmp/scan.err",
	"ls >/tmp/list.txt",
];

const ALLOWED = [
	'rg -n "bookmarks.txt" ~/repos',
	"grep -n foo file.txt",
	"grep -c foo file.txt",
	'git grep -n "pattern"',
	"xargs -r grep foo",
	'echo "never run grep -rn over your home"',
	"rg --files | grep -c test",
	"curl --max-time 20 https://example.com",
	"curl -fsSL --connect-timeout 5 https://example.com",
	"curl -m 20 https://example.com",
	"wget --timeout=60 https://example.com",
	// bounded test runs, and things that merely contain the word test
	"timeout 180 emacs -Q --batch -l tests/todo_tests.el -f ert-run-tests-batch-and-exit",
	"timeout 900 swift test",
	"scripts/test",
	"~/.agents/skills/todo/scripts/test",
	"rg -n test ~/repos",
	"grep -c test file.txt",
	"rm -rf .build/test-artifacts",
	// the safe forms of both, and a read from /tmp, which the rule allows
	"cat -v -e README.md",
	"cat -n README.md",
	"sed -n l README.md",
	"echo hi > ~/tmp/notes.txt",
	"python3 scripts/scan.py 2> ~/tmp/scan.err",
	"rg -n pattern /tmp/leftover.txt",
	"cat /tmp/leftover.txt | head -3",
	"python3 scripts/scan.py 2>&1 | tail -3",
];

for (const command of BLOCKED) {
	assert.notEqual(guardHit(command), null, `should block: ${command}`);
}
for (const command of ALLOWED) {
	assert.equal(guardHit(command), null, `should allow: ${command}`);
}
const grep = guardHit(BLOCKED[0]);
const curl = guardHit(BLOCKED[8]);
assert.equal(grep?.name, "recursive grep", grep);
assert.equal(curl?.name, "curl or wget with no maximum time", curl);
assert.match(grep?.fix ?? "", /rg -n/);
assert.match(curl?.fix ?? "", /--max-time 60/);
console.log(`command_guard ok: ${BLOCKED.length} blocked, ${ALLOWED.length} allowed`);
