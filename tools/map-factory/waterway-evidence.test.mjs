import assert from 'node:assert/strict';
import test from 'node:test';
import {assertPinnedTile,matchFrozen,surfaceGeometry} from './waterway-evidence.js';
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
