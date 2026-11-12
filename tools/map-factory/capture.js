// Run in a Playwright page on the app's origin. Captures the actual browser
// terrain pipeline, not a second implementation of its elevation/carving rules.
async function captureRegion(sq) {
  const t = await import('/terrain.js');
  const elevation = await t.sampleElevation(sq);
  const sea = t.seaMask(elevation.heights);
  const ground = t.smooth(elevation.heights, 1);
  const water = await t.fetchBasemapWater(sq);
  const carved = t.carveWater(ground, sq, water, { depth: 10, halfWidth: 40, lakeDepth: 4 });
  const fit = t.fitHeights(ground, carved.heights, { sea });
  const sources = t.waterSources(sq, water, carved, fit);

  const { VectorTile } = await import('https://cdn.jsdelivr.net/npm/@mapbox/vector-tile@2.0.3/+esm');
  const { default: Pbf } = await import('https://cdn.jsdelivr.net/npm/pbf@4.0.1/+esm');
  const tj = await (await fetch('https://tiles.openfreemap.org/planet')).json();
  const z = water.zoom;
  const corners = t.corners(sq);
  const merc = ([lon, lat]) => [(lon + 180) / 360 * 2 ** z,
    (1 - Math.asinh(Math.tan(lat * Math.PI / 180)) / Math.PI) / 2 * 2 ** z];
  const tiles = corners.map(merc), roads = [], streams = [], jobs = [];
  for (let y = Math.floor(Math.min(...tiles.map(p => p[1]))); y <= Math.floor(Math.max(...tiles.map(p => p[1]))); y++)
    for (let x = Math.floor(Math.min(...tiles.map(p => p[0]))); x <= Math.floor(Math.max(...tiles.map(p => p[0]))); x++) jobs.push([x, y]);
  const worker = async () => {
    while (jobs.length) {
      const [x, y] = jobs.shift();
      const response = await fetch(tj.tiles[0].replace('{z}', z).replace('{x}', x).replace('{y}', y));
      if (response.status === 204 || response.status === 404) continue;
      if (!response.ok) throw new Error(`transport ${z}/${x}/${y}: ${response.status}`);
      const vt = new VectorTile(new Pbf(await response.arrayBuffer()));
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
  const download = (filename, blob) => {
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = filename; a.click();
  };
  const metadata = { sq, ...water, streams, roads, sources, seaLevel: fit.seaLevel,
    fit: { base: fit.base, verticalScale: fit.verticalScale },
    provenance: { page: location.href, terrainModule: '/terrain.js', elevation: 'AWS Terrain Tiles', water: 'OpenFreeMap / OpenStreetMap', captured: new Date().toISOString() } };
  download(`${sq.slug}-geometry.json`, new Blob([JSON.stringify(metadata)]));
  download(`${sq.slug}.png`, await t.png16(t.encode16(fit.game), 1081, 1081));
  // Uncarved bank elevations in the same game frame allow stable surface
  // estimates even where overlapping area/line cuts lowered the river bed.
  const uncarved = t.fitHeights(ground, ground, { sea, verticalScale: fit.verticalScale });
  download(`${sq.slug}-banks.f32`, new Blob([uncarved.game]));
  return { name: sq.name, riverPieces: water.rivers.length, roads: roads.length, seaLevel: fit.seaLevel };
}
