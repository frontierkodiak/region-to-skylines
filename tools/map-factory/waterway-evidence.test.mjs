import assert from 'node:assert/strict';
import test from 'node:test';
import {assertPinnedTile,matchFrozen,surfaceGeometry,snapshotTiles,SNAPSHOT} from './waterway-evidence.js';
const sha='a'.repeat(64), evidenceSha='b'.repeat(64);
const tile={x:1,y:2,z:14,url:'https://example.test/pinned.pbf',sha256:sha,status:200};
function fixture() {
  const pieces=['tunnel',undefined,'bridge',undefined].map((brunnel,i)=>({
    class:'river',name:'same name',pts:[[i,0],[i+1,0]],feature_id:i+10,feature_index:i,line_index:0,piece_index:0,
    tile,properties:{class:'river',name:'same name',intermittent:i===3?1:0,...(brunnel?{brunnel}:{})}}));
  const frozen={sq:{rotation:37},rivers:pieces.map(p=>({name:p.name,pts:p.pts})),streams:[],roads:[{pts:[[1,2],[3,4]]}],lakes:[],riverAreas:[]};
  return {frozen,inspection:{pieces,tiles:[tile]}};
}
test('only explicit tunnel excluded; unlabelled/bridge/intermittent remain with exact points',()=>{
  const {frozen,inspection}=fixture(),original=structuredClone(frozen);
  const g=surfaceGeometry(frozen,inspection,sha,evidenceSha);
  assert.equal(g.rivers.length,3);assert.equal(g.undergroundWaterways.length,1);
  assert.deepEqual(g.rivers.map(f=>f.pts),frozen.rivers.slice(1).map(f=>f.pts));
  assert.equal(g.rivers[2].intermittent,1);assert.deepEqual(g.roads,frozen.roads);
  assert.deepEqual(g.sq,frozen.sq);assert.deepEqual(frozen,original);
  const u=g.undergroundWaterways[0];assert.equal(u.sourceFeature.feature_id,10);
  assert.equal(u.sourceFeature.tile.sha256,sha);assert.equal(u.sourceFeature.original_index,0);
  assert.equal(u.exclusionReason,'explicit waterway.brunnel=tunnel');
  assert.equal(g.surfaceWaterPolicy.waterwayEvidenceSha256,evidenceSha);
});
test('touching pieces are never joined across an underground segment',()=>{
  const {frozen,inspection}=fixture();inspection.pieces[1].properties.brunnel='tunnel';
  delete inspection.pieces[0].properties.brunnel;
  const g=surfaceGeometry(frozen,inspection,sha,evidenceSha);
  assert.deepEqual(g.rivers.map(f=>f.sourceFeature.original_index),[0,2,3]);
  assert.deepEqual(g.rivers[0].pts,[[0,0],[1,0]]);assert.deepEqual(g.rivers[1].pts,[[2,0],[3,0]]);
});
test('unknown/ambiguous geometry and name mismatches fail rather than guess',()=>{
  for (const kind of ['missing','duplicate','duplicate-frozen','name']) {
    const {frozen,inspection}=fixture();
    if(kind==='missing') inspection.pieces.pop();
    if(kind==='duplicate') inspection.pieces.push({...inspection.pieces[0],feature_id:999});
    if(kind==='name') inspection.pieces[0].name='other';
    if(kind==='duplicate-frozen') frozen.rivers.push(structuredClone(frozen.rivers[0]));
    assert.throws(()=>surfaceGeometry(frozen,inspection,sha,evidenceSha),/unknown\/ambiguous/);
  }
});
test('exact piece clipping/reversal matters; no proximity match',()=>{
  const {frozen,inspection}=fixture();inspection.pieces[0].pts=[...inspection.pieces[0].pts].reverse();
  assert.equal(matchFrozen(frozen,inspection.pieces).unknown.length,1);
});
test('changed/missing tile SHA, HTTP status and unbound source evidence rejected',()=>{
  assert.doesNotThrow(()=>assertPinnedTile(tile,200,sha));
  for (const [spec,status,actual] of [[tile,200,evidenceSha],[tile,404,sha],[{...tile,sha256:null},200,sha]])
    assert.throws(()=>assertPinnedTile(spec,status,actual),/pinned tile/);
  const {frozen,inspection}=fixture();assert.throws(()=>surfaceGeometry(frozen,inspection,sha,null),/SHA binding/);
  inspection.pieces[0].properties.brunnel='unknown';
  assert.throws(()=>surfaceGeometry(frozen,inspection,sha,evidenceSha),/unknown waterway/);
});
test('identical buffer multiset retains every duplicate and all provenance without tile assignment',()=>{
  const {frozen,inspection}=fixture();
  frozen.rivers.push(structuredClone(frozen.rivers[0]));
  inspection.pieces.push({...structuredClone(inspection.pieces[0]),tile:{...tile,x:2,url:'https://example.test/tile2.pbf',sha256:evidenceSha},feature_index:40});
  const g=surfaceGeometry(frozen,inspection,sha,evidenceSha);
  assert.equal(g.undergroundWaterways.length,2); // never deduplicate frozen geometry
  for(const u of g.undergroundWaterways) {
    const s=u.sourceFeature;assert.equal(s.tile,null);assert.equal(s.feature_index,null);
    assert.equal(s.properties.brunnel,'tunnel');assert.equal(s.provenanceGroup.source_count,2);
    assert.equal(s.provenanceGroup.frozen_count,2);assert.equal(s.provenanceGroup.members.length,2);
    assert.equal(s.provenanceGroup.evidence_sha256,evidenceSha);
    assert.deepEqual(s.provenanceGroup.members.map(p=>p.feature_index),[0,40]);
    assert.deepEqual(s.provenanceGroup.members.map(p=>p.tile.sha256),[sha,evidenceSha]);
  }
  assert.equal(g.surfaceWaterPolicy.provenanceGroupCount,1);
});
test('buffer grouping rejects ID/property/tag/multiplicity disagreement',()=>{
  for(const kind of ['id','tag','property','class','coordinates','count']) {
    const {frozen,inspection}=fixture();frozen.rivers.push(structuredClone(frozen.rivers[0]));
    const duplicate=structuredClone(inspection.pieces[0]);
    if(kind==='id') duplicate.feature_id=999;
    if(kind==='tag') duplicate.properties.brunnel='bridge';
    if(kind==='property') duplicate.properties.intermittent=1;
    if(kind==='class') duplicate.class='stream';
    if(kind==='coordinates') duplicate.pts[1][0]+=.01;
    if(kind!=='count') inspection.pieces.push(duplicate);
    assert.throws(()=>surfaceGeometry(frozen,inspection,sha,evidenceSha),/unknown\/ambiguous/);
  }
});
test('snapshot tile requests preserve recorded hashes and separate padded river/unpadded stream scope',()=>{
  const frozen={zoom:14,sq:{rotation:37}};
  const original={x:0,y:0,z:14,status:200,sha256:sha,url:`https://tiles.openfreemap.org/planet/${SNAPSHOT}/14/0/0.pbf`};
  const t={bbox:(_,pad)=>pad,tileRange:pad=>({x0:0,y0:0,x1:pad?1:0,y1:pad?1:0})};
  const jobs=snapshotTiles(frozen,[original],t);
  assert.equal(jobs.length,4);assert.equal(jobs[0].sha256,sha);
  assert.equal(jobs.filter(j=>j.streamEligible).length,1);
  assert.equal(jobs.filter(j=>j.sha256===undefined).length,3);
  assert.ok(jobs.every(j=>j.url.includes(`/${SNAPSHOT}/`)));
  assert.throws(()=>snapshotTiles(frozen,[{...original,url:original.url.replace(SNAPSHOT,'latest')}],t),/snapshot/);
  assert.throws(()=>snapshotTiles(frozen,[original,original],t),/duplicate recorded/);
});
