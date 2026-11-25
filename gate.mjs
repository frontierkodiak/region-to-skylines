#!/usr/bin/env node
// The gate: one command that runs every suite this repo holds, the shipped CLI on a
// committed region, and the byte-conformance fixtures. CI runs exactly this.
//
//   npm run gate            everything (about ten minutes; the fixtures dominate)
//   npm test                every Node suite, including the CLI region run (fast)
//   npm run test:fixtures   just the byte-conformance fixtures
//   npm run test:cli        just the CLI region run
//
// Suites deliberately left out are listed with their reason in README.md, "Development".
import { spawnSync } from "node:child_process";
import { readdirSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL(".", import.meta.url));
const mode = process.argv[2] ?? "all";
const ignore = new Set(["node_modules", ".venv", "dist", ".git", "__pycache__"]);

/** Every *.test.mjs / *.test.js in the repo, except the slow conformance suite below. */
function nodeTests(dir = ".", found = []) {
  for (const entry of readdirSync(join(root, dir), { withFileTypes: true })) {
    if (ignore.has(entry.name)) continue;
    const path = dir === "." ? entry.name : `${dir}/${entry.name}`;
    if (entry.isDirectory()) nodeTests(path, found);
    else if (/\.test\.(mjs|js)$/.test(entry.name) && path !== "test/fixtures.test.mjs") found.push(path);
  }
  return found.sort();
}

const stages = [];
const stage = (name, command, args, cwd = root) => stages.push({ name, command, args, cwd });

if (mode === "all" || mode === "node") {
  stage("node: every suite, including the CLI region run", process.execPath,
    ["--test", "--test-concurrency=1", ...nodeTests()]);
}
if (mode === "all" || mode === "python") {
  // unittest discovery is what these tools ship; it leaves out fixtures/** (quarantined
  // rejected candidates, not suites) and the two place-model tests skip themselves.
  stage("python: map-factory", "uv", ["run", "--project", ".", "--frozen", "python", "-m", "unittest", "discover", "-p", "test_*.py"], join(root, "tools/map-factory"));
  stage("python: cs1-harness", "uv", ["run", "--project", ".", "--frozen", "python", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"], join(root, "tools/cs1-harness"));
  stage("python: save-reader", "uv", ["run", "--project", ".", "--frozen", "pytest", "-q", "-rs"], join(root, "tools/save-reader"));
}
if (mode === "all") {
  stage("fixtures: five regions, exact .crp bytes", process.execPath,
    ["--test", "--test-concurrency=1", "test/fixtures.test.mjs"]);
}

const started = Date.now();
let failed = null;
for (const { name, command, args, cwd } of stages) {
  process.stdout.write(`\n== ${name}\n`);
  const began = Date.now();
  const result = spawnSync(command, args, { cwd, stdio: "inherit" });
  const seconds = ((Date.now() - began) / 1000).toFixed(1);
  if (result.status !== 0) {
    failed = `${name} (exit ${result.status ?? result.signal})`;
    break;
  }
  process.stdout.write(`   ${name}: ${seconds} s\n`);
}
if (failed) {
  process.stderr.write(`\ngate failed at ${failed}\n`);
  process.exit(1);
}
process.stdout.write(`\ngate passed: ${stages.length} stages in ${((Date.now() - started) / 1000).toFixed(1)} s\n`);
