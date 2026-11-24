#!/usr/bin/env node
// Local preview: serves this checkout like the deployed site, including vercel.json's
// /worldcover/ rewrite (with byte ranges), which a plain static server can't do.
// Usage: node dev.mjs [port]   (default 8000)
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";

const root = new URL(".", import.meta.url).pathname, port = Number(process.argv[2] || 8000);
const types = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".json": "application/json",
  ".md": "text/markdown", ".txt": "text/plain", ".py": "text/plain", ".png": "image/png" };
const rewrite = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/";
const canopy = "https://dataforgood-fb-data.s3.us-east-1.amazonaws.com/forests/v2/global/dinov3_global_chm_v2_ml3/chm/";
const forest = "https://zenodo.org/api/records/3939050/files/PROBAV_LC100_global_v3.0.1_2019-nrt_Forest-Type-layer_EPSG-4326.tif/content";
const tile = /^\/worldcover\/(ESA_WorldCover_10m_2021_v200_[NS]\d{2}[EW]\d{3}_Map\.tif)$/;

createServer(async (req, res) => {
  const path = decodeURIComponent(new URL(req.url, "http://x").pathname);
  const wc = path.match(tile), chm = path.match(/^\/canopy\/([0-3]{10}\.tif)$/);
  if (wc || chm || path === "/forest-types.tif") {
    try {
      const upstream = await fetch(wc ? rewrite + wc[1] : chm ? canopy + chm[1] : forest, { headers: {
        ...(req.headers.range ? { Range: req.headers.range } : {}),
        ...(!wc && !chm ? { "User-Agent": "Polli-Region-to-Skylines/vegetation (https://github.com/frontierkodiak/region-to-skylines)" } : {}),
      }, signal: AbortSignal.timeout(30000) });
      const headers = { "Cache-Control": "public, max-age=31536000, immutable" };
      for (const h of ["content-type", "content-length", "content-range", "accept-ranges"]) if (upstream.headers.get(h)) headers[h] = upstream.headers.get(h);
      const body = Buffer.from(await upstream.arrayBuffer());
      res.writeHead(upstream.status, headers);
      return res.end(body);
    } catch { return res.writeHead(502).end("Upstream raster unavailable"); }
  }
  const file = normalize(join(root, path.endsWith("/") ? path + "index.html" : path));
  if (!file.startsWith(root)) return res.writeHead(403).end();
  try {
    const body = await readFile(file);
    res.writeHead(200, { "Content-Type": types[extname(file)] ?? "application/octet-stream" }).end(body);
  } catch { res.writeHead(404).end("not found"); }
}).listen(port, () => console.log(`http://localhost:${port}/`));
