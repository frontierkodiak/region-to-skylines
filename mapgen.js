// The ready-to-play map file, made by the reference writer itself: tools/map-factory (Python)
// runs under Pyodide, in a Web Worker on the page (mapgen-worker.js) and in Node for the CLI.
// This module is the part both share. Python does the arithmetic; this side does every
// network read, because Pyodide has no sockets: WorldCover land cover (GeoTIFF byte ranges)
// and USGS deposits. Environment-specific pieces (loadPyodide, file reads, geotiff's fromUrl,
// URLs) are passed in.

export const PYODIDE_VERSION = "314.0.7";
export const PYODIDE_CDN = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
export const GEOTIFF_ESM = "https://cdn.jsdelivr.net/npm/geotiff@2.1.3/+esm";
/** WorldCover 2021 v200 map tiles; the page reads them through its same-origin /worldcover/ rewrite. */
export const WORLDCOVER_S3 = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/";
export const worldCoverFile = (tile) => `ESA_WorldCover_10m_2021_v200_${tile}_Map.tif`;

/** tools/map-factory files the writer needs: generate.py's imports, the land cover and deposit helpers, and the template. */
export const FACTORY_FILES = [
  "generate.py", "region.py", "prepare.py", "surface_water.py", "crp.py", "template.py", "map_metadata.py",
  "paint.py", "resources.py", "landcover.py", "evidence.py", "web.py",
  "templates/native-corridors.crp", "templates/native-corridors.json",
];

/**
 * Start Python with NumPy, SciPy and Pillow and the writer's files in /factory.
 * `read(path)` returns a file of tools/map-factory as bytes.
 */
export async function startFactory({ loadPyodide, read, indexURL, status = () => {} }) {
  status("Loading Python");
  const py = await loadPyodide({ ...(indexURL ? { indexURL } : {}), stdout: () => {}, stderr: () => {} });
  await py.loadPackage(["numpy", "scipy", "pillow"], { messageCallback: () => {} });
  py.FS.mkdirTree("/factory/templates");
  await Promise.all(FACTORY_FILES.map(async (f) => py.FS.writeFile(`/factory/${f}`, await read(f))));
  py.runPython(`import sys\nif "/factory" not in sys.path: sys.path.insert(0, "/factory")\nimport warnings\nwarnings.simplefilter("ignore")`);
  return { py, web: py.pyimport("web") };
}

/** Whether an HTTP status means "no file here" (WorldCover has no tile over open ocean). */
const absent = (status) => status === 403 || status === 404;

/**
 * The square's 1728 x 1728 WorldCover grid, rows north first, written gzip-compressed to
 * `path` exactly as landcover.py writes it. `tileUrl(tile)` gives a tile's URL.
 */
export async function landCover({ py, web }, sq, { fromUrl, tileUrl, path = "/work/landcover.u8.gz", status = () => {} }) {
  status("Reading land cover");
  const square = JSON.stringify({ lon: sq.lon, lat: sq.lat, rotation: sq.rotation, scale: sq.scale });
  const tiles = JSON.parse(web.landcover_plan(square));
  const headers = [], images = new Map();
  for (const tile of tiles) {
    const url = tileUrl(tile), probe = await fetch(url, { headers: { Range: "bytes=0-0" } });
    await probe.body?.cancel(); // only the status matters; never stream a whole tile if a proxy ignores Range
    if (absent(probe.status)) { headers.push({ tile, missing: true }); continue; }
    if (!probe.ok) throw new Error(`land cover ${tile}: HTTP ${probe.status}`);
    const image = await (await fromUrl(url, { allowFullFile: false })).getImage();
    const [ox, oy] = image.getOrigin(), [rx, ry] = image.getResolution();
    images.set(tile, image);
    headers.push({ tile, transform: [rx, 0, ox, 0, ry, oy], width: image.getWidth(), height: image.getHeight() });
  }
  const windows = JSON.parse(web.landcover_windows(JSON.stringify(headers)));
  py.FS.mkdirTree("/work");
  for (let k = 0; k < headers.length; k++) {
    if (!windows[k]) continue;
    const [col, row, width, height] = windows[k];
    const [block] = await images.get(headers[k].tile).readRasters({ window: [col, row, col + width, row + height], samples: [0] });
    py.FS.writeFile("/work/landcover-block.bin", new Uint8Array(block.buffer, block.byteOffset, block.byteLength));
    web.landcover_add(JSON.stringify(headers[k]), JSON.stringify(windows[k]), "/work/landcover-block.bin");
  }
  return { path, classes: JSON.parse(web.landcover_result(path)), tiles: headers.filter((h) => !h.missing).map((h) => h.tile) };
}

/** USGS MRDS deposits near the square, written as evidence.py writes them; null if the service fails. */
export async function deposits({ py, web }, sq, { path = "/work/evidence.json", status = () => {} } = {}) {
  status("Looking up mineral deposits");
  const square = JSON.stringify({ lon: sq.lon, lat: sq.lat, rotation: sq.rotation, scale: sq.scale });
  try {
    const r = await fetch(web.evidence_url(square), { signal: AbortSignal.timeout(60000) });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    py.FS.mkdirTree("/work");
    py.FS.writeFile("/work/mrds.xml", new Uint8Array(await r.arrayBuffer()));
    return { path, count: web.evidence_parse(square, "/work/mrds.xml", path) };
  } catch {
    return null; // resources then come from the balanced defaults alone, as without evidence in the reference
  }
}

/**
 * Write the map file. `inputs` are capture's: `png` (16-bit heightmap PNG bytes), `geometry`
 * (an object, or its JSON bytes as captured), `banks` (Float32Array, rows north first); `landcover` and `evidence` are the paths
 * landCover and deposits wrote (or null). Returns {bytes, mapName, receipt}.
 */
export async function buildMap({ py, web }, { png, geometry, banks, landcover = null, evidence = null }, { status = () => {} } = {}) {
  status("Building the map");
  py.FS.mkdirTree("/work/out");
  py.FS.writeFile("/work/input.png", png);
  py.FS.writeFile("/work/geometry.json", geometry instanceof Uint8Array ? geometry : new TextEncoder().encode(JSON.stringify(geometry)));
  py.FS.writeFile("/work/banks.f32", new Uint8Array(banks.buffer, banks.byteOffset, banks.byteLength));
  const result = JSON.parse(web.build("/work", landcover, evidence));
  const bytes = py.FS.readFile(result.crp);
  return { bytes, mapName: result.map_name, receipt: result.receipt };
}

/** Remove one build's files so the next starts clean. */
export function clearWork({ py }) {
  py.runPython(`import shutil\nshutil.rmtree("/work", ignore_errors=True)`);
}
