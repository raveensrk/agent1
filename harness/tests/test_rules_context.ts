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

// a trial rule reaches the prompt, and reads after the rules it can override
const trial = "# Experimental rules\n\n## Name\n\nYour name is Optimus Prime.\n";
const both = rulesSection("# Common\n\n- be precise\n", undefined, trial);
const EXP_HEADER = "## Experimental rules (loaded from ~/repos/agent1/experimental.md)";
assert.match(both, new RegExp(EXP_HEADER.replace(/[.()/]/g, "\\$&")), "the trial rules must be injected");
assert.ok(both.includes("Your name is Optimus Prime."), "the trial rule body must arrive verbatim");
assert.ok(both.includes("- be precise"), "common.md must survive alongside it");
assert.ok(
	both.indexOf("## Rules (loaded from") < both.indexOf(EXP_HEADER),
	"common.md reads first so the trial rules can override it above",
);
assert.ok(!both.endsWith("\n\n"), "the section must not end on a blank line");

// an empty or absent experimental.md adds nothing
assert.ok(!rulesSection("# Common\n", undefined, "").includes("Experimental rules"));
assert.ok(!rulesSection("# Common\n", undefined, "  \n").includes("Experimental rules"));

// the file this reads in a real session is the canonical rules file
const common = readFileSync(join(homedir(), "repos/agent1/common.md"), "utf8");
const real = rulesSection(common);
assert.match(real, /## Output style/, "common.md's sections must survive verbatim");
assert.ok(real.includes(common.trim()), "the rules body must be the file itself");
assert.ok(real.split("\n").length > 200, `expected the whole file, got ${real.split("\n").length} lines`);

// and the live trial rules file is the one a real session gets
const experimental = readFileSync(join(homedir(), "repos/agent1/experimental.md"), "utf8");
const live = rulesSection(common, undefined, experimental);
assert.ok(
	live.endsWith(experimental.trim()),
	"the experimental file must arrive whole, as the last thing in the section",
);
assert.ok(
	live.indexOf("## Rules (loaded from") < live.indexOf(EXP_HEADER),
	"ordering holds for the real files too",
);

console.log(
	`rules_context: all checks passed (${real.split("\n").length} lines of rules, ` +
		`${experimental.trim().split("\n").length} of trial rules)`,
);
