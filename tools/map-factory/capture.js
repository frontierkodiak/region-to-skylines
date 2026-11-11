// Run in a Playwright page on the app's origin. Captures the actual browser
// terrain pipeline, not a second implementation of its elevation/carving rules.
async function captureRegion(sq, { frozenGeometry = null, frozenGeometrySha256 = null } = {}) {
  const t = await import('/terrain.js');
  const { oceanPolygons, rasterizeOcean } = await import('/tools/map-factory/capture-ocean.js');
  const hash = async bytes => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)),
    b => b.toString(16).padStart(2, '0')).join('');
  if (frozenGeometry && JSON.stringify(frozenGeometry.sq) !== JSON.stringify(sq))
    throw new Error('Frozen geometry must have the identical capture square');
  const elevation = await t.sampleElevation(sq);
  const ground = t.smooth(elevation.heights, 1);
  const water = frozenGeometry ? Object.fromEntries(
    ['rivers', 'lakes', 'riverAreas', 'fragments', 'source', 'zoom', 'tiles'].map(k => [k, frozenGeometry[k]])
  ) : await t.fetchBasemapWater(sq);

  const { VectorTile } = await import('https://cdn.jsdelivr.net/npm/@mapbox/vector-tile@2.0.3/+esm');
  const { default: Pbf } = await import('https://cdn.jsdelivr.net/npm/pbf@4.0.1/+esm');
  const tj = await (await fetch('https://tiles.openfreemap.org/planet')).json();
  const z = water.zoom;
  const corners = t.corners(sq);
  const merc = ([lon, lat]) => [(lon + 180) / 360 * 2 ** z,
    (1 - Math.asinh(Math.tan(lat * Math.PI / 180)) / Math.PI) / 2 * 2 ** z];
  const tiles = corners.map(merc), roads = [], streams = [], jobs = [], oceans = [], tileEvidence = [];
  const waterClasses = {};
  for (let y = Math.floor(Math.min(...tiles.map(p => p[1]))); y <= Math.floor(Math.max(...tiles.map(p => p[1]))); y++)
    for (let x = Math.floor(Math.min(...tiles.map(p => p[0]))); x <= Math.floor(Math.max(...tiles.map(p => p[0]))); x++) jobs.push([x, y]);
  const worker = async () => {
    while (jobs.length) {
      const [x, y] = jobs.shift();
      const response = await fetch(tj.tiles[0].replace('{z}', z).replace('{x}', x).replace('{y}', y));
      const evidence = { x, y, z, status: response.status, url: response.url, waterClasses: {} };
      tileEvidence.push(evidence);
      // Missing tiles are unknown/no evidence, never an inferred ocean square.
      if (response.status === 204 || response.status === 404) continue;
      if (!response.ok) throw new Error(`transport ${z}/${x}/${y}: ${response.status}`);
      const bytes = await response.arrayBuffer();
      evidence.sha256 = await hash(bytes);
      const vt = new VectorTile(new Pbf(bytes));
      const waterLayer = vt.layers.water;
      for (let i = 0; waterLayer && i < waterLayer.length; i++) {
        const feature = waterLayer.feature(i), cls = String(feature.properties.class ?? '<missing>');
        waterClasses[cls] = (waterClasses[cls] || 0) + 1;
        evidence.waterClasses[cls] = (evidence.waterClasses[cls] || 0) + 1;
        oceans.push(...oceanPolygons(feature, { x, y, z }));
      }
      const waterways = vt.layers.waterway;
      for (let i = 0; waterways && i < waterways.length; i++) {
        const f = waterways.feature(i);
        if (f.properties.class !== 'stream') continue;
        const g = f.toGeoJSON(x, y, z).geometry;
        for (const pts of g.type === 'MultiLineString' ? g.coordinates : g.type === 'LineString' ? [g.coordinates] : [])
          streams.push({ name: f.properties.name || '', class: 'stream', pts });
      }
      const layer = vt.layers.transportation;
      for (let i = 0; layer && i < layer.length; i++) {
        const f = layer.feature(i);
        if (!['motorway', 'trunk', 'rail'].includes(f.properties.class)) continue;
        const g = f.toGeoJSON(x, y, z).geometry;
        for (const pts of g.type === 'MultiLineString' ? g.coordinates : g.type === 'LineString' ? [g.coordinates] : [])
          roads.push({ ...f.properties, pts });
      }
    }
  };
  await Promise.all(Array.from({ length: 6 }, worker));
  oceans.sort((a, b) => a.tile.y - b.tile.y || a.tile.x - b.tile.x || JSON.stringify(a.rings).localeCompare(JSON.stringify(b.rings)));
  tileEvidence.sort((a, b) => a.y - b.y || a.x - b.x);
  const sea = rasterizeOcean(oceans, sq, t);
  const carved = t.carveWater(ground, sq, water, { depth: 10, halfWidth: 40, lakeDepth: 4 });
  const fit = t.fitHeights(ground, carved.heights, { sea });
  const sources = t.waterSources(sq, water, carved, fit);
  const keptRoads = frozenGeometry ? frozenGeometry.roads : roads;
  const keptStreams = frozenGeometry ? frozenGeometry.streams : streams;
  const download = (filename, blob) => {
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = filename; a.click();
  };
  const provenance = {
    page: location.href, terrainModule: '/terrain.js',
    terrainModuleSha256: await hash(await (await fetch('/terrain.js')).arrayBuffer()),
    captureHelperSha256: await hash(await (await fetch('/tools/map-factory/capture.js')).arrayBuffer()),
    oceanHelperSha256: await hash(await (await fetch('/tools/map-factory/capture-ocean.js')).arrayBuffer()),
    elevation: { source: 'AWS Terrain Tiles / Terrarium', zoom: elevation.zoom, tiles: elevation.tiles,
      rawFloat32Sha256: await hash(elevation.heights.buffer), metresPerTilePx: elevation.metresPerTilePx },
    ocean: { source: 'OpenFreeMap / OpenStreetMap', tileJSON: 'https://tiles.openfreemap.org/planet',
      layer: 'water', acceptedClass: 'ocean', waterClasses, tiles: tileEvidence,
      polygons: oceans.length, maskCells: sea ? sea.reduce((a, b) => a + b, 0) : 0,
      classification: 'explicit ocean polygons only; separate polygon union with even-odd holes; alpha >=128',
      maskSha256: sea ? await hash(sea.buffer) : null, missingTiles: 'not classified as sea', heightThreshold: null },
    nonSea: { mode: frozenGeometry ? 'frozen vector geometry' : 'fresh vector geometry',
      frozenGeometrySha256, preservedFields: frozenGeometry ? ['sq', 'rivers', 'lakes', 'riverAreas', 'roads', 'streams'] : [],
      derivedSources: 'recomputed by unchanged terrain.waterSources after corrected sea fitting',
      previousSourcesSha256: frozenGeometry ? await hash(new TextEncoder().encode(JSON.stringify(frozenGeometry.sources))) : null,
      sourcesSha256: await hash(new TextEncoder().encode(JSON.stringify(sources))) },
    water: 'OpenFreeMap / OpenStreetMap', captured: new Date().toISOString()
  };
  const metadata = { sq, ...water, streams: keptStreams, roads: keptRoads, oceans, sources, seaLevel: fit.seaLevel,
    fit: { base: fit.base, verticalScale: fit.verticalScale },
    provenance };
  download(`${sq.slug}-geometry.json`, new Blob([JSON.stringify(metadata)]));
  download(`${sq.slug}.png`, await t.png16(t.encode16(fit.game), 1081, 1081));
  // Uncarved bank elevations in the same game frame allow stable surface
  // estimates even where overlapping area/line cuts lowered the river bed.
  const uncarved = t.fitHeights(ground, ground, { sea, verticalScale: fit.verticalScale });
  download(`${sq.slug}-banks.f32`, new Blob([uncarved.game]));
  download(`${sq.slug}-provenance.json`, new Blob([JSON.stringify(provenance, null, 2)]));
  download(`${sq.slug}-raw.f32`, new Blob([elevation.heights]));
  download(`${sq.slug}-sea.u8`, new Blob([sea || new Uint8Array(t.CS1.px ** 2)]));
  return { name: sq.name, riverPieces: water.rivers.length, roads: keptRoads.length, seaLevel: fit.seaLevel,
    waterClasses, oceanPolygons: oceans.length, oceanCells: provenance.ocean.maskCells, nonSeaMode: provenance.nonSea.mode };
}
