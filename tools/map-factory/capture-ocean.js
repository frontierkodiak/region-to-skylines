// Experimental capture-only sea classification. The live terrain module is unchanged.
export function oceanPolygons(feature, tile) {
  if (feature.properties.class !== 'ocean') return [];
  const geometry = feature.toGeoJSON(tile.x, tile.y, tile.z).geometry;
  if (!['Polygon', 'MultiPolygon'].includes(geometry.type))
    throw new Error(`water/ocean has unsupported geometry ${geometry.type}`);
  return (geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates)
    .map(rings => ({ rings, properties: { ...feature.properties }, tile, featureId: feature.id ?? null }));
}

export function rasterizeOcean(polygons, sq, terrain) {
  if (!polygons.length) return null;
  const n = terrain.CS1.px, half = (n - 1) / 2, spacing = terrain.extentOf(sq) / (n - 1);
  const canvas = new OffscreenCanvas(n, n);
  const context = canvas.getContext('2d', { willReadFrequently: true });
  context.fillStyle = '#fff';
  // Match carveWater's native vertex-grid -> canvas pixel-centre transform.
  // Fill each polygon separately: holes use even-odd, overlapping tile pieces union.
  for (const polygon of polygons) {
    context.beginPath();
    for (const ring of polygon.rings) {
      ring.forEach(([lon, lat], i) => {
        const [u, v] = terrain.lonLatToSquare(sq, lon, lat);
        const x = u / spacing + half + 0.5, y = half - v / spacing + 0.5;
        i ? context.lineTo(x, y) : context.moveTo(x, y);
      });
      context.closePath();
    }
    context.fill('evenodd');
  }
  const rgba = context.getImageData(0, 0, n, n).data;
  const mask = new Uint8Array(n * n);
  let count = 0;
  for (let i = 0; i < mask.length; i++) if (rgba[4 * i + 3] >= 128) { mask[i] = 1; count++; }
  return count ? mask : null;
}
