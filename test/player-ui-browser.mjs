// Blade only. node test/player-ui-browser.mjs PLAYWRIGHT_MODULE BEFORE_DIST AFTER_DIST OUT
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {resolve,extname} from 'node:path';
import {pathToFileURL} from 'node:url';
const [modulePath,beforeRoot,afterRoot,out]=process.argv.slice(2);
const {chromium,webkit}=await import(pathToFileURL(resolve(modulePath,'index.mjs')));


const serve=async root=>{
 const server=createServer(async(req,res)=>{
  try{
   const u=new URL(req.url,'http://local');
   let upstream;
   if(u.pathname.startsWith('/worldcover/'))upstream='https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/'+u.pathname.split('/').at(-1);
   if(u.pathname.startsWith('/canopy/'))upstream='https://dataforgood-fb-data.s3.us-east-1.amazonaws.com/forests/v2/global/dinov3_global_chm_v2_ml3/chm/'+u.pathname.split('/').at(-1);
   if(u.pathname==='/forest-types.tif')upstream='https://zenodo.org/api/records/3939050/files/PROBAV_LC100_global_v3.0.1_2019-nrt_Forest-Type-layer_EPSG-4326.tif/content';
   if(upstream){
    const r=await fetch(upstream,{headers:{...(req.headers.range?{Range:req.headers.range}:{}),'User-Agent':'Polli-Region-to-Skylines/vegetation'},signal:AbortSignal.timeout(30000)});
    for(const k of ['content-type','content-length','content-range','accept-ranges'])if(r.headers.get(k))res.setHeader(k,r.headers.get(k));
    res.writeHead(r.status);return res.end(Buffer.from(await r.arrayBuffer()));
   }
   const p=resolve(root,'.'+(u.pathname==='/'?'/index.html':u.pathname));
   if(!p.startsWith(root+'/'))return res.writeHead(403).end();
   res.setHeader('Content-Type',({'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.css':'text/css'})[extname(p)]??'application/octet-stream');
   res.end(await readFile(p));
  }catch{res.writeHead(404).end();}
 });
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 return [server,`http://127.0.0.1:${server.address().port}`];
};
await mkdir(out,{recursive:true});
const [before,beforeURL]=await serve(resolve(beforeRoot)),[after,afterURL]=await serve(resolve(afterRoot));
const results=[];
const places=[['asheville',-82.555,35.58],['innsbruck',11.4,47.27],['grand-canyon',-112.11,36.08]];
try{
 for(const[name,engine]of[['chromium',chromium],['webkit',webkit]]){
  const browser=await engine.launch({headless:true});
  try{
   for(const[device,width,height]of[['ipad',768,1024],['phone',390,844]]){
    const page=await browser.newPage({viewport:{width,height},hasTouch:true,ignoreHTTPSErrors:true});
    const errors=[];let vegetationCaptured=false;page.on('pageerror',e=>errors.push(e.message));
    for(const[slug,lon,lat]of places)for(const[version,base]of[['before',beforeURL],['after',afterURL]]){
     const hash=`#c=${lon},${lat}&r=0&s=1&h=auto&rivers=1&n=${slug}`;
     await page.goto('about:blank');await page.goto(base+'/'+hash,{waitUntil:'domcontentloaded'});
     await page.waitForFunction(()=>window.__regionmap?.result&&Array.from(document.querySelectorAll('[data-capability]')).every(b=>b.dataset.level!=='loading'),null,{timeout:100000});
     if(version==='after'){
      assert.equal(await page.locator('[data-capability]').count(),8);
      assert.equal(await page.locator('.capability-state,.capability-heading,.start-footprint').count(),0);
      assert.equal(await page.locator('a[href*="capabilities.html"]').count(),0);
      assert.equal(await page.locator('.stock-row[data-state=not_comparable]').count(),0);
      assert.equal(await page.locator('#stats dt').count(),4);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      const sizes=await page.locator('.capability-row button').evaluateAll(bs=>bs.map(b=>[b.clientWidth,b.clientHeight]));
      assert.ok(sizes.every(s=>s[0]===sizes[0][0]&&s[1]===sizes[0][1]));
      assert.equal((await page.request.get(base+'/capabilities.html')).status(),404);
      await page.locator('[data-capability=ship]').focus();await page.keyboard.press('Enter');
      assert.equal(await page.locator('.capability-detail').isVisible(),true);
      await page.keyboard.press('Escape');assert.equal(await page.locator('.capability-detail').isVisible(),false);
      results.push({browser:name,device,place:slug,position:await page.evaluate(()=>[__regionmap.result.sq.lon,__regionmap.result.sq.lat]),tiles:sizes,stock:await page.locator('.stock-row').count()});
     }
     if(version==='after'){
      await page.waitForFunction(()=>['available','unavailable'].includes(document.querySelector('#vegetation')?.dataset.state),null,{timeout:14000});
      if(await page.locator('#vegetation').isVisible()){
       const crop=!vegetationCaptured&&await page.locator('.genus-bar').count()>0;
       if(crop){await page.locator('#vegetation').screenshot({path:`${out}/${name}-${device}-vegetation.png`});vegetationCaptured=true;}
       results.push({browser:name,device,vegetationPlace:slug,crop,canopy:await page.locator('.vegetation-summary').innerText()});
      }
     }
     await page.locator('details').evaluateAll(nodes=>nodes.forEach(node=>{node.open=false;}));
     await page.evaluate(()=>new Promise(resolve=>{scrollTo(0,0);requestAnimationFrame(()=>requestAnimationFrame(resolve));}));
     await page.screenshot({path:`${out}/${name}-${device}-${slug}-${version}-closed.png`,fullPage:true});
     await page.locator('#howto').evaluate(el=>el.open=true);
     await page.locator('#advanced').evaluate(el=>{el.open=true;for(const d of el.querySelectorAll('details'))d.open=true;});
     if(version==='after')for(const id of['map-details','settings','credits'])await page.locator('#'+id).evaluate(el=>el.open=true);
     else await page.locator('#vegetation details').evaluate(el=>el.open=true);
     await page.evaluate(()=>new Promise(resolve=>{scrollTo(0,0);requestAnimationFrame(()=>requestAnimationFrame(resolve));}));
     await page.screenshot({path:`${out}/${name}-${device}-${slug}-${version}-open.png`,fullPage:true});
     console.log(name,device,slug,version,'closed/open pass');
    }
    assert.ok(vegetationCaptured,'at least one real canopy/genus capture is required per browser and viewport');
    await page.goto('about:blank');
    await page.goto(afterURL+'/#c=11.4,47.27&r=0&s=1&h=auto&rivers=1&n=innsbruck');
    await page.waitForFunction(()=>window.__regionmap?.result,null,{timeout:100000});
    assert.ok(await page.evaluate(()=>Math.abs(__regionmap.result.sq.lon-11.4)<.01));
    assert.equal(await page.locator('#preview-place').innerText(),'Innsbruck');
    await page.locator('#settings').evaluate(el=>el.open=true);await page.locator('#vscale').selectOption('1');
    await page.waitForFunction(()=>!document.querySelector('#clip-key').hidden,null,{timeout:10000});
    assert.ok(await page.evaluate(()=>__regionmap.result.fit.clipped>0));
    await page.locator('#previewwrap').screenshot({path:`${out}/${name}-${device}-innsbruck-clipped.png`});
    await page.locator('#fit-height').click();assert.equal(await page.locator('#vscale').inputValue(),'auto');
    await page.getByRole('button',{name:'Innsbruck',exact:true}).click();
    await page.getByRole('button',{name:'Grand Canyon',exact:true}).click();
    await page.waitForFunction(()=>Math.abs(window.__regionmap?.result?.sq.lon+112.11)<.01&&document.querySelector('.capability-row')?.getAttribute('aria-busy')==='false',null,{timeout:100000});
    assert.ok(await page.evaluate(()=>Math.abs(__regionmap.state.lon+112.11)<.01));
    assert.match(await page.locator('#preview-place').innerText(),/Grand Canyon/);
    if(device==='ipad'){
     let blocked=0;
     await page.route('**/terrarium/**',route=>{blocked++;route.abort();});
     await page.goto('about:blank');
     await page.goto(afterURL+'/#c=-82.555,35.58&r=0&s=1&h=auto&rivers=1&n=asheville');
     await page.waitForFunction(()=>!document.querySelector('#retry')?.hidden,null,{timeout:40000});
     assert.ok(blocked>0,'the elevation failure must actually be exercised');
     assert.equal(await page.locator('[data-level=loading]').count(),0);
     assert.equal(await page.locator('#previewwrap').getAttribute('aria-busy'),'false');
     assert.equal(await page.locator('#preview3d').isVisible(),false);
     await page.unroute('**/terrarium/**');await page.locator('#retry').click();
     await page.waitForFunction(()=>document.querySelector('[data-capability=ship]')?.dataset.level==='no',null,{timeout:100000});
     results.push({browser:name,terrainFailure:'Retry recovered'});
     await page.evaluate(async()=>{
      const {mountCapabilities}=await import('./capability-ui.js');
      const root=document.createElement('section');root.innerHTML='<div class="capability-row"></div><p class="capability-detail" hidden></p><div class="stock-readout"><span class="stock-basis"></span><div class="stock-list"></div></div>';document.body.append(root);
      const view=mountCapabilities(root,{capture:()=>new Promise(()=>{}),deadlineMs:25});await view.update({});
      if(root.querySelector('[data-level="loading"]'))throw new Error('Capability loading did not settle');root.remove();
      const {mountVegetation}=await import('./vegetation-ui.js');const widget=document.querySelector('#vegetation');
      const original=window.Worker;window.Worker=class{postMessage(){}terminate(){}};
      try{const v=mountVegetation(widget,{deadlineMs:25});v.update({});await new Promise(r=>setTimeout(r,50));if(!widget.hidden)throw new Error('Stalled vegetation visible');v.reset();}finally{window.Worker=original;}
     });
     results.push({browser:name,capabilityTimeout:'Unknown',vegetationTimeout:'hidden'});
    }
    assert.deepEqual(errors,[]);
    await page.close();
   }
  }finally{await browser.close();}
 }
}finally{
 await Promise.all([new Promise(r=>before.close(r)),new Promise(r=>after.close(r))]);
 await writeFile(resolve(out,'results.json'),JSON.stringify(results,null,2)+'\n');
}
