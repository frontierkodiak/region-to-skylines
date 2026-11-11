// Browser tests use the real canvas rasterizer and inherited terrain fit.
async function testOceanCapture() {
  const { oceanPolygons, rasterizeOcean } = await import('/tools/map-factory/capture-ocean.js');
  const t = await import('/terrain.js');
  const frame = { CS1: { px: 9 }, extentOf: () => 8, lonLatToSquare: (_, x, y) => [x, y] };
  const outer = [[-1, -5], [5, -5], [5, 5], [-1, 5], [-1, -5]];
  const hole = [[1, -1], [3, -1], [3, 1], [1, 1], [1, -1]];
  const polygon = { rings: [outer, hole] }, raw = new Float32Array(81).fill(2);
  const sea = rasterizeOcean([polygon], {}, frame);
  const fit = t.fitHeights(raw, raw, { sea });
  const checks = [];
  const assert = (condition, name) => { if (!condition) throw new Error(name); checks.push(name); };
  assert(sea[4 * 9] === 0 && fit.game[4 * 9] > fit.seaLevel, 'edge-connected coastal ground <=3m remains land');
  assert(sea[4 * 9 + 8] === 1 && fit.game[4 * 9 + 8] < fit.seaLevel, 'explicit ocean becomes sea');
  assert(sea[4 * 9 + 6] === 0 && fit.game[4 * 9 + 6] > fit.seaLevel, 'polygon island hole remains dry');
  assert(rasterizeOcean([], {}, frame) === null, 'no ocean evidence returns null inland');
  assert(t.fitHeights(raw, raw, { sea: null }).seaLevel === null, 'inland inherited fit has null sea level');
  assert(Array.from(rasterizeOcean([polygon, polygon], {}, frame)).join() === Array.from(sea).join(),
    'overlapping tile polygons union rather than cancel');
  const outside = { rings: [[[20, 20], [30, 20], [30, 30], [20, 30], [20, 20]]] };
  assert(rasterizeOcean([outside], {}, frame) === null, 'out-of-frame ocean does not enable sea fitting');
  assert(oceanPolygons({ properties: { class: 'lake' } }, {}).length === 0, 'lake class is not inferred ocean');
  const feature = { properties: { class: 'ocean' }, id: 7,
    toGeoJSON: () => ({ geometry: { type: 'MultiPolygon', coordinates: [[outer, hole], [outer]] } }) };
  const decoded = oceanPolygons(feature, { x: 1, y: 2, z: 3 });
  assert(decoded.length === 2 && decoded[0].rings.length === 2 && decoded[0].featureId === 7,
    'MultiPolygon decoding preserves holes, feature identity and explicit ocean class');
  const sq = { lon: 20, lat: 35, rotation: 90, scale: 1 };
  const rotatedFrame = { ...t, CS1: { px: 9 } };
  const rotated = { rings: [outer, hole].map(r => r.map(([u, v]) => t.squareToLonLat(sq, u * 2160, v * 2160))) };
  const rotatedMask = rasterizeOcean([rotated], sq, rotatedFrame);
  assert(rotatedMask[4 * 9] === 0 && rotatedMask[4 * 9 + 8] === 1 && rotatedMask[4 * 9 + 6] === 0,
    'clockwise rotated geographic frame preserves ocean, dry coast and island hole');
  let rejected = false;
  try { oceanPolygons({ properties: { class: 'ocean' }, toGeoJSON: () => ({ geometry: { type: 'LineString' } }) }, {}); }
  catch { rejected = true; }
  assert(rejected, 'explicit ocean with unsupported geometry fails instead of silently classifying');
  return { passed: true, checks };
}
