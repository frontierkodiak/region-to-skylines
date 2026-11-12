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
const rewrite = JSON.parse(await readFile(join(root, "vercel.json"), "utf8")).rewrites[0].destination.replace(/:tile$/, "");
const tile = /^\/worldcover\/(ESA_WorldCover_10m_2021_v200_[NS]\d{2}[EW]\d{3}_Map\.tif)$/;

createServer(async (req, res) => {
  const path = decodeURIComponent(new URL(req.url, "http://x").pathname);
  const wc = path.match(tile);
  if (wc) {
    const upstream = await fetch(rewrite + wc[1], { headers: req.headers.range ? { Range: req.headers.range } : {} });
    const headers = { "Cache-Control": "public, max-age=31536000, immutable" };
    for (const h of ["content-type", "content-length", "content-range", "accept-ranges"]) if (upstream.headers.get(h)) headers[h] = upstream.headers.get(h);
    res.writeHead(upstream.status, headers);
    return res.end(Buffer.from(await upstream.arrayBuffer()));
  }
  const file = normalize(join(root, path.endsWith("/") ? path + "index.html" : path));
  if (!file.startsWith(root)) return res.writeHead(403).end();
  try {
    const body = await readFile(file);
    res.writeHead(200, { "Content-Type": types[extname(file)] ?? "application/octet-stream" }).end(body);
  } catch { res.writeHead(404).end("not found"); }
}).listen(port, () => console.log(`http://localhost:${port}/`));
