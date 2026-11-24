import test from 'node:test';import assert from'node:assert/strict';import{execFileSync}from'node:child_process';
import{measurePlace,placeDecisions}from'../place-rules.js';
const metrics=x=>({buildable_fraction:x,dry_fraction:x,resource_fraction:x,farm_fraction:x});
test('land and default resources show yes/maybe/no, while missing data remains maybe',()=>{
 assert.equal(placeDecisions(metrics(0)).buildable.level,'no');assert.equal(placeDecisions(metrics(0)).resources.level,'no');
 assert.equal(placeDecisions(metrics(.1)).buildable.level,'maybe');assert.equal(placeDecisions(metrics(.8)).buildable.level,'yes');
 assert.equal(placeDecisions(metrics(.8)).resources.level,'yes');assert.equal(placeDecisions(null).resources.level,'maybe');
 assert.equal(placeDecisions(metrics(.8),null,{footprint:'candidate'}).start_footprint.level,'yes');
 assert.equal(placeDecisions(metrics(.8),null,{reason:'no_footprint_in_finite_search'}).start_footprint.level,'no');
 assert.equal(placeDecisions(metrics(.8)).start_footprint.level,'maybe');
});
test('one terrain/depth input measures the same flat or submerged square',()=>{
 const ground=new Float64Array(1081**2),depth=new Float64Array(1081**2);
 assert.deepEqual(measurePlace(ground,depth),{buildable_fraction:1,dry_fraction:1,resource_fraction:.96,farm_fraction:.96,urban_screened:false});
 const city=measurePlace(ground,depth,new Array(271**2).fill(50));assert.equal(city.farm_fraction,0);assert.equal(city.resource_fraction,.96);
 depth.fill(1);assert.deepEqual(measurePlace(ground,depth),{...metrics(0),urban_screened:false});assert.equal(measurePlace([],[]),null);
});
test('Python and browser agree on all decision boundaries and missing cover',()=>{
 const rows=[null,...[0,.01,.027,.034,.052,.1,.459999,.46,.57,.9,1].map(metrics)].flatMap(m=>[null,{landcover:{status:'available',coverage_of_central_land:1},vegetation:{tree_suitability:.4}},{landcover:{status:'available',coverage_of_central_land:null}}].map(e=>[m,e,{footprint:'candidate'}]));
 const python=JSON.parse(execFileSync('python3',['-c',"import sys,json;sys.path.insert(0,'tools/map-factory');from place_rules import place_decisions;print(json.dumps([place_decisions(*r)for r in json.load(sys.stdin)]))"],{cwd:new URL('..',import.meta.url),input:JSON.stringify(rows),encoding:'utf8'}));
 assert.deepEqual(rows.map(r=>placeDecisions(...r)),python);
});
test('the live place answers preserve Water and Trees and promise authored Air',async()=>{
 const {checkCapabilities}=await import('../capability-model.js');
 const {readFileSync}=await import('node:fs');
 const ledger=JSON.parse(readFileSync(new URL('../capabilities.json',import.meta.url)));
 const base={schema:1,mode:'estimate'},old=checkCapabilities(base,ledger).capabilities;
 const current=checkCapabilities({...base,plane_entries_policy:'always',place_metrics:metrics(.8),start_footprint:{footprint:'candidate'}},ledger).capabilities;
 for(const k of ['water','trees','start'])assert.deepEqual(current[k],old[k]);
 for(const k of ['air','buildable','resources','start_footprint'])assert.equal(current[k].level,'yes');
 assert.equal(current.start_footprint.hookup,'unknown');
});

test('fitted fallback and invalid forest evidence agree with the live rules',()=>{
 assert.equal(placeDecisions(metrics(.46)).buildable.level,'yes');
 assert.equal(placeDecisions(metrics(.459999)).buildable.level,'maybe');
 for(const value of [true,false,NaN,Infinity,-Infinity,'0.5',null]){
  const evidence={landcover:{status:'available',coverage_of_central_land:1},vegetation:{tree_suitability:value}};
  assert.equal(placeDecisions(metrics(.8),evidence).resources.details.forest.level,'maybe');
 }
});
