import test from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { connectionRules, edgeConnection, waterWidth, CONNECTION_RULES } from "../connection-rules.js";

const grid = (n, predicate, spacing = 64, sea = false) => ({ size: n, spacing_m: spacing,
  water: Array.from({ length: n * n }, (_, i) => +predicate(Math.floor(i / n), i % n)),
  sea: Array.from({ length: n * n }, (_, i) => +(sea && predicate(Math.floor(i / n), i % n))) });
const input = (water, roads = []) => ({ extent_m: (water.size - 1) * water.spacing_m, water_grid: water, roads });

test("only an eligible line crossing the boundary is yes", () => {
  assert.equal(edgeConnection([{class:"motorway",pts:[[-600,0],[600,0]]}],"road",500,32).level,"yes");
  assert.equal(edgeConnection([{class:"motorway",pts:[[0,0],[100,0]]}],"road",500,32).level,"no");
  assert.equal(edgeConnection([{class:"trunk",pts:[[0,0],[480,0]]}],"road",500,32).level,"maybe");
  assert.equal(edgeConnection([{class:"residential",pts:[[-600,0],[600,0]]}],"road",500,32).level,"no");
  assert.equal(edgeConnection([{class:"rail",service:"yard",pts:[[-600,0],[600,0]]}],"rail",500,32).level,"no");
  assert.equal(edgeConnection([{class:"motorway",pts:[[-500,-600],[-500,600]]}],"road",500,32).level,"no");
  assert.equal(edgeConnection([{class:"rail",pts:[[-600,0],[600,0]]}],"rail",500,32).level,"yes");
});

test("ship uses a continuous water corridor, not wet share or a place name", () => {
  assert.equal(connectionRules(input(grid(17, (r) => r === 8))).ship.level,"no");
  assert.equal(connectionRules(input(grid(17, (r) => r >= 5 && r <= 11))).ship.level,"yes");
  assert.equal(connectionRules(input(grid(17, (r,c) => r>2 && r<14 && c>2 && c<14))).ship.level,"no");
  assert.equal(connectionRules(input(grid(17, () => true,64,true))).ship.level,"yes");
  assert.equal(waterWidth(grid(17,(r,c)=>r>=5&&r<=11&&c!==8)),0,"two disconnected half corridors do not join");
  const near = connectionRules(input(grid(17, (r) => r>=5&&r<=11,48)), {...CONNECTION_RULES,ship_width_m:336,margin_m:48});
  assert.equal(near.ship.level,"maybe");
});

test("Python and browser run the same geometry rules and threshold margins", () => {
  const cases = [];
  for (let width=0;width<11;width++) for (const sea of [false,true]) {
    cases.push(input(grid(25,(r)=>Math.abs(r-12)<width,64,sea),[{class:"trunk",pts:[[-900,0],[900,0]]}]));
  }
  const script = "import sys,json;sys.path.insert(0,'tools/map-factory');from connection_rules import check;print(json.dumps([check(x) for x in json.load(sys.stdin)]))";
  const python = JSON.parse(execFileSync("python3",["-c",script],{input:JSON.stringify(cases),cwd:new URL("..",import.meta.url),encoding:"utf8"}));
  assert.deepEqual(cases.map(x=>connectionRules(x)),python);
});

test("the live core uses mapped geometry without changing Water or old inputs", async () => {
  const {checkCapabilities}=await import('../capability-model.js');
  const {readFileSync}=await import('node:fs');
  const ledger=JSON.parse(readFileSync(new URL('../capabilities.json',import.meta.url)));
  const data={schema:1,mode:'estimate',connection_geometry:input(grid(17,r=>r>=5&&r<=11))};
  const report=checkCapabilities(data,ledger), expected=connectionRules(data.connection_geometry);
  for(const key of ['road','rail','ship','air'])assert.deepEqual(report.capabilities[key],expected[key]);
  assert.equal(report.capabilities.water.level,'unknown');
  assert.equal(checkCapabilities({schema:1,mode:'estimate'},ledger).capabilities.air.level,'unknown');
});

test("the published stock agreement is the arithmetic of the retained scalar rows", async () => {
  const {readFileSync}=await import('node:fs');
  const fit=JSON.parse(readFileSync(new URL('../tools/map-factory/survey/connection-fit.json',import.meta.url)));
  assert.equal(fit.rows.length,104);assert.deepEqual(fit.rules,CONNECTION_RULES);
  for(const kind of ['road','rail','ship','air']){
    const rows=fit.rows.filter(r=>!['road','rail'].includes(kind)||kind in r);
    const agree=rows.filter(r=>(kind==='ship'?r.width_m>=fit.rules.ship_width_m:kind==='air'?true:r[kind])===r.labels[kind]).length;
    assert.equal(fit.stock_agreement[kind].agree,agree);assert.equal(fit.stock_agreement[kind].total,rows.length);
  }
});
