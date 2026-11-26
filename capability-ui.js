import {captureEstimate} from "./capability-inputs.js";
import {checkCapabilities,stockComparison} from "./capability-model.js";
import {labels,states,pct,stockLabels,stockReason,capabilityReason} from "./interface-copy.js";

const ICONS = {
  road: "M6 3 3 21M18 3l3 18M12 3v4m0 3v4m0 3v4",
  rail: "M7 3h10v14H7zM7 7h10M7 13h10M9 17l-4 4m10-4 4 4M7 20h10",
  ship: "M5 12V6h6v6m0-4h6v4M3 12l3 7h12l3-7-9-3-9 3m0 9q3-2 6 0t6 0 6 0",
  air: "m3 12 7-2 1-7h2l1 7 7 2v2l-7-1-1 6 3 2H8l3-2-1-6-7 1z",
  water: "M12 3S5 11 5 15a7 7 0 0 0 14 0c0-4-7-12-7-12z",
  buildable: "m3 10 9-7 9 7M6 8v13h12V8M10 21v-7h4v7",
  resources: "m4 20 5-15 7-2 5 9-8 9-9-1zM9 5l4 16m3-18-3 18M4 20l17-8",
  trees: "m12 3-6 8h3l-5 7h6v3h4v-3h6l-5-7h3z",
};
const marks={yes:'✓',no:'×',maybe:'~',promised:'✓',likely:'~',not_possible_here:'×',unknown:'?',loading:''};
export {planDetail,placeDetail,waterDetail,footprintDetail} from './interface-copy.js';

export function mountCapabilities(root,{onFootprint=()=>{},capture=captureEstimate,deadlineMs=35000}={}) {
  const row=root.querySelector('.capability-row'),detail=root.querySelector('.capability-detail');
  const stockList=root.querySelector('.stock-list'),stockNote=root.querySelector('.stock-basis');
  let controller=null,sequence=0,catalog=null,active=null;
  const buttons=new Map();
  const hide=()=>{active=null;detail.hidden=true;detail.textContent='';};
  const show=button=>{active=button;detail.textContent=button.title;detail.hidden=false;};
  for(const[id,label]of Object.entries(labels)){
    const button=document.createElement('button');button.type='button';button.dataset.capability=id;
    button.innerHTML=`<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${ICONS[id]}"/></svg><span class="capability-mark" aria-hidden="true"></span>`;
    button.addEventListener('pointerenter',()=>show(button));button.addEventListener('focus',()=>show(button));
    button.addEventListener('click',()=>show(button));
    button.setAttribute('aria-label',label);buttons.set(id,button);row.append(button);
  }
  root.addEventListener('pointerleave',()=>{if(!root.contains(document.activeElement))hide();});
  root.addEventListener('focusout',event=>{if(!root.contains(event.relatedTarget))hide();});
  root.addEventListener('keydown',event=>{if(event.key==='Escape')hide();});
  function reset(){
    controller?.abort();sequence++;onFootprint(null);hide();
    row.setAttribute('aria-busy','true');stockList.replaceChildren();root.querySelector('.stock-readout').hidden=true;
    for(const[id,button]of buttons){button.dataset.level='loading';button.title=`${labels[id]} loading`;button.setAttribute('aria-label',button.title);button.querySelector('.capability-mark').textContent='';}
  }
  function unavailable(){
    controller?.abort();sequence++;onFootprint(null);hide();row.setAttribute('aria-busy','false');
    for(const[id,button]of buttons){button.dataset.level='unknown';button.title=`${labels[id]}: Data unavailable.`;button.setAttribute('aria-label',button.title);button.querySelector('.capability-mark').textContent='?';}
    stockList.replaceChildren();root.querySelector('.stock-readout').hidden=true;
  }
  const format=(v,unit)=>unit==='fraction'?pct(v):`${Number(v.toFixed(1))}${unit==='%'?'%':' m'}`;
  function renderStock(stock){
    stockList.replaceChildren();
    const comparison=stockComparison(stock?.measures,catalog.stock_reference,stock?.comparability);
    stockNote.textContent='Middle half';
    for(const[id,label]of Object.entries(stockLabels)){
      const value=comparison[id];if(!value?.comparable||value.value==null)continue;
      const el=document.createElement('button');el.type='button';el.className='stock-row';el.dataset.metric=id;
      const ceiling=Math.max(value.value,value.p75*1.4,1),lo=value.p25/ceiling*100,hi=value.p75/ceiling*100,dot=value.value/ceiling*100;
      el.innerHTML='<span class="stock-name"></span><span class="stock-track"><i class="stock-range"></i><i class="stock-dot"></i></span><span class="stock-value"></span>';
      el.querySelector('.stock-name').textContent=label;el.querySelector('.stock-value').textContent=format(value.value,value.unit);
      el.querySelector('.stock-range').style.cssText=`left:${lo}%;width:${hi-lo}%`;
      el.querySelector('.stock-dot').style.left=`${Math.min(98,Math.max(2,dot))}%`;
      el.title=stockReason(label,format(value.value,value.unit),format(value.p25,value.unit),format(value.p75,value.unit));
      el.setAttribute('aria-label',el.title);el.addEventListener('click',()=>show(el));el.addEventListener('pointerenter',()=>show(el));el.addEventListener('focus',()=>show(el));stockList.append(el);
    }
    root.querySelector('.stock-readout').hidden=!stockList.childElementCount;
  }
  async function update(square){
    controller?.abort();controller=new AbortController();const ctl=controller,current=++sequence;
    let timer;
    try{
      const timeout=new Promise((_,reject)=>{timer=setTimeout(()=>{reject(new Error('Capture deadline'));ctl.abort();},deadlineMs);});
      const load=catalog?Promise.resolve(catalog):fetch('./capabilities.json',{signal:ctl.signal}).then(r=>{if(!r.ok)throw new Error('Rules unavailable');return r.json();});
      const [data,captured]=await Promise.race([Promise.all([load,capture(square,{signal:ctl.signal})]),timeout]);
      if(current!==sequence||ctl.signal.aborted)return;
      catalog=data;const report=checkCapabilities(captured.input,catalog);row.setAttribute('aria-busy','false');
      onFootprint(captured.input.start_footprint,square);
      for(const[id,button]of buttons){
        const result=report.capabilities[id];button.dataset.level=result.level;
        button.querySelector('.capability-mark').textContent=marks[result.level]??'?';
        button.title=`${labels[id]}: ${capabilityReason(id,result)}`;button.setAttribute('aria-label',`${labels[id]}, ${states[result.level]}. ${capabilityReason(id,result)}`);
      }
      renderStock(captured.stock);if(active)show(active);
    }catch{if(current===sequence)unavailable();}
    finally{clearTimeout(timer);}
  }
  row.setAttribute('aria-busy','true');
  for(const button of buttons.values())button.dataset.level='loading';
  root.querySelector('.stock-readout').hidden=true;
  return{reset,update,unavailable};
}
