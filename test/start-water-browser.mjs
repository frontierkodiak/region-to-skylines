// Saved real evidence, served-byte identity and responsive/keyboard checks only.
// Run on blade in mcr.microsoft.com/playwright:v1.65.0-noble.
import assert from "node:assert/strict";
import {createHash} from "node:crypto";
import {createServer} from "node:http";
import {readFile, writeFile, mkdir} from "node:fs/promises";
import {resolve, extname} from "node:path";
import {pathToFileURL} from "node:url";
const [modulePath,directory,output]=process.argv.slice(2);
const {chromium,webkit}=await import(pathToFileURL(resolve(modulePath,"index.mjs")));
const root=resolve(directory),out=resolve(output);
await mkdir(out,{recursive:true});
const server=createServer(async(req,res)=>{
  const path=resolve(root,"."+new URL(req.url,"http://local").pathname);
  if(!path.startsWith(root+"/"))return res.writeHead(403).end();
  try {
    res.setHeader("Content-Type",({".html":"text/html",".js":"text/javascript",".json":"application/json",".css":"text/css",".png":"image/png"})[extname(path)]??"application/octet-stream");
    res.end(await readFile(path));
  }catch{res.writeHead(404).end();}
});
await new Promise((r)=>server.listen(0,"127.0.0.1",r));
const origin=`http://127.0.0.1:${server.address().port}`;
const results={scope:"Saved real evidence and HTTP bytes; no new native/game/player run, no live Boston capture. Mutation tests are separate constructed tests.",browsers:[]};
try {
  for(const [name,engine] of [["chromium",chromium],["webkit",webkit]]) {
    const browser=await engine.launch({headless:true});
    try {
      const page=await browser.newPage({viewport:{width:1440,height:1000}});
      const errors=[];page.on("pageerror",(e)=>errors.push(String(e)));
      await page.goto(origin+"/capabilities.html#start");
      const start=page.locator('[data-witness-study][data-capability="start"]');
      const water=page.locator('[data-witness-study][data-capability="water"]');
      for(const [study,expected] of [[start,["Fitting","2/3","Regional holdout","NOT ESTIMABLE (n=0)"]],[water,["Fitting","3/3","Regional holdout","1/2","130/843"]]]) {
        for(const text of expected)assert.ok((await study.textContent()).includes(text),text);
        await study.locator("summary").filter({hasText:/^All 11 /}).click();
        assert.equal(await study.locator("[data-witness-rows] tbody tr").count(),11);
      }
      const hk=water.locator("[data-witness-rows] tbody tr").filter({hasText:"hong-kong-northeast"});
      assert.match(await hk.textContent(),/Yes \/ No/);
      const gc=water.locator("[data-witness-rows] tbody tr").filter({hasText:"grand-canyon-northeast"});
      assert.match(await gc.textContent(),/Unknown \/ Unknown/);
      const first=start.locator("[data-first-hour] summary").first();
      await first.focus();await page.keyboard.press("Enter");
      assert.equal(await first.evaluate((e)=>e.parentElement.open),true);
      assert.equal(await start.locator("[data-first-hour-pairs] tbody tr").count(),11);
      assert.match(await start.textContent(),/6.038/);assert.match(await start.textContent(),/peak 540/);
      await start.locator("h3").evaluate((e)=>e.scrollIntoView({block:"start"}));
      await page.screenshot({path:resolve(out,name+"-desktop.png")});
      const ledgerResponse=await page.request.get(origin+"/capabilities.json");assert.equal(ledgerResponse.status(),200);
      const ledger=await ledgerResponse.json(),study=ledger.witness_studies["pl1078-start-water-v2"],httpFiles=[];
      for(const ref of [...study.provenance.files,study.provenance.manifest]) {
        const response=await page.request.get(origin+"/"+ref.file);assert.equal(response.status(),200,ref.file);
        const digest=createHash("sha256").update(await response.body()).digest("hex");
        assert.equal(digest,ref.sha256,ref.file);httpFiles.push({file:ref.file,sha256:digest});
      }
      // Check every local href, not just native evidence (historical/build links included).
      const localHrefs=await page.locator('a[href]').evaluateAll((links)=>[...new Set(links.map((a)=>a.getAttribute("href")).filter((h)=>!h.startsWith("#")&&!/^https?:/.test(h)))]);
      for(const href of localHrefs) {
        const response=await page.request.get(origin+"/"+(href==="./"?"index.html":href));
        assert.equal(response.status(),200,href);
      }
      const checked=await page.evaluate(async()=>{
        const {checkCapabilities}=await import("/capability-model.js");
        return checkCapabilities({schema:1,mode:"estimate"},await(await fetch("/capabilities.json")).json());
      });
      for(const id of ["start","water"])assert.equal(checked.capabilities[id].level,"unknown");
      await page.evaluate(()=>document.activeElement?.blur());
      for(const width of [390,320]) {
        await page.setViewportSize({width,height:844});
        for(const study of [start,water]) {
          const capability=study===start?"start":"water";
          // A fresh fragment navigation prevents WebKit restoring the old focused
          // disclosure's scroll position while capturing a different capability.
          await page.goto(origin+"/capabilities.html#"+capability);
          await study.locator("h3").evaluate((e)=>e.scrollIntoView({block:"start"}));
          await page.waitForFunction((id)=>{
            const el=document.querySelector('[data-witness-study][data-capability="'+id+'"] h3');
            const y=el.getBoundingClientRect().top;
            return y>=-1&&y<200;
          },capability);
          assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),"page overflow");
          const container=study.locator(".ledger-table").first();
          assert.equal(await container.evaluate((e)=>getComputedStyle(e).overflowX),"auto");
          assert.ok(await container.evaluate((e)=>e.getBoundingClientRect().right<=innerWidth));
          if(await container.evaluate((e)=>e.scrollWidth>e.clientWidth)) {
            await container.evaluate((e)=>{e.scrollLeft=e.scrollWidth;});
            assert.ok(await container.evaluate((e)=>e.scrollLeft>0));
          }
          await container.evaluate((e)=>{e.scrollLeft=0;});
          await page.screenshot({path:resolve(out,name+"-"+capability+"-"+width+".png")});
          const captureTop=await study.locator("h3").evaluate((e)=>e.getBoundingClientRect().top);
          assert.ok(captureTop>=-1&&captureTop<500,"capture kept intended section heading in view");
        }
      }
      assert.deepEqual(errors,[]);
      results.browsers.push({name,widths:[1440,390,320],keyboard:true,rows_per_capability:11,first_hour_pairs:11,httpFiles,local_hrefs:localHrefs.length,page_errors:errors});
    }finally{await browser.close();}
  }
  await writeFile(resolve(out,"results.json"),JSON.stringify(results,null,2)+"\n");
  console.log(JSON.stringify(results.browsers.map(({httpFiles,...r})=>({...r,served_evidence_files:httpFiles.length}))));
}finally{await new Promise((r)=>server.close(r));}
