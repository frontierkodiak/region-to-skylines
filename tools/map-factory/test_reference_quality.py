"""Reference selection cannot look at generated-terrain success or omit points."""

import json
import unittest

import numpy as np

from reference_quality import POLICY, POLICY_PATH, alarms, assess, registration


class ReferenceQualityTests(unittest.TestCase):
    def setUp(self):
        row, col = np.mgrid[:128, :128]
        self.water = ((row < 24) & (col < 80)) | ((row < 93) & (col < 21))
        land = (
            2
            + row * 0.01
            + col * 0.02
            + 100 * np.exp(-(((row - 83) / 13) ** 2) - ((col - 93) / 20) ** 2)
            + 40 * np.exp(-(((row - 29) / 8) ** 2) - ((col - 103) / 7) ** 2)
        )
        self.source = np.where(self.water, -1.0, land)
        self.tx = np.where(col < 44, 5, 6)
        self.ty = np.full_like(row, 9)

    def assess(self, frozen, water=None, game=None):
        return assess(
            self.source,
            frozen,
            self.source,
            self.tx,
            self.ty,
            self.water if water is None else water,
            8.0,
            game=self.source if game is None else game,
            terracing=0,
        )

    def test_shared_real_cliff_is_not_a_reference_seam(self):
        cliff = self.source + (self.tx == 5) * 20
        result = alarms(cliff, cliff, cliff, self.tx, self.ty)
        self.assertFalse(result["alarm"])

    def test_tile_seam_replacement_requires_independent_registration(self):
        frozen = self.source + (self.tx == 5) * 10
        result = self.assess(frozen)
        self.assertEqual(result["state"], "reference_defect")
        self.assertEqual(result["selected_reference"], "canonical_source")
        self.assertTrue(result["accepted"])
        unknown = self.assess(frozen, water=np.zeros_like(self.water))
        self.assertEqual(unknown["state"], "unresolved")
        self.assertEqual(unknown["selected_reference"], "frozen_z13")
        self.assertFalse(unknown["accepted"])

    def test_uniform_vertical_datum_offset_is_not_a_defect_alarm(self):
        result = self.assess(self.source + 8)
        self.assertFalse(result["defect_evidence"]["alarm"])
        self.assertEqual(result["selected_reference"], "frozen_z13")

    def test_reference_choice_is_independent_of_export_success(self):
        frozen = self.source + (self.tx == 5) * 10
        good = self.assess(frozen)
        bad = self.assess(frozen, game=np.rot90(self.source))
        self.assertEqual(good["selected_reference"], bad["selected_reference"])
        self.assertFalse(bad["accepted"])

    def test_bad_export_is_not_excused_without_reference_alarm(self):
        result = self.assess(self.source, game=np.rot90(self.source))
        self.assertEqual(result["state"], "no_reference_alarm")
        self.assertFalse(result["accepted"])

    def test_shifted_or_flipped_coast_cannot_authorize_replacement(self):
        for mask in [np.flipud(self.water), np.roll(self.water, 24, axis=1)]:
            self.assertEqual(registration(self.source, mask, 8)["status"], "unresolved")

    def test_nonfinite_coverage_is_rejected_not_masked(self):
        frozen = self.source.copy()
        frozen[17, 18] = np.nan
        with self.assertRaisesRegex(ValueError, "no point exclusion"):
            self.assess(frozen)

    def test_v2_detects_shared_product_error_without_export_input(self):
        policy = json.loads(
            POLICY_PATH.with_name("reference-policy-v2.json").read_text()
        )
        row, col = np.mgrid[:128, :128]
        wrong = self.source + 100 * np.exp(
            -(((row - 72) / 20) ** 2) - ((col - 67) / 15) ** 2
        )
        tiles = np.zeros_like(self.tx)
        self.assertFalse(alarms(self.source, wrong, wrong, tiles, tiles)["alarm"])
        result = assess(
            self.source, wrong, wrong, tiles, tiles, self.water, 8, policy=policy
        )
        self.assertTrue(result["defect_evidence"]["canonical_alarm"])
        self.assertEqual(result["state"], "reference_defect")
        self.assertNotIn("accepted", result)
        self.assertEqual(policy["acceptance"], POLICY["acceptance"])

    def test_v2_registers_coast_not_interior_pools_without_changing_dem(self):
        policy = json.loads(
            POLICY_PATH.with_name("reference-policy-v2.json").read_text()
        )
        pools = self.water.copy()
        pools[40:120:5, 40:120:5] = True
        source = self.source.copy()
        result = registration(source, pools, 8, policy)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["p90_shore_distance_m"], 0)
        np.testing.assert_array_equal(source, self.source)

    def test_unqualified_canonical_acquisition_cannot_authorize_replacement(self):
        result = assess(
            self.source,
            self.source + (self.tx == 5) * 10,
            self.source,
            self.tx,
            self.ty,
            self.water,
            8,
            game=self.source,
            terracing=0,
            canonical_eligible=False,
        )
        self.assertEqual(result["state"], "unresolved")
        self.assertFalse(result["accepted"])


if __name__ == "__main__":
    unittest.main()
