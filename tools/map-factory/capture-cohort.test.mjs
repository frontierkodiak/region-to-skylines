import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync, existsSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const script = fileURLToPath(new URL('./capture-connections.mjs', import.meta.url));
const frozen = JSON.parse(readFileSync(new URL('./cohorts/playable-start-v1.json', import.meta.url)));

test('incomplete original manifests stop before capture or output creation', () => {
  for (const missing of [undefined, {}, { 'input.png': 'not-a-digest' }]) {
    const temporary = mkdtempSync(join(tmpdir(), 'cs1-cohort-'));
    try {
      const plan = structuredClone(frozen);
      plan.original[0].input_files_sha256 = missing;
      const input = join(temporary, 'registered.json'), output = join(temporary, 'output');
      writeFileSync(input, JSON.stringify(plan));
      const run = spawnSync(process.execPath, [script, output, '--plan', '--cohort', input], { encoding: 'utf8' });
      assert.notEqual(run.status, 0);
      assert.match(run.stderr, /Missing or invalid frozen input manifest/);
      assert.equal(existsSync(output), false);
    } finally { rmSync(temporary, { recursive: true, force: true }); }
  }
});
