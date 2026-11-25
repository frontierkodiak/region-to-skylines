// Record a region's network responses, so test/cli-run.test.mjs can replay the shipped
// CLI offline. Run only when re-capturing the fixture; the recorded bytes are committed.
//
//   RECORD_DIR=/tmp/region node --import test/support/record-region.mjs \
//     cli.mjs asheville --scale 0.5 --heightmap --out /tmp/map --json
//
// The bytes come from the real services the CLI uses (AWS Terrain Tiles, OpenFreeMap),
// and requests.json keeps each URL with its status and content type.
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { join } from "node:path";

const dir = process.env.RECORD_DIR;
if (!dir) throw new Error("RECORD_DIR must name where the capture is written");
mkdirSync(dir, { recursive: true });
const indexPath = join(dir, "requests.json");
const index = new Map(existsSync(indexPath)
  ? JSON.parse(readFileSync(indexPath, "utf8")).requests.map((r) => [r.url, r])
  : []);
const original = globalThis.fetch;

globalThis.fetch = async (input, init) => {
  const url = typeof input === "string" ? input : input.url;
  const response = await original(input, init);
  const body = new Uint8Array(await response.clone().arrayBuffer());
  const file = `${createHash("sha256").update(url).digest("hex").slice(0, 16)}.bin`;
  writeFileSync(join(dir, file), body);
  index.set(url, {
    url,
    file,
    status: response.status,
    type: response.headers.get("content-type") ?? "",
  });
  writeFileSync(indexPath, `${JSON.stringify({ requests: [...index.values()] }, null, 1)}\n`);
  return response;
};
