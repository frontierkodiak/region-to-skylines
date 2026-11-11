// Runs inside pixel-asheville (see export_current.mjs): plan every building, write the
// chunks that hold the pilot buildings, and return those buildings' triangles.
import { loadData, heightSampler, roadIndex, footprintGrid, chunkKey } from "./src/world.js";
import { planBuildings, pointInRing, roadDistance, plan900 } from "./src/buildings.js";
import { LANDMARK_SKIP } from "./src/landmarks.js";

window.exportBuildings = async (targets) => {
  const ids = targets.map((t) => t.id);
  const data = await loadData();
  const heightAt = heightSampler(data);
  const clearance = footprintGrid(data.buildings);
  const opts = {
    skip: LANDMARK_SKIP,
    isFree: (x, z) => clearance(x, z, 1.5) >= 1,
    isRad: (x, z) => pointInRing(x, z, data.rad.strip),
    roadDist: roadDistance(data.roads),
  };
  const plan = planBuildings(data.buildings, roadIndex(data), chunkKey, heightAt, opts);
  const F = Object.fromEntries(data.buildings.fields.map((f, i) => [f, i]));
  const want = new Set(ids), meshes = new Map(), buildings = [];
  const meshOf = (key) => { if (!meshes.has(key)) meshes.set(key, plan.build(key)); return meshes.get(key); };
  const byId = new Map();
  for (const it of plan.items) {
    const id = it.parent ?? it.id;
    if (!want.has(id)) continue;
    if (!byId.has(id)) byId.set(id, []);
    byId.get(id).push(it);
  }
  // pixel-asheville swaps some county outlines for OpenStreetMap ones (other ids): take
  // whatever the generator draws with its centre inside the county outline.
  for (const t of targets) {
    if (byId.has(t.id)) continue;
    const inside = plan.items.filter((it) => pointInRing(it.cx, it.cz, t.ring));
    if (inside.length) byId.set(t.id, inside);
  }
  for (const id of ids) {
    const items = byId.get(id) ?? [];
    const tri = [], ramp = [], how = new Set();
    let row = null;
    for (const it of items) {
      const m = meshOf(it.key);
      row = it.row;
      let span = it.span && it.span[1] > it.span[0] && !(it.how === "block" || it.how === "skipped") ? it.span : plan900.blockSpans?.get(it.id);
      how.add(it.span && it.how?.startsWith("kit") ? it.how : span ? "block" : it.drawn === null ? "dropped" : "none");
      if (!span) continue;
      for (let i = span[0]; i < span[1]; i++) tri.push(Math.round(m.p[i] * 1000) / 1000);
      for (let i = span[0] / 3; i < span[1] / 3; i += 3) ramp.push(m.c[i]);
    }
    buildings.push({
      id, swapped: items.some((it) => (it.parent ?? it.id) !== id), how: [...how].join("+") || (LANDMARK_SKIP.has(id) ? "landmark" : "absent"), parts: items.length, tri, ramp,
      height: row ? row[F.height] : null, estimated: row ? row[F.estimated] : null, ground: row ? row[F.ground] : null,
      wall: row ? row[F.wall] ?? null : null, roof_rgb: row ? row[F.roof_rgb] ?? null : null, kind: row ? row[F.kind] ?? null : null,
    });
  }
  return { buildings, stats: plan.stats };
};
