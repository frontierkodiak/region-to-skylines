// Capture-only metadata recovery. Exact clipping is supplied by an isolated
// served copy of terrain.js exporting its private clipLine; never edit product code.
export function assertPinnedTile(tile, status, sha256) {
  if (status!==200 || tile.status!==status || !/^[0-9a-f]{64}$/.test(tile.sha256) || tile.sha256!==sha256)
    throw Error(`pinned tile status/SHA changed ${tile.url}`);
}

export const SNAPSHOT = '20261101_080013_pt';
export function snapshotTiles(frozen, recorded, {bbox,tileRange}) {
  const z=frozen.zoom, range=tileRange(bbox(frozen.sq,500),z), streams=tileRange(bbox(frozen.sq,0),z), byKey=new Map();
  for (const t of recorded) {
    if (t.url!==`https://tiles.openfreemap.org/planet/${SNAPSHOT}/${t.z}/${t.x}/${t.y}.pbf` || t.z!==z)
      throw Error('recorded tile is not the exact requested snapshot/zoom');
    const key=`${t.z}/${t.x}/${t.y}`;
    if(byKey.has(key)) throw Error('duplicate recorded tile identity');
    byKey.set(key,t);
  }
  for(let y=range.y0;y<=range.y1;y++) for(let x=range.x0;x<=range.x1;x++) {
    const key=`${z}/${x}/${y}`;
    if(!byKey.has(key)) byKey.set(key,{x,y,z,status:200,url:`https://tiles.openfreemap.org/planet/${SNAPSHOT}/${z}/${x}/${y}.pbf`});
  }
  return [...byKey.values()].map(t=>({...t,streamEligible:t.x>=streams.x0 && t.x<=streams.x1 && t.y>=streams.y0 && t.y<=streams.y1}));
}

export async function inspectWaterways(tiles, clipLine, {firstObserved=false}={}) {
  const keys=tiles.map(t=>`${t.z}/${t.x}/${t.y}`);
  if (new Set(keys).size!==keys.length) throw Error('duplicate pinned tile identity');
  const { VectorTile } = await import('https://cdn.jsdelivr.net/npm/@mapbox/vector-tile@2.0.3/+esm');
  const { default: Pbf } = await import('https://cdn.jsdelivr.net/npm/pbf@4.0.1/+esm');
  const hash = async b => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', b)), x => x.toString(16).padStart(2,'0')).join('');
  const r5 = v => Math.round(v * 1e5) / 1e5;
  const jobs = [...tiles], evidence = [], pieces = [];
  const worker = async () => {
    while (jobs.length) {
      const tile = jobs.shift(), {x,y,z} = tile;
      const response = await fetch(tile.url);
      if (response.status !== tile.status) throw Error(`pinned tile status changed ${tile.url}`);
      if (response.status !== 200) throw Error(`no complete waterway evidence ${tile.url}`);
      const bytes = await response.arrayBuffer(), sha256 = await hash(bytes);
      let assurance='recorded_sha256_verified';
      if(tile.sha256!==undefined) assertPinnedTile(tile,response.status,sha256);
      else {
        if(!firstObserved || tile.url!==`https://tiles.openfreemap.org/planet/${SNAPSHOT}/${z}/${x}/${y}.pbf`)
          throw Error('unrecorded tile requires explicit exact-snapshot first observation');
        assurance='first_observed_exact_snapshot';
      }
      evidence.push({x,y,z,url:tile.url,sha256,status:response.status,assurance,streamEligible:tile.streamEligible});
      const layer = new VectorTile(new Pbf(bytes)).layers.waterway;
      for (let i=0; layer && i<layer.length; i++) {
        const f=layer.feature(i), cls=f.properties.class;
        if (!['river','stream'].includes(cls) || (cls==='stream' && tile.streamEligible===false)) continue;
        const name=f.properties.name || f.properties['name:latin'] || f.properties.name_en || '';
        const provenance={tile:{x,y,z,url:tile.url,sha256,assurance},feature_index:i,feature_id:f.id ?? null,properties:{...f.properties}};
        if (cls === 'river') {
          const E=layer.extent;
          const ll=([px,py]) => [r5((x+px/E)/2**z*360-180),r5(360/Math.PI*Math.atan(Math.exp(Math.PI*(1-2*(y+py/E)/2**z)))-90)];
          f.loadGeometry().forEach((line,line_index) => clipLine(line.map(p=>[p.x,p.y]),E).forEach((pts,piece_index) =>
            pieces.push({name,class:cls,pts:pts.map(ll),...provenance,line_index,piece_index})));
        } else {
          const g=f.toGeoJSON(x,y,z).geometry;
          const lines=g.type==='MultiLineString'?g.coordinates:g.type==='LineString'?[g.coordinates]:[];
          lines.forEach((pts,line_index)=>pieces.push({name:f.properties.name || '',class:cls,pts,...provenance,line_index,piece_index:0}));
        }
      }
    }
  };
  await Promise.all(Array.from({length:6},worker));
  pieces.sort((a,b)=>a.tile.y-b.tile.y || a.tile.x-b.tile.x || a.feature_index-b.feature_index || a.line_index-b.line_index || a.piece_index-b.piece_index);
  evidence.sort((a,b)=>a.y-b.y || a.x-b.x);
  return {tiles:evidence,pieces};
}

const canonical = value => JSON.stringify(value && typeof value==='object' && !Array.isArray(value)
  ? Object.fromEntries(Object.keys(value).sort().map(k=>[k,JSON.parse(canonical(value[k]))]))
  : Array.isArray(value) ? value.map(v=>JSON.parse(canonical(v))) : value);

export function matchFrozen(frozen, pieces) {
  const byKey=new Map(), originals=new Map();
  const keyOf=p=>JSON.stringify([p.class,p.pts]);
  for (const p of pieces) {
    const key=keyOf(p);
    if (!byKey.has(key)) byKey.set(key,[]);
    byKey.get(key).push(p);
  }
  for (const field of ['rivers','streams']) for(let index=0;index<(frozen[field] || []).length;index++) {
    const original=frozen[field][index],cls=field==='rivers'?'river':'stream',key=keyOf({...original,class:cls});
    if(!originals.has(key)) originals.set(key,[]);
    originals.get(key).push({field,index,original});
  }
  const matched=[],unknown=[],ambiguous=[],provenanceGroups=[];
  for(const [key,occurrences] of originals) {
    const found=byKey.get(key) || [];
    if(!found.length) { unknown.push(...occurrences); continue; }
    const first=found[0];
    const equivalent=found.every(p=>p.feature_id===first.feature_id && p.feature_id!==null && p.class===first.class
      && p.name===first.name && canonical(p.properties)===canonical(first.properties));
    if(found.length!==occurrences.length || occurrences.some(o=>o.original.name!==first.name)
      || (found.length>1 && !equivalent)) {
      ambiguous.push(...occurrences.map(o=>({...o,candidates:found})));continue;
    }
    let evidence=first;
    if(found.length>1) {
      const provenanceGroup={group_index:provenanceGroups.length,source_count:found.length,frozen_count:occurrences.length,
        members:found.map(p=>({tile:p.tile,feature_index:p.feature_index,line_index:p.line_index,piece_index:p.piece_index})),
        original_occurrences:occurrences.map(o=>({field:o.field,index:o.index})),
        equivalence:'same VT feature_id,class,name,all properties,exact coordinates; equal multiplicity; no tile assignment'};
      provenanceGroups.push(provenanceGroup);
      evidence={name:first.name,class:first.class,pts:first.pts,feature_id:first.feature_id,
        properties:first.properties,tile:null,feature_index:null,line_index:null,piece_index:null,provenanceGroup};
    }
    matched.push(...occurrences.map(o=>({...o,evidence})));
  }
  matched.sort((a,b)=>a.field.localeCompare(b.field)||a.index-b.index);
  return {matched,unknown,ambiguous,provenanceGroups};
}

export function surfaceGeometry(frozen, inspection, originalGeometrySha256, waterwayEvidenceSha256) {
  if (![originalGeometrySha256,waterwayEvidenceSha256].every(h=>typeof h==='string' && /^[0-9a-f]{64}$/.test(h)))
    throw Error('missing source/evidence SHA binding');
  const match=matchFrozen(frozen,inspection.pieces);
  if (match.unknown.length || match.ambiguous.length) throw Error('unknown/ambiguous frozen waterway match');
  const byIndex=new Map(match.matched.map(m=>[`${m.field}/${m.index}`,m]));
  const undergroundWaterways=[], result={...frozen};
  for (const field of ['rivers','streams']) {
    result[field]=[];
    frozen[field].forEach((original,index)=>{
      const e=byIndex.get(`${field}/${index}`).evidence, brunnel=e.properties.brunnel;
      if (brunnel!==undefined && !['','bridge','tunnel'].includes(brunnel)) throw Error('unknown waterway brunnel value');
      const annotated={...original,brunnel:brunnel ?? null,intermittent:e.properties.intermittent ?? null,
        sourceFeature:{tile:e.tile,feature_id:e.feature_id,feature_index:e.feature_index,
          line_index:e.line_index,piece_index:e.piece_index,properties:e.properties,
          original_field:field,original_index:index,
          ...(e.provenanceGroup ? {provenanceGroup:{...e.provenanceGroup,evidence_sha256:waterwayEvidenceSha256}} : {})}};
      if (brunnel==='tunnel') undergroundWaterways.push({...annotated,class:e.class,exclusionReason:'explicit waterway.brunnel=tunnel'});
      else result[field].push(annotated);
    });
  }
  result.undergroundWaterways=undergroundWaterways;
  result.surfaceWaterPolicy={schema:1,policy:'exclude explicit waterway.brunnel=tunnel only',
    originalGeometrySha256,waterwayEvidenceSha256,tiles:inspection.tiles,
    matching:'exact class + coordinate arrays + name; unique source OR exact metadata-equivalent buffer multiset with equal multiplicity',
    provenanceGroupCount:match.provenanceGroups.length,
    groupedFrozenPieces:match.provenanceGroups.reduce((n,g)=>n+g.frozen_count,0),
    intermittentPolicy:'preserve only; no exclusion',
    originalCounts:{rivers:frozen.rivers.length,streams:frozen.streams.length},
    retainedCounts:{rivers:result.rivers.length,streams:result.streams.length},
    excludedCounts:{rivers:undergroundWaterways.filter(f=>f.sourceFeature.original_field==='rivers').length,
      streams:undergroundWaterways.filter(f=>f.sourceFeature.original_field==='streams').length},
    excludedField:'undergroundWaterways',
    caveat:'Underground connectivity/portals and Python hydrology routing are not implemented by this capture policy'};
  return result;
}
