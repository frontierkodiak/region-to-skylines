import {test} from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {liveShore, evaluateWater, bankCandidate} from "../water-model.js";
import {waterDetail} from "../capability-ui.js";
import {validateLedger} from "../capability-ledger.mjs";
const N=1081;
const grids=()=>{
  const g=new Float64Array(N*N).fill(103),d=new Float64Array(N*N);
  // North-first east/west channel in the southern half; equal wet share on all variants.
  for(let r=560;r<=564;r++)for(let c=0;c<N;c++){g[r*N+c]=100;d[r*N+c]=2;}
  return [g,d];
};
test("live bank geometry depends on terrain, not wet share; north/south conversion",()=>{
  const [g,d]=grids(),a=liveShore(g,d);
  assert.equal(a.opportunity,"candidate");assert.equal(a.level,"likely");
  assert.ok(a.wet_point_xz[1]<0);
  assert.equal(a.predicted,null);assert.equal(a.service,"unknown");
  assert.match(waterDetail(a),/Shore\/bank.*candidate.*Service.*Unknown.*Not comparable/);
  // Raise only dry terrain beyond the max freeboard. Wet share is unchanged.
  for(let i=0;i<g.length;i++)if(!d[i])g[i]=120;
  assert.equal(liveShore(g,d).opportunity,"unknown");
  assert.equal(liveShore(g,d).level,"unknown");
  assert.equal(liveShore(...grids(),{spacing:64}).opportunity,"unknown");
  assert.equal(liveShore([100],[0]).opportunity,"unknown");
  g[0]=NaN;assert.equal(liveShore(g,d).level,"unknown");
});
test("bank requires depth/freeboard/slope and snap distance",()=>{
  const [g,d]=grids();
  assert.ok(bankCandidate(g,d,[0,0,-352],102,12,true));
  // Anchor in dry ground must not succeed even with a bank in radius.
  assert.equal(bankCandidate(g,d,[0,0,500],102,12,true),null);
});
test("water sources, predicates and scores cannot inherit archived qualification",()=>{
  const ledger=JSON.parse(readFileSync(new URL("../capabilities.json",import.meta.url)));
  const water=ledger.capabilities.find((c)=>c.id==="water");
  assert.equal(water.game_agreement.length,0);
  assert.equal(water.runtime_model.agreement,"unscored_new_runtime");
  for(const mutate of [
    (c)=>{c.runtime_model.parameters.bank.minimum_wet_depth_m=0.5;},
    (c)=>{c.runtime_model.source_sha256["water-model.js"]="0".repeat(64);},
    (c)=>{c.runtime_model.agreement="qualified";},
    (c)=>{c.game_agreement.push({agreement:1});},
    (c)=>{c.browser_check=null;},
  ]){
    const changed=structuredClone(ledger);mutate(changed.capabilities.find((c)=>c.id==="water"));
    assert.throws(()=>validateLedger(changed),/scope changed|agreement|Unbound game evidence/);
  }
  assert.equal(evaluateWater({planner_enabled:{water:false}}).level,"unknown");
});


test("bank slope equality and shallow-apron snap gap",()=>{
  for(const [slope,expected] of [[.15,true],[.15001,false]]){
    const g=new Float64Array(N*N),d=new Float64Array(N*N);
    for(let r=0;r<N;r++)for(let c=0;c<N;c++){
      g[r*N+c]=(c-540)*16*slope;if(r>=538&&r<543)d[r*N+c]=2;
    }
    assert.equal(!!bankCandidate(g,d,[0,0,0],2,12),expected);
  }
  for(const [shore,expected] of [[80,true],[96,false]]){
    const g=new Float64Array(N*N),d=new Float64Array(N*N);
    for(let r=0;r<N;r++)for(let c=0;c<N;c++){
      const x=(c-540)*16;g[r*N+c]=x>=shore?103:100;
      d[r*N+c]=x<=32?2:x<shore?.5:0;
    }
    assert.equal(!!bankCandidate(g,d,[0,0,0],102,12),expected);
  }
});
