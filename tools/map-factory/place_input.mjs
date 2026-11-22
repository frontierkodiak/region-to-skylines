// Target codecs only: acquisition and canonical semantics stay in place_model.
import { readFile, writeFile } from "node:fs/promises";
import { carveSurfaceWater, oceanMask, CAPTURE } from "../../inputs.js";
import { CS1, smooth, fitHeights, encode16, png16 } from "../../terrain.js";
import { waterRiskDecision } from "../../water-risk.js";
import { sourceFaithfulTerrain } from "./terrain_fidelity.mjs";

const [directory, riskPath] = process.argv.slice(2);
if (directory === "--water-risk") {
  console.log(JSON.stringify(waterRiskDecision(JSON.parse(await readFile(riskPath, "utf8")))));
} else {
  if (riskPath && !["legacy", "source-faithful-v2"].includes(riskPath)) throw new Error("Unknown terrain policy");
  const geometry = JSON.parse(await readFile(`${directory}/geometry.json`, "utf8"));
  const bytes = await readFile(`${directory}/elevation.f64`);
  const raw = new Float64Array(CS1.px ** 2);
  for (let i = 0; i < raw.length; i++) raw[i] = bytes.readDoubleLE(i * 8);
  const candidate = riskPath === "source-faithful-v2" ? sourceFaithfulTerrain(raw, geometry.sq, geometry) : null;
  const ground = candidate?.ground ?? smooth(raw, CAPTURE.smoothing);
  const sea = candidate?.fit.sea ?? oceanMask(geometry.oceans, geometry.sq);
  const carved = candidate?.carved ?? carveSurfaceWater(ground, geometry.sq, geometry);
  const fit = candidate?.fit ?? fitHeights(ground, carved.heights, { sea });
  const banks = candidate?.banks ?? fitHeights(ground, ground, { sea, verticalScale: fit.verticalScale }).game;
  const bankBytes = Buffer.alloc(banks.length * 4);
  for (let i = 0; i < banks.length; i++) bankBytes.writeFloatLE(banks[i], i * 4);
  await writeFile(`${directory}/banks.f32`, bankBytes);
  await writeFile(`${directory}/input.png`, new Uint8Array(await (await png16(encode16(fit.game), CS1.px, CS1.px)).arrayBuffer()));
  geometry.fit = { base: fit.base, verticalScale: fit.verticalScale };
  geometry.seaLevel = fit.seaLevel;
  geometry.placeInput.terrain_fit = {
    policy: candidate?.policy ?? "inputs.js CAPTURE smoothing/carveSurfaceWater; terrain.js fitHeights auto",
    real_min_m: fit.realMin, real_max_m: fit.realMax, clipped_fraction: fit.clipped,
    sea_reference: sea ? `${candidate ? "experimental shallow-coast policy" : "existing coastal policy"}: zero in source vertical datum (not a measured tide)` : null,
  };
  await writeFile(`${directory}/geometry.json`, JSON.stringify(geometry) + "\n");
}
