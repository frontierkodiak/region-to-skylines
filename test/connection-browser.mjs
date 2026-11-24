// Actual open-data captures, never injected capability results. Blade only.
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {resolve,extname} from 'node:path';
import {pathToFileURL} from 'node:url';
const [modulePath,root,out]=process.argv.slice(2);
const {chromium,webkit}=await import(pathToFileURL(resolve(modulePath,'index.mjs')));
await mkdir(out,{recursive:true});
const server=createServer(async(req,res)=>{
 const u=new URL(req.url,'http://local');
 try {
  if(u.pathname.startsWith('/worldcover/')){
   const r=await fetch('https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/'+u.pathname.split('/').at(-1),{headers:req.headers.range?{Range:req.headers.range}:{}});
   for(const k of ['content-type','content-length','content-range','accept-ranges'])if(r.headers.get(k))res.setHeader(k,r.headers.get(k));
   res.writeHead(r.status);return res.end(Buffer.from(await r.arrayBuffer()));
  }
  const p=resolve(root,'.'+(u.pathname==='/'?'/index.html':u.pathname));
  if(!p.startsWith(resolve(root)+'/'))return res.writeHead(403).end();
  res.setHeader('Content-Type',({'.html':'text/html','.js':'text/javascript','.json':'application/json','.css':'text/css'})[extname(p)]??'application/octet-stream');
  res.end(await readFile(p));
 }catch{res.writeHead(404).end();}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const origin=`http://127.0.0.1:${server.address().port}`,results=[];
const places=[['asheville',-82.555,35.58,'no'],['boston',-71.057,42.36,'yes'],['rio',-43.205,-22.94,'yes'],['grand-canyon',-112.11,36.08,'no']];
try{
 for(const [name,engine]of [['chromium',chromium],['webkit',webkit]]){
  const browser=await engine.launch({headless:true});
  try{
   const page=await browser.newPage({viewport:{width:1280,height:950},ignoreHTTPSErrors:true});
   page.on('pageerror',e=>console.error(name,e.message));
   const recapture=async action=>{const pending=page.waitForFunction(()=>document.querySelector('[data-capability=ship]')?.dataset.level==='loading',{},{timeout:20000});await action();await pending;await page.waitForFunction(()=>document.querySelector('[data-capability=ship]')?.dataset.level==='yes',{},{timeout:180000});};
   for(const [slug,lon,lat,ship]of places){
    await page.goto('about:blank');
    await page.goto(origin+`/#c=${lon},${lat}&r=0&s=1&h=auto&rivers=1&n=${slug}`,{waitUntil:'domcontentloaded'});
    await page.waitForFunction(()=>['yes','no','maybe'].includes(document.querySelector('[data-capability=ship]')?.dataset.level),{},{timeout:180000});
    const row=await page.locator('[data-capability]').evaluateAll(es=>Object.fromEntries(es.map(e=>[e.dataset.capability,e.dataset.level])));
    assert.equal(row.ship,ship,slug);if(slug==='asheville')assert.equal(row.road,'yes');
    assert.equal(Object.keys(row).length,8);assert.equal(row.air,'yes');
    for(const k of ['buildable','resources'])assert.ok(['yes','no','maybe'].includes(row[k]));
    assert.match(await page.locator('[data-capability=air]').getAttribute('title'),/writes two plane entries/);
    const footprint=await page.locator('.start-footprint').innerText();assert.match(footprint,/(Yes|Maybe|No).*384.*Hookup: Unknown/);
    await page.locator('[data-capability=resources]').focus();await page.keyboard.press('Enter');
    for(const k of ['Ore:','Oil:','Fertile:','Forest:'])assert.match(await page.locator('.capability-detail').innerText(),new RegExp(k));
    await page.locator('#capabilities').scrollIntoViewIfNeeded();
    await page.screenshot({path:resolve(out,`${name}-${slug}.png`),fullPage:true});
    results.push({browser:name,place:slug,row,footprint});console.log(name,slug,JSON.stringify(row));
   }
   await page.setViewportSize({width:390,height:844});
   await page.goto('about:blank');
   await page.goto(origin+'/#c=-71.057,42.36&r=0&s=1&h=auto&rivers=1&n=boston');
   await page.waitForFunction(()=>document.querySelector('[data-capability=ship]')?.dataset.level==='yes',{},{timeout:180000});
   await page.locator('#capabilities').scrollIntoViewIfNeeded();
   await page.screenshot({path:resolve(out,`${name}-boston-390.png`),fullPage:true});
   const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);assert.equal(overflow,false);
   await page.locator('[data-capability=resources]').focus();await page.keyboard.press('Enter');
   await page.screenshot({path:resolve(out,`${name}-boston-detail-390.png`),fullPage:true});
   await recapture(()=>page.setViewportSize({width:320,height:740}));
   await page.locator('[data-capability=resources]').click();
   assert.match(await page.locator('.capability-detail').innerText(),/Fertile: Yes/);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   await page.screenshot({path:resolve(out,`${name}-boston-detail-320.png`),fullPage:true});
   await recapture(()=>page.setViewportSize({width:1280,height:950}));
   await page.locator('#map').scrollIntoViewIfNeeded();const box=await page.locator('#map').boundingBox();
   await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await recapture(async()=>{await page.mouse.down();await page.mouse.move(box.x+box.width/2+35,box.y+box.height/2+15,{steps:6});await page.mouse.up();});
   await page.waitForFunction(()=>document.querySelector('[data-capability=ship]')?.dataset.level==='yes',{},{timeout:180000});
   results.push({browser:name,pan:'Boston ship yes'});
  }finally{await browser.close();}
 }
}finally{await new Promise(r=>server.close(r));await writeFile(resolve(out,'results.json'),JSON.stringify(results,null,2)+'\n');}
