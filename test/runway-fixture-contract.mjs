// Additive capture capability. Historical source/native receipts remain historical.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { loadWaterRiskContract } from './water-risk-fixture-contract.mjs';
const sha = b => createHash('sha256').update(b).digest('hex');
const parse = b => JSON.parse(new TextDecoder().decode(b));
const PREFIX = 'contracts/pl1066-optional-runways-v1/';
export async function loadRunwayContract({ read, readSource, current, historical, historicalNativeCases, factoryFiles }) {
  const adoption = current.capture_adoption;
  assert.deepEqual(Object.keys(adoption).sort(), ['compatibility', 'historical_inputs', 'predecessor', 'previous_active']);
  const bound = async (key, filename) => {
    assert.equal(adoption[key].file, PREFIX + filename);
    const bytes = await read('fixtures/' + adoption[key].file);
    assert.equal(sha(bytes), adoption[key].sha256, `${key}: capture archive changed`);
    return bytes;
  };
  const previousBytes = await bound('predecessor', 'predecessor.json'), previous = parse(previousBytes);
  assert.equal(sha(await read('fixtures/contracts/pl912-water-risk-v1/current.json')), sha(previousBytes), 'predecessor contract changed');
  assert.equal(previous.version, 'pl912-water-risk-v1');
  const activeBytes = await bound('previous_active', 'previous-active.json');
  assert.deepEqual(parse(activeBytes), { format: 2, current: 'contracts/pl912-water-risk-v1/current.json', historical_current: 'current.json' });
  const inputs = await bound('historical_inputs', 'historical-inputs.js');
  assert.equal(sha(inputs), previous.source_files_sha256['inputs.js'], 'historical capture source changed');
  assert.deepEqual(current, { ...previous,
    version: 'pl1066-optional-runways-v1',
    scope: 'Optional runway capture; default capture byte compatibility; no new native qualification or physical package',
    source_files_sha256: { ...previous.source_files_sha256, 'inputs.js': sha(await readSource('inputs.js')) },
    capture_adoption: adoption,
  }, 'current contract source changed or predecessor evidence relabelled');
  const proof = parse(await bound('compatibility', 'capture-compatibility.json'));
  assert.equal(proof.status, 'default_capture_byte_compatible_not_native_qualification');
  assert.equal(proof.native_tested, false);
  assert.equal(proof.source_sha256.historical_inputs, sha(inputs));
  assert.equal(proof.source_sha256.current_inputs, current.source_files_sha256['inputs.js']);
  assert.equal(proof.source_sha256.terrain, sha(await readSource('terrain.js')));
  assert.equal(proof.source_sha256.proof_driver, sha(await readSource('test/capture-runway-proof.mjs')));
  assert.equal(proof.cases.length, 4);
  for (const c of proof.cases) {
    assert.deepEqual(c.historical, c.current_default, 'default capture byte mismatch');
    assert.deepEqual(c.historical, c.explicit_false, 'explicit default capture byte mismatch');
    assert.deepEqual(c.historical_keys, c.default_keys);
    assert.deepEqual(c.historical_provenance_keys, c.default_provenance_keys);
    for (const name of ['png', 'banks', 'game']) assert.equal(c.enabled[name], c.historical[name]);
  }
  const base = await loadWaterRiskContract({ read, readSource: name => name === 'inputs.js' ? inputs : readSource(name),
    current: previous, historical, historicalNativeCases, factoryFiles });
  return { ...base, current, historicalCaptureSources: { 'inputs.js': adoption.historical_inputs } };
}
