import { test } from "node:test";
import assert from "node:assert/strict";
import { waterRiskDecision } from "../water-risk.js";
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
