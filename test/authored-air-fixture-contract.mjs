// New byte expectations do not overwrite or qualify any old native package.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {FACTORY_FILES} from '../mapgen.js';
import {loadSeaNeighbourContract} from './sea-neighbour-fixture-contract.mjs';
const sha=b=>createHash('sha256').update(b).digest('hex');
const parse=b=>JSON.parse(new TextDecoder().decode(b));
const PREFIX='contracts/pl1119-authored-air-v1/';
const PARENT='contracts/pl1072-sea-neighbours-v1/current.json';

export async function loadAuthoredAirContract({read,readSource,liveSource,current,historical,historicalNativeCases,factoryFiles}){
  assert.deepEqual(Object.keys(current).sort(),['format','version','status','scope','predecessor','source_files_sha256','export_gate_files_sha256','baseline_sources','proof','cases'].sort());
  assert.equal(current.format,1);assert.equal(current.version,'pl1119-authored-air-v1');
  assert.equal(current.status,'byte_conformance_only_not_native_tested');
  assert.equal(current.scope,'Add plane entries; retain all earlier fixture and native evidence without qualifying the new packages');
  assert.equal(current.predecessor.file,PARENT);
  const raw=await read('fixtures/'+PARENT);
  assert.equal(sha(raw),current.predecessor.sha256,'Air predecessor contract changed');
  const parent=parse(raw);
  assert.deepEqual(current.export_gate_files_sha256,parent.export_gate_files_sha256);
  assert.deepEqual(Object.keys(current.baseline_sources).sort(),['mapgen.js','tools/map-factory/generate.py']);
  for(const[name,item]of Object.entries(current.baseline_sources)){
    assert.equal(item.file,'contracts/pl1119-capability-ui-v1/baseline/'+name.split('/').at(-1));
    const bytes=await read('fixtures/'+item.file);
    assert.equal(sha(bytes),item.sha256);assert.equal(item.sha256,parent.source_files_sha256[name]);
    assert.equal(sha(await readSource(name)),item.sha256);
  }
  assert.deepEqual(Object.keys(current.source_files_sha256).sort(),['inputs.js','terrain.js','mapgen.js',...FACTORY_FILES.map(f=>'tools/map-factory/'+f)].sort());
  for(const[name,digest]of Object.entries(current.source_files_sha256)){
    assert.equal(sha(await liveSource(name)),digest,`${name}: current contract source changed`);
    if(parent.source_files_sha256[name]&&!current.baseline_sources[name])
      assert.equal(digest,parent.source_files_sha256[name],`${name}: unrelated writer change`);
  }
  const prior=await loadSeaNeighbourContract({read,readSource,current:parent,historical,historicalNativeCases,factoryFiles});
  assert.equal(current.proof.file,PREFIX+'proof.json');
  const proofBytes=await read('fixtures/'+current.proof.file);
  assert.equal(sha(proofBytes),current.proof.sha256,'Air byte proof changed');
  const proof=parse(proofBytes);assert.equal(proof.native_tested,false);
  assert.deepEqual(proof.predecessor,current.predecessor);
  assert.deepEqual(proof.source_files_sha256,current.source_files_sha256);
  assert.deepEqual(current.cases.map(c=>c.slug),prior.manifest.cases.map(c=>c.slug));
  assert.deepEqual(proof.cases.map(r=>[r.slug,r.kind]),current.cases.flatMap(c=>['reference','shipping'].map(k=>[c.slug,k])));
  const cases=[];
  for(const c of current.cases){
    assert.deepEqual(Object.keys(c).sort(),['reference','shipping','slug']);
    const old=parent.cases.find(p=>p.slug===c.slug),base=prior.manifest.cases.find(p=>p.slug===c.slug);
    for(const kind of ['reference','shipping']){
      const expected=c[kind],row=proof.cases.find(r=>r.slug===c.slug&&r.kind===kind);
      assert.deepEqual(Object.keys(expected).sort(),['expected_crp_bytes','expected_crp_sha256','expected_simulation_sha256']);
      assert.deepEqual(row.after,expected);
      assert.deepEqual(row.before,Object.fromEntries(Object.keys(expected).map(k=>[k,old[kind][k]])));
      assert.deepEqual(row.prepared_sha256,old.reference.prepared_sha256);
      assert.equal(row.other_managers_equal,true);assert.equal(row.existing_network_equal,true);assert.ok(row.plane_entries>=2);
    }
    const next={...base,...c.reference,shipping:{...base.shipping,...c.shipping,source_files_sha256:current.source_files_sha256},air_delta:c};
    // The earlier presentation proof remains checked above against its own bytes.
    // It must not be asserted against the now different NetManager payload.
    delete next.presentation_delta;delete next.shipping.presentation_delta;
    cases.push(next);
  }
  return {...prior,current,historicalScreen:prior.current,manifest:{...prior.manifest,cases},nativeQualification:'not_tested_for_authored_air_packages'};
}
