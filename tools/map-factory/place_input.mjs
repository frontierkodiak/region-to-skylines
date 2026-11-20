// Target codecs only: acquisition and canonical semantics stay in place_model.
import { readFile, writeFile } from "node:fs/promises";
import { carveSurfaceWater, oceanMask, CAPTURE } from "../../inputs.js";
import { CS1, smooth, fitHeights, encode16, png16 } from "../../terrain.js";
import { waterRiskDecision } from "../../water-risk.js";

const [directory, riskPath] = process.argv.slice(2);
if (directory === "--water-risk") {
  console.log(JSON.stringify(waterRiskDecision(JSON.parse(await readFile(riskPath, "utf8")))));
} else {
  const geometry = JSON.parse(await readFile(`${directory}/geometry.json`, "utf8"));
  const bytes = await readFile(`${directory}/elevation.f64`);
  const raw = new Float64Array(CS1.px ** 2);
  for (let i = 0; i < raw.length; i++) raw[i] = bytes.readDoubleLE(i * 8);
  const ground = smooth(raw, CAPTURE.smoothing);
  const sea = oceanMask(geometry.oceans, geometry.sq);
  const carved = carveSurfaceWater(ground, geometry.sq, geometry);
  const fit = fitHeights(ground, carved.heights, { sea });
  const banks = fitHeights(ground, ground, { sea, verticalScale: fit.verticalScale });
  const bankBytes = Buffer.alloc(banks.game.length * 4);
  for (let i = 0; i < banks.game.length; i++) bankBytes.writeFloatLE(banks.game[i], i * 4);
  await writeFile(`${directory}/banks.f32`, bankBytes);
  await writeFile(`${directory}/input.png`, new Uint8Array(await (await png16(encode16(fit.game), CS1.px, CS1.px)).arrayBuffer()));
  geometry.fit = { base: fit.base, verticalScale: fit.verticalScale };
  geometry.seaLevel = fit.seaLevel;
  geometry.placeInput.terrain_fit = {
    policy: "inputs.js CAPTURE smoothing/carveSurfaceWater; terrain.js fitHeights auto",
    real_min_m: fit.realMin, real_max_m: fit.realMax, clipped_fraction: fit.clipped,
    sea_reference: sea ? "existing coastal policy: zero in source vertical datum (not a measured tide)" : null,
  };
  await writeFile(`${directory}/geometry.json`, JSON.stringify(geometry) + "\n");
}
