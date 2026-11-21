// Exact new-model Python/browser parity on real retained prepared exports.
// Run only on blade in the official Playwright 1.65 image.
import assert from "node:assert/strict";
import {createServer} from "node:http";
import {readFile,writeFile} from "node:fs/promises";
import {resolve} from "node:path";
import {pathToFileURL} from "node:url";
const [modulePath,root,input,out]=process.argv.slice(2);
const {chromium,webkit}=await import(pathToFileURL(resolve(modulePath,"index.mjs")));
const rows=JSON.parse(await readFile(input,"utf8"));
const model=await readFile(resolve(root,"start-model.js"));
const server=createServer((req,res)=>{
  if(req.url==="/start-model.js"){res.setHeader("Content-Type","text/javascript");return res.end(model);}
  if(req.url.startsWith("/case/")){res.setHeader("Content-Type","application/json");return res.end(JSON.stringify(rows[Number(req.url.slice(6))].data));}
  res.setHeader("Content-Type","text/html");res.end("<!doctype html><title>Prepared Start parity</title>");
});
function compare(a,b){
  if(typeof a==="number"){assert.ok(Math.abs(a-b)<=1e-7);return;}
  if(a && typeof a==="object"){
    assert.deepEqual(Object.keys(a).sort(),Object.keys(b).sort());
    for(const k of Object.keys(a))compare(a[k],b[k]);
  }else assert.equal(a,b);
}
await new Promise((r)=>server.listen(0,"127.0.0.1",r));
const origin=`http://127.0.0.1:${server.address().port}`,results=[];
try{
  for(const [name,engine] of [["chromium",chromium],["webkit",webkit]]){
    const browser=await engine.launch({headless:true});
    try{
      const page=await browser.newPage();await page.goto(origin);
      for(let i=0;i<rows.length;i++){
        const actual=await page.evaluate(async(i)=>{
          const {evaluateStart}=await import('/start-model.js');
          const data=await (await fetch('/case/'+i)).json();return evaluateStart(data);
        },i);
        compare(rows[i].expected,actual);
        results.push({browser:name,version:browser.version(),artifact_sha256:rows[i].artifact_sha256,parity:"pass",reason:actual.reason,predicted:actual.predicted,witness:actual.witness??null});
      }
      console.log(name+": "+rows.length+" real prepared exports match Python");
    }finally{await browser.close();}
  }
}finally{await new Promise((r)=>server.close(r));await writeFile(out,JSON.stringify(results,null,2)+"\n");}
