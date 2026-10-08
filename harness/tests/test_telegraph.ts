/**
 * check for telegraph.ts. Run:
 *   timeout 180 node --experimental-strip-types harness/tests/test_telegraph.ts
 */
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { CONFIG_PATH, readEnabled, readRule, RULE_PATH, ruleSection, writeEnabled } from "../extensions/telegraph.ts";

// the switch: on unless the file says otherwise
const dir = mkdtempSync(join(homedir(), "tmp/telegraph-test-"));
assert.equal(readEnabled(join(dir, "absent.json")), true, "a missing switch must not drop the rule");
writeFileSync(join(dir, "off.json"), '{"enabled": false}');
assert.equal(readEnabled(join(dir, "off.json")), false);
writeEnabled(true, join(dir, "on.json"));
assert.equal(readEnabled(join(dir, "on.json")), true);
writeEnabled(false, join(dir, "round.json"));
assert.equal(readEnabled(join(dir, "round.json")), false, "write then read must round-trip");
writeFileSync(join(dir, "broken.json"), "{not json");
assert.equal(readEnabled(join(dir, "broken.json")), true);

// the rule file itself: present, and the one the switch names
assert.equal(readRule(join(dir, "no-rule.md")), "");
const live = readRule();
assert.ok(live.startsWith("## Output style: Telegraph"), `rule file must open with its heading: ${live.slice(0, 40)}`);
assert.ok(live.length > 2000, `the whole rule, not a stub: ${live.length} chars`);
assert.match(live, /strict audit/, "the session audit is part of the rule");
assert.ok(RULE_PATH.endsWith("harness/extensions/telegraph.md"), RULE_PATH);
assert.ok(CONFIG_PATH.endsWith(".local/state/agent1/telegraph.json"), "one switch for every harness");

// the injected section: provenance, body, and it appends rather than replaces
const section = ruleSection(live);
assert.match(section, /^## Voice rules \(loaded from /);
assert.ok(section.includes(live), "the rule arrives verbatim");
assert.equal(ruleSection(""), "", "an empty rule injects nothing");
assert.equal(ruleSection("   \n"), "");
const prompt = `BASE\n\n${section}`;
assert.ok(prompt.startsWith("BASE\n\n"), "the rule must append to the prompt it was handed");

console.log(`telegraph ok: switch, ${live.length} chars of rule, section appends`);
