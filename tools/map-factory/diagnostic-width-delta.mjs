// Diagnostic only: compare browser incision half-widths on the SAME game-fitted DEM.
// The production carver and its 40 m minimum are never edited.
import { readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { carveWater } from "../../terrain.js";

const [source, output] = process.argv.slice(2);
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const original = await readFile(new URL("../../terrain.js", import.meta.url), "utf8");
const needle = "const w = Math.max(halfWidth, 2.5 * sp);";
if (original.split(needle).length !== 2) throw Error("carver changed; inspect the diagnostic before reuse");
let code = original.replace(needle, "const w = halfWidth;");
for (const name of ["@mapbox/vector-tile", "pbf"])
  code = code.replace(`from "${name}"`, `from ${JSON.stringify(import.meta.resolve(name))}`);
const variant = await import(`data:text/javascript;base64,${Buffer.from(code).toString("base64")}`);
const bankBytes = await readFile(`${source}/banks.f32`);
const banks = new Float32Array(bankBytes.buffer, bankBytes.byteOffset, bankBytes.byteLength / 4);
const geometryBytes = await readFile(`${source}/geometry.json`);
const geometry = JSON.parse(geometryBytes);
const water = { ...geometry, rivers: geometry.rivers.filter((r) => r.brunnel !== "tunnel") };
const scale = geometry.fit.verticalScale;
const options = { depth: 10 * scale, halfWidth: 40, lakeDepth: 4 * scale };
const forty = carveWater(banks, geometry.sq, water, options).heights;
const fortyCopy = variant.carveWater(banks, geometry.sq, water, options).heights;
const narrow = variant.carveWater(banks, geometry.sq, water, { ...options, halfWidth: 24 }).heights;
const delta = new Float32Array(banks.length);
for (let i = 0; i < banks.length; i++) {
  if (forty[i] !== fortyCopy[i]) throw Error(`40 m copy differs at ${i}`);
  if (narrow[i] < forty[i] - 0.00002) throw Error(`narrow incision lowered terrain at ${i}`);
  delta[i] = Math.max(0, narrow[i] - forty[i]);
}
await writeFile(`${output}/width-delta.f32`, new Uint8Array(delta.buffer));
await writeFile(`${output}/width-recipe.json`, JSON.stringify({
  diagnostic_only: true, half_widths_m: [40, 24],
  method: "positive browser-carve delta on the same game-fitted uncarved DEM; retain later preparation",
  production_source_sha256: sha(original), diagnostic_source_sha256: sha(code),
  replaced_expression: needle, banks_sha256: sha(bankBytes), geometry_sha256: sha(geometryBytes),
  depth_game_m: options.depth, lake_depth_game_m: options.lakeDepth,
  forty_copy_byte_identical: true, delta_sha256: sha(new Uint8Array(delta.buffer)),
}, null, 2) + "\n");
