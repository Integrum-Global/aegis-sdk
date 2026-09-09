#!/usr/bin/env node
/**
 * lifecycle-driver.mjs — run a derivation against a tree, in a REAL process.
 *
 * The fixture cases could import `auditLifecycle` and call it directly, and that
 * would be cheaper. It is a child process for two reasons, and only the second
 * is about style:
 *
 *   1. THE MUTATION CONTROLS NEED A DIFFERENT MODULE. A control copies
 *      `lifecycle.mjs`, breaks one line in the copy, and requires the suite to
 *      notice. In-process that means importing two modules with the same
 *      specifier, which the module cache makes awkward and, once cached, silently
 *      wrong — the second import returns the FIRST module and the mutation is
 *      never exercised, which is an inert mutation wearing a passing test.
 *
 *   2. It matches the hook cases beside it: real script, real exit code.
 *
 * Exit: 0 the derivation found nothing · 2 it found at least one problem.
 * Never 1 — that is node's own failure code, and a crash must not be readable
 * as a finding.
 */

import { pathToFileURL } from "node:url";

const [, , lifecyclePath, root, overlays] = process.argv;
const { auditLifecycle } = await import(pathToFileURL(lifecyclePath).href);
const audit = auditLifecycle(root, { overlays: overlays === "1" });
if (audit.problems.length) {
  for (const p of audit.problems) process.stderr.write("PROBLEM  " + p + "\n");
  process.exit(2);
}
process.exit(0);
