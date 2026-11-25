// Serve a committed region capture in place of the network, so the shipped CLI can run
// end to end in the gate without touching S3 or OpenFreeMap.
//
// Used as a preload: CLI_REGION_FIXTURE=<test/fixtures/cli-region-asheville> \
//   node --import test/support/offline-region.mjs cli.mjs asheville --scale 0.5 --heightmap
//
// Every request must be in the capture; a URL the capture does not hold throws, so a run
// that starts reading a new service fails instead of quietly inventing an answer. With
// CLI_REGION_LOG set, each served URL is appended to that file so a test can prove the
// whole capture was replayed.
import { appendFileSync, readFileSync } from "node:fs";
import { join } from "node:path";

const dir = process.env.CLI_REGION_FIXTURE;
if (!dir) throw new Error("CLI_REGION_FIXTURE must point at a captured region (see test/fixtures/cli-region-asheville)");
const { requests } = JSON.parse(readFileSync(join(dir, "requests.json"), "utf8"));
const held = new Map(requests.map((r) => [r.url, r]));
const log = process.env.CLI_REGION_LOG;

globalThis.fetch = async (input) => {
  const url = typeof input === "string" ? input : input.url;
  const record = held.get(url);
  if (!record) throw new Error(`region capture ${dir} has no response for ${url}`);
  if (log) appendFileSync(log, `${url}\n`);
  return new Response(readFileSync(join(dir, "tiles", record.file)), {
    status: record.status,
    headers: record.type ? { "content-type": record.type } : {},
  });
};
