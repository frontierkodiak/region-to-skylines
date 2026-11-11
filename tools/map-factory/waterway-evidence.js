// Capture-only metadata recovery. Exact clipping is supplied by an isolated
// served copy of terrain.js exporting its private clipLine; never edit product code.
export function assertPinnedTile(tile, status, sha256) {
  if (status!==200 || tile.status!==status || !/^[0-9a-f]{64}$/.test(tile.sha256) || tile.sha256!==sha256)
    throw Error(`pinned tile status/SHA changed ${tile.url}`);
}

export async function inspectWaterways(tiles, clipLine) {
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
      assertPinnedTile(tile,response.status,sha256);
      evidence.push({x,y,z,url:tile.url,sha256,status:response.status});
      const layer = new VectorTile(new Pbf(bytes)).layers.waterway;
      for (let i=0; layer && i<layer.length; i++) {
        const f=layer.feature(i), cls=f.properties.class;
        if (!['river','stream'].includes(cls)) continue;
        const name=f.properties.name || f.properties['name:latin'] || f.properties.name_en || '';
        const provenance={tile:{x,y,z,url:tile.url,sha256},feature_index:i,feature_id:f.id ?? null,properties:{...f.properties}};
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

export function matchFrozen(frozen, pieces) {
  const byKey=new Map();
  for (const p of pieces) {
    const key=JSON.stringify([p.class,p.pts]);
    if (!byKey.has(key)) byKey.set(key,[]);
    byKey.get(key).push(p);
  }
  const matched=[],unknown=[],ambiguous=[],used=new Set();
  for (const field of ['rivers','streams']) for (let index=0;index<(frozen[field] || []).length;index++) {
    const f=frozen[field][index], cls=field==='rivers'?'river':'stream';
    const found=byKey.get(JSON.stringify([cls,f.pts])) || [];
    if (!found.length) unknown.push({field,index,name:f.name,pts:f.pts});
    else if (found.length!==1 || found[0].name!==f.name) ambiguous.push({field,index,name:f.name,candidates:found});
    else if (used.has(found[0])) ambiguous.push({field,index,name:f.name,candidates:found});
    else { used.add(found[0]); matched.push({field,index,original:f,evidence:found[0]}); }
  }
  return {matched,unknown,ambiguous};
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
          original_field:field,original_index:index}};
      if (brunnel==='tunnel') undergroundWaterways.push({...annotated,class:e.class,exclusionReason:'explicit waterway.brunnel=tunnel'});
      else result[field].push(annotated);
    });
  }
  result.undergroundWaterways=undergroundWaterways;
  result.surfaceWaterPolicy={schema:1,policy:'exclude explicit waterway.brunnel=tunnel only',
    originalGeometrySha256,waterwayEvidenceSha256,tiles:inspection.tiles,
    matching:'exact class + coordinate arrays, verified name; unique source feature per frozen piece',
    intermittentPolicy:'preserve only; no exclusion',
    originalCounts:{rivers:frozen.rivers.length,streams:frozen.streams.length},
    retainedCounts:{rivers:result.rivers.length,streams:result.streams.length},
    excludedCounts:{rivers:undergroundWaterways.filter(f=>f.sourceFeature.original_field==='rivers').length,
      streams:undergroundWaterways.filter(f=>f.sourceFeature.original_field==='streams').length},
    excludedField:'undergroundWaterways',
    caveat:'Underground connectivity/portals and Python hydrology routing are not implemented by this capture policy'};
  return result;
}
