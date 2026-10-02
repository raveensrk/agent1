/**
 * check for search_guard.ts. Run:
 *   node --experimental-strip-types harness/tests/test_search_guard.ts
 */
import assert from "node:assert/strict";
import { recursiveGrep } from "../extensions/search_guard.ts";

const BLOCKED = [
	// the call that cost this session 111s
	'grep -rn "bookmarks.txt" ~/dot ~/repos --include="*" -l',
	"grep -R foo .",
	"grep --recursive foo .",
	"egrep -r foo /etc",
	"/usr/bin/grep -rn foo .",
	"cd ~/repos && grep -rln foo .",
	"history | grep -r foo",
];

const ALLOWED = [
	'rg -n "bookmarks.txt" ~/repos',
	"grep -n foo file.txt",
	"grep -c foo file.txt",
	'git grep -n "pattern"',
	"xargs -r grep foo",
	'echo "never run grep -rn over your home"',
	"rg --files | grep -c test",
];

for (const command of BLOCKED) {
	assert.equal(recursiveGrep(command), true, `should block: ${command}`);
}
for (const command of ALLOWED) {
	assert.equal(recursiveGrep(command), false, `should allow: ${command}`);
}
console.log(`search_guard ok: ${BLOCKED.length} blocked, ${ALLOWED.length} allowed`);
