/**
 * check for release_reminder.ts. Run:
 *   node --experimental-strip-types harness/tests/test_release_reminder.ts
 */
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { remind } from "../extensions/release_reminder.ts";

const dir = mkdtempSync(join(homedir(), "tmp/release-reminder-test-"));
const messages: string[] = [];
const notify = (message: string) => messages.push(message);
const state = () => readFileSync(join(dir, "last_notified_pi_version"), "utf8").trim();

// first run on empty state: baseline only, no reminder, state recorded
remind(dir, "1.0.4", notify);
assert.equal(messages.length, 0, "missing state must establish the baseline silently");
assert.equal(state(), "1.0.4");

// same version again: still silent
remind(dir, "1.0.4", notify);
assert.equal(messages.length, 0);

// version change: exactly one reminder naming both versions
remind(dir, "1.0.5", notify);
assert.equal(messages.length, 1);
assert.match(messages[0], /1\.0\.4/);
assert.match(messages[0], /1\.0\.5/);
assert.equal(state(), "1.0.5");

// empty state file reads as unknown, not as a baseline
writeFileSync(join(dir, "last_notified_pi_version"), "");
messages.length = 0;
remind(dir, "1.0.6", notify);
assert.equal(messages.length, 1);
assert.match(messages[0], /unknown/);
assert.equal(state(), "1.0.6");

console.log(`release reminder ok: baseline, same-version silence, one change reminder, unknown state`);
