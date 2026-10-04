/**
 * check for command_guard.ts. Run:
 *   node --experimental-strip-types harness/tests/test_command_guard.ts
 */
import assert from "node:assert/strict";
import { executableText, guardHit } from "../extensions/command_guard.ts";

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
	// the real shapes stay caught: a runner after a quoted argument, a bound
	// written inside quotes, and a real suite after a closed heredoc
	'python3 -m pytest "tests/unit" -q',
	'echo "timeout 900" && python3 -m pytest tests/',
	[
		"cat <<'EOF' > ~/tmp/notes.txt",
		"nothing to see here",
		"EOF",
		"python3 -m pytest tests/",
	].join("\n"),
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
	// a quoted mention and a heredoc body are data, not commands. Both blocked
	// real work on 2026-10-04: a quoted echo, and a note written through a
	// heredoc. A script built inside a heredoc can still hide a run; that false
	// negative is the price of never blocking note text.
	"rg -n 'pytest' ~/repos/agent1/harness/tests/test_lint.py | head -5",
	"echo '=== pytest test names ==='",
	[
		"python3 - <<'PY'",
		"import subprocess",
		'subprocess.run(["pytest", "tests/"])',
		"PY",
	].join("\n"),
	[
		"cat <<'EOF' > ~/tmp/scratch.sh",
		"grep -rn foo ~/repos",
		"EOF",
		"chmod +x ~/tmp/scratch.sh",
	].join("\n"),
	"timeout 180 python3 -m pytest tests/",
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

// the text the patterns read: quoted spans and heredoc bodies are gone
assert.ok(!executableText("echo 'pytest'").includes("pytest"), "quoted spans must be dropped");
assert.match(executableText("cat <<'EOF' > f\nbody\nEOF\nls"), /^cat <<.* > f\nls$/, "body and terminator go, the tail stays");
assert.equal(executableText("cat <<'EOF' > f\nunclosed"), "cat <<'' > f", "an unterminated heredoc swallows the rest");

console.log(`command_guard ok: ${BLOCKED.length} blocked, ${ALLOWED.length} allowed`);
