import test from 'node:test';
import assert from 'node:assert/strict';
import { runwayAirport } from '../inputs.js';

test('runway axis supplies the real-roads airport contract', () => {
  const airport = runwayAirport([{ ref: '09/27', pts: [[0, 0], [0.02, 0]] }]);
  assert.deepEqual(airport, { name: '09/27', lat: 0, lon: 0.01, heading: 90 });
});

test('selection is deterministic across tile order and line reversal', () => {
  const runways = [
    { name: 'short', pts: [[0, 0], [0, 0.01]] },
    { name: 'long', pts: [[0, 0.04], [0, 0]] },
    { name: 'tie', pts: [[1, 0], [1, 0.04]] },
  ];
  const first = runwayAirport(runways);
  assert.equal(first.name, 'long');
  assert.deepEqual(first, runwayAirport(runways.reverse().map(r => ({ ...r, pts: [...r.pts].reverse() }))));
});

test('missing, point and invalid runway evidence does not invent an airport', () => {
  assert.equal(runwayAirport([]), null);
  assert.equal(runwayAirport([{ pts: [[0, 0]] }, { pts: [[1, 1], [1, 1]] }, { pts: [[NaN, 0], [1, 1]] }]), null);
});

import { readFile } from 'node:fs/promises';
import { captureProof } from './capture-runway-proof.mjs';
import { loadFixtureContract } from './fixture-contract.mjs';
const factoryRoot = new URL('../tools/map-factory/', import.meta.url);
const read = name => readFile(new URL(name, factoryRoot));
const source = name => readFile(new URL('../' + name, import.meta.url));

test('archived and live captures reproduce exact default bytes; only explicit opt-in reads runway evidence', async () => {
  const stored = JSON.parse(await read('fixtures/contracts/pl1066-optional-runways-v1/capture-compatibility.json'));
  const proof = await captureProof();
  assert.deepEqual(proof, stored);
  for (const c of proof.cases) {
    assert.deepEqual(c.historical, c.current_default);
    assert.deepEqual(c.historical, c.explicit_false);
    assert.deepEqual(c.historical_keys, c.default_keys);
    assert.deepEqual(c.historical_provenance_keys, c.default_provenance_keys);
    assert.ok(!c.default_keys.includes('runways') && !c.default_keys.includes('airport'));
    assert.ok(!c.default_provenance_keys.includes('runway'));
    if (c.sq.lon === 120) { assert.equal(c.runway_pieces, 0); assert.equal(c.airport, null); }
    else { assert.ok(c.runway_pieces > 0); assert.equal(c.airport.heading, 90); assert.equal(c.airport.name, '09/27'); }
  }
});

test('capture adoption refuses changed snapshots, compatibility proof, live source and active pointer', async () => {
  for (const suffix of ['historical-inputs.js', 'capture-compatibility.json', 'previous-active.json', 'predecessor.json'])
    await assert.rejects(loadFixtureContract(async name => {
      const bytes = await read(name);
      return name.endsWith('pl1066-optional-runways-v1/' + suffix) ? Buffer.concat([bytes, Buffer.from(' ')]) : bytes;
    }, source), /capture archive changed/);
  await assert.rejects(loadFixtureContract(read, async name => name === 'inputs.js' ? Buffer.from('changed source') : source(name)), /current contract source changed/);
});
