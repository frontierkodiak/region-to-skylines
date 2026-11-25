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
  assert.match(waterDetail(a),/Mapped wet shore.*stability is untested/);
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

const ledgerForBoundary = JSON.parse(readFileSync(new URL("../capabilities.json",import.meta.url)));
const coreWater = async (input) => {
  const {checkCapabilities}=await import("../capability-model.js");
  return checkCapabilities({schema:1,mode:"estimate",...input},ledgerForBoundary).capabilities.water;
};
test("estimate boundary strips injected promise, No and proof fields",async()=>{
  for(const level of ["promised","not_possible_here"]){
    const water=await coreWater({water_opportunity:{level,service:"verified",quality:"clean",native_agreement:"qualified",certificate:{valid:true}}});
    assert.equal(water.level,"unknown");
    for(const key of ["service","quality","flow","hookup"])assert.equal(water[key],"unknown");
    assert.equal(water.predicted,null);
    assert.equal(water.certificate,undefined);
    assert.match(water.native_agreement,/^unscored/);
  }
});
test("computed opportunity is projected independently of caller qualification claims",async()=>{
  const valid=liveShore(...grids());
  const original=await coreWater({water_opportunity:valid});
  assert.equal(original.level,"likely");
  const claims={...valid,level:"promised",predicted:true,service:"verified",flow:"verified",
    quality:"clean",hookup:"verified",native_agreement:"qualified",certificate:{valid:true},witness:{qualified:true}};
  assert.deepEqual(await coreWater({water_opportunity:claims}),original);
  for(const opportunity of [null,{},[],{...valid,model:"unsupported"},{...valid,fidelity:"coarse"},
    {...valid,bank:null},{...valid,wet_point_xz:[0,0]},
    {...valid,bank:{...valid.bank,water_anchor:[0,0,500]}},
  ]){
    const water=await coreWater({water_opportunity:opportunity});
    assert.equal(water.level,"unknown");
    assert.equal(water.predicted,null);
  }
});
test("Unicode code-point order matches Python for route iteration and tied witnesses",async()=>{
  const {channelCandidate}=await import("../water-model.js");
  const g=Float64Array.from({length:N*N},(_,i)=>100-(i%N)/64),d=new Float64Array(N*N).fill(2);
  const route=[[-160,0,0],[160,0,0]];
  for(const names of [["\ue000","\u{10000}"],["a\ue000","a\u{10000}"],["河\ue000","河\u{10000}"]]){
    for(const order of [names,[...names].reverse()]){
      const candidate=channelCandidate(g,d,Object.fromEntries(order.map((n)=>[n,route])),12);
      assert.equal(candidate.river,names[0]);
    }
  }
});
