// Builds the ready-to-play map file off the page's main thread: Pyodide (Python on
// WebAssembly) runs tools/map-factory, the reference writer, on the inputs the page captured
// (inputs.js). Land cover comes through the site's same-origin /worldcover/ rewrite.
import { startFactory, landCover, deposits, buildMap, clearWork, PYODIDE_CDN, GEOTIFF_ESM, worldCoverFile } from "./mapgen.js";

const base = new URL(".", self.location.href);
let factory = null;

self.onmessage = async ({ data: { id, sq, inputs } }) => {
  const status = (text) => self.postMessage({ id, status: text });
  try {
    if (!factory) {
      const { loadPyodide } = await import(`${PYODIDE_CDN}pyodide.mjs`);
      const read = async (f) => {
        const r = await fetch(new URL(`tools/map-factory/${f}`, base));
        if (!r.ok) throw new Error(`${f}: HTTP ${r.status}`);
        return new Uint8Array(await r.arrayBuffer());
      };
      factory = await startFactory({ loadPyodide, read, indexURL: PYODIDE_CDN, status });
    }
    const { fromUrl } = await import(GEOTIFF_ESM);
    clearWork(factory);
    const cover = await landCover(factory, sq, { fromUrl, tileUrl: (tile) => new URL(`worldcover/${worldCoverFile(tile)}`, base).href, status });
    const found = await deposits(factory, sq, { status });
    const map = await buildMap(factory, { ...inputs, landcover: cover.path, evidence: found?.path ?? null }, { status });
    let memory = null;
    try { memory = factory.py._module.HEAP8.length; } catch {}
    const prep = map.receipt.preparation ?? {};
    self.postMessage({ id, done: true, bytes: map.bytes, mapName: map.mapName, memory,
      summary: { tiles: cover.tiles, deposits: found?.count ?? null, wet_cells: prep.wet_cells, starter_reservoir: !!prep.starter_reservoir } },
    [map.bytes.buffer]);
    clearWork(factory);
  } catch (err) {
    self.postMessage({ id, error: String(err?.message ?? err) });
  }
};
