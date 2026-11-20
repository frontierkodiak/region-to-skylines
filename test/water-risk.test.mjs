import { test } from "node:test";
import assert from "node:assert/strict";
import { waterRiskDecision } from "../water-risk.js";
import { readFile } from "node:fs/promises";
import { loadFixtureContract } from "./fixture-contract.mjs";
const base = () => ({ schema: 1, status: "lower", reasons: [], features: {}, outside_calibration: [], calibration: { squares: 5 },
  risks: { flood: { level: "not_flagged" }, drying: { level: "not_flagged" } } });

test("missing, inconsistent or declined water checks cannot silently download", () => {
  for (const risk of [null, {}, { ...base(), risks: {} }, { ...base(), outside_calibration: ["new-terrain"] },
    { ...base(), reasons: ["a risk exists"] }, { ...base(), status: "declined", reasons: ["missing input"] },
    { ...base(), risks: { flood: { level: "flagged" }, drying: { level: "not_flagged" } } }])
    assert.equal(waterRiskDecision(risk).action, "decline");
});
test("a flagged square requires review; a complete unflagged square can download", () => {
  assert.equal(waterRiskDecision(base()).action, "download");
  const flagged = { ...base(), status: "warning", reasons: ["Low coastal shores need verification."] };
  assert.equal(waterRiskDecision(flagged).action, "review");
  assert.deepEqual(waterRiskDecision(flagged).reasons, flagged.reasons);
});

test("omitted-stream notes require review without being called drying predictions", () => {
  const note = "Mapped stream left uncarved.";
  const risk = { ...base(), status: "warning", notes: [note], reasons: [note] };
  assert.equal(waterRiskDecision(risk).action, "review");
  assert.deepEqual(waterRiskDecision(risk).reasons, [note]);
  assert.equal(risk.risks.drying.level, "not_flagged");
});

test("the predecessor active pointer archive is enforced byte-for-byte", async () => {
  const root = new URL("../tools/map-factory/", import.meta.url);
  const read = async (name) => {
    const bytes = await readFile(new URL(name, root));
    return name.endsWith("pl912-water-risk-v1/previous-active.json") ? Buffer.concat([bytes, Buffer.from(" ")]) : bytes;
  };
  await assert.rejects(loadFixtureContract(read, (name) => readFile(new URL("../" + name, import.meta.url))), /archived active pointer changed/);
});
