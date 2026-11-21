// One real full-grid case per request: never concatenate the complete cohort.
import assert from "node:assert/strict";
import {createServer} from "node:http";
import {createReadStream} from "node:fs";
import {readFile,writeFile} from "node:fs/promises";
import {resolve} from "node:path";
import {pathToFileURL} from "node:url";
const [modulePath,root,inputs,out]=process.argv.slice(2);
const {chromium,webkit}=await import(pathToFileURL(resolve(modulePath,"index.mjs")));
const rows=JSON.parse(await readFile(resolve(inputs,"cases.json"),"utf8"));
const server=createServer((req,res)=>{
  if(req.url.startsWith("/case/")){
    const row=rows[Number(req.url.slice(6))];
    if(!row)return res.writeHead(404).end();
    res.setHeader("Content-Type","application/json");
    return createReadStream(resolve(inputs,row.file)).pipe(res);
  }
  if(req.url==="/capabilities.json"){
    res.setHeader("Content-Type","application/json");return createReadStream(resolve(root,"capabilities.json")).pipe(res);
  }
  if(["/capability-model.js","/water-model.js","/start-model.js"].includes(req.url)){
    res.setHeader("Content-Type","text/javascript");return createReadStream(resolve(root,"."+req.url)).pipe(res);
  }
  res.setHeader("Content-Type","text/html");res.end("<!doctype html><title>Water boundary full-core parity</title>");
});
function compare(a,b){
  if(typeof a==="number"){assert.ok(Math.abs(a-b)<=1e-7, a+" != "+b);return;}
  if(a&&typeof a==="object"){
    assert.deepEqual(Object.keys(a).sort(),Object.keys(b).sort());
    for(const k of Object.keys(a))compare(a[k],b[k]);
  }else assert.equal(a,b);
}
await new Promise((r)=>server.listen(0,"127.0.0.1",r));
const origin="http://127.0.0.1:"+server.address().port,results=[];
try{
  for(const [name,engine] of [["chromium",chromium],["webkit",webkit]]){
    const browser=await engine.launch({headless:true});
    try{
      const page=await browser.newPage();await page.goto(origin);
      for(let i=0;i<rows.length;i++){
        const actual=await page.evaluate(async(i)=>{
          const {checkCapabilities}=await import("/capability-model.js");
          return checkCapabilities(await(await fetch("/case/"+i)).json(),await(await fetch("/capabilities.json")).json());
        },i);
        compare(rows[i].expected,actual);
        const water=actual.capabilities.water;
        assert.ok(["unknown","likely"].includes(water.level));
        for(const k of ["service","quality","flow","hookup"])assert.equal(water[k],"unknown");
        assert.match(water.native_agreement,/^unscored/);
        assert.equal(water.certificate,undefined);
        results.push({case:rows[i].case,browser:name,version:browser.version(),parity:"python_node_browser_pass",water});
      }
      console.log(name+": "+rows.length+" constructed full-core boundary/Unicode cases match Python");
    }finally{await browser.close();}
  }
}finally{await new Promise((r)=>server.close(r));await writeFile(out,JSON.stringify(results,null,2)+"\n");}
