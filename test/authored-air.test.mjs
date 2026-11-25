import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {loadFixtureContract} from './fixture-contract.mjs';
const read=name=>readFile(new URL('../tools/map-factory/'+name,import.meta.url));
const source=name=>readFile(new URL('../'+name,import.meta.url));

test('Air byte reference retains five cases and does not inherit native qualification',async()=>{
  const result=await loadFixtureContract(read,source);
  assert.equal(result.current.version,'pl1119-authored-air-v1');
  assert.equal(result.nativeQualification,'not_tested_for_authored_air_packages');
  assert.equal(result.manifest.cases.length,5);
  assert.equal(result.historicalScreen.version,'pl1072-sea-neighbours-v1');
  for(const c of result.manifest.cases){
    assert.ok(c.air_delta.reference.expected_crp_bytes>0);
    assert.equal(c.shipping.source_files_sha256['mapgen.js'],result.current.source_files_sha256['mapgen.js']);
  }
});
