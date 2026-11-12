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
  const mask = new Uint8Array(n * n);
  let count = 0;
  // Match carveWater's native vertex-grid -> canvas pixel-centre transform.
  // Fill each polygon separately: holes use even-odd, overlapping tile pieces union.
  for (const polygon of polygons) {
    context.clearRect(0, 0, n, n);
    context.beginPath();
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const ring of polygon.rings) {
      ring.forEach(([lon, lat], i) => {
        const [u, v] = terrain.lonLatToSquare(sq, lon, lat);
        const x = u / spacing + half + 0.5, y = half - v / spacing + 0.5;
        minX = Math.min(minX, x); maxX = Math.max(maxX, x);
        minY = Math.min(minY, y); maxY = Math.max(maxY, y);
        i ? context.lineTo(x, y) : context.moveTo(x, y);
      });
      context.closePath();
    }
    context.fill('evenodd');
    const x0 = Math.max(0, Math.floor(minX)), x1 = Math.min(n, Math.ceil(maxX));
    const y0 = Math.max(0, Math.floor(minY)), y1 = Math.min(n, Math.ceil(maxY));
    if (x1 <= x0 || y1 <= y0) continue;
    const width = x1 - x0, rgba = context.getImageData(x0, y0, width, y1 - y0).data;
    // Threshold each tile polygon before union, so duplicated antialiased
    // coast pixels cannot accumulate opacity and swallow extra land cells.
    for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) {
      const i = y * n + x, pixel = (y - y0) * width + x - x0;
      if (!mask[i] && rgba[4 * pixel + 3] >= 128) { mask[i] = 1; count++; }
    }
  }
  return count ? mask : null;
}
