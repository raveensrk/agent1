/**
 * check for rules_context.ts. Run:
 *   node --experimental-strip-types harness/tests/test_rules_context.ts
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { rulesSection } from "../extensions/rules_context.ts";

const section = rulesSection("# Common\n\n## Working style\n\n- be precise\n");
assert.match(section, /^## Rules \(loaded from ~\/repos\/agent1\/common\.md\)/);
assert.match(section, /## Working style/);
assert.match(section, /- be precise/);
assert.match(section, /Read the topic file when the task touches it:/);
assert.match(section, /- agent1\/jobs\.md - ETA rules for long-running jobs/);
assert.ok(!section.endsWith("\n\n"), "the section must not end on a blank line");

// nothing to say, nothing appended
assert.equal(rulesSection(""), "");
assert.equal(rulesSection("   \n"), "");

// the file this reads in a real session is the canonical rules file
const common = readFileSync(join(homedir(), "repos/agent1/common.md"), "utf8");
const real = rulesSection(common);
assert.match(real, /## Output style/, "common.md's sections must survive verbatim");
assert.ok(real.includes(common.trim()), "the rules body must be the file itself");
assert.ok(real.split("\n").length > 200, `expected the whole file, got ${real.split("\n").length} lines`);

console.log(`rules_context: all checks passed (${real.split("\n").length} lines of rules)`);
