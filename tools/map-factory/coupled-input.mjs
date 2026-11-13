// ONE experimental source/profile-guided input, using the production carver.
import {readFile,writeFile} from 'node:fs/promises';
import {carveWater} from '../../terrain.js';
const [source,tracePath,output]=process.argv.slice(2);
const geometry=JSON.parse(await readFile(`${source}/geometry.json`));
const trace=JSON.parse(await readFile(tracePath));
const selected=new Set(trace.deferred_source_features.map(f=>JSON.stringify(f)));
const bytes=await readFile(`${source}/banks.f32`);
const banks=new Float32Array(bytes.buffer,bytes.byteOffset,bytes.byteLength/4);
const visible=geometry.rivers.filter(r=>r.brunnel!=='tunnel');
const retained=visible.filter(r=>!selected.has(JSON.stringify(r)));
if(visible.length-retained.length!==selected.size)throw Error('Deferred source identity mismatch');
const options={depth:10*geometry.fit.verticalScale,halfWidth:40,lakeDepth:4*geometry.fit.verticalScale};
const before=carveWater(banks,geometry.sq,{...geometry,rivers:visible},options).heights;
const after=carveWater(banks,geometry.sq,{...geometry,rivers:retained},options).heights;
const delta=new Float32Array(banks.length);
for(let i=0;i<delta.length;i++){if(after[i]<before[i]-.0001)throw Error('Source deferral deepened browser incision');delta[i]=Math.max(0,after[i]-before[i]);}
await writeFile(output,new Uint8Array(delta.buffer));
const i=313*1081+465;
console.log(JSON.stringify({deferred_pieces:selected.size,control_node:{uncarved:banks[i],browser_carve:before[i],deferred_carve:after[i]},production_options:options}));
