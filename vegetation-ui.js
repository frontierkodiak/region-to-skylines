const percent=v=>Number.isFinite(v)?`${Math.round(v*100)}%`:'?';
export const genusText=c=>c?.genus?.slice(0,3).map(g=>`${g.genus} ${percent(g.share)}`).join(' · ')||'';
export function paintCanopy(canvas,report){
 const n=report.grid.size;canvas.width=n;canvas.height=n;const context=canvas.getContext('2d'),pixels=context.createImageData(n,n);
 for(let i=0;i<report.cells.length;i++){const v=report.cells[i].canopy.cover;pixels.data.set(Number.isFinite(v)?[232-v*183,238-v*125,229-v*170,255]:[180,179,176,255],i*4);}
 context.putImageData(pixels,0,0);
}
export function mountVegetation(root,{deadlineMs=12000}={}){
 const readout=root.querySelector('.vegetation-summary'),genera=root.querySelector('.vegetation-genera'),canvas=root.querySelector('canvas');
 let worker=null,sequence=0,timer;
 function reset(){clearTimeout(timer);worker?.terminate();worker=null;sequence++;root.hidden=true;root.dataset.state='loading';readout.textContent='';genera.replaceChildren();canvas.getContext('2d').clearRect(0,0,canvas.width,canvas.height);}
 function unavailable(){reset();root.dataset.state='unavailable';}
 function render(value){
  clearTimeout(timer);worker?.terminate();worker=null;const canopy=value.summary.canopy;
  if(canopy.status!=='available'||!Number.isFinite(canopy.cover))return unavailable();
  const height=canopy.height_m?.p50;readout.textContent=`${percent(canopy.cover)} canopy${Number.isFinite(height)?` · ${Math.round(height)} m`:''}`;readout.title='Canopy cover and median height';
  for(const g of value.summary.composition?.genus?.slice(0,3)??[]){
   const row=document.createElement('div');row.className='genus-bar';const name=document.createElement('span');name.textContent=g.genus;const share=document.createElement('span');share.textContent=percent(g.share);const track=document.createElement('i');track.style.setProperty('--share',`${Math.max(0,Math.min(100,g.share*100))}%`);row.append(name,share,track);genera.append(row);
  }
  if(!genera.childElementCount)genera.textContent='Genera unavailable';
  paintCanopy(canvas,value);canvas.title=`${percent(canopy.coverage.fraction)} imagery coverage`;root.dataset.state='available';root.hidden=false;
 }
 function update(square){reset();const current=sequence;timer=setTimeout(()=>{if(current===sequence)unavailable();},deadlineMs);try{worker=new Worker(new URL('./vegetation-worker.js',import.meta.url),{type:'module'});worker.onmessage=({data})=>{if(current===sequence)data.report?render(data.report):unavailable();};worker.onerror=()=>{if(current===sequence)unavailable();};worker.postMessage(square);}catch{unavailable();}}
 return{reset,update,unavailable,render};
}
