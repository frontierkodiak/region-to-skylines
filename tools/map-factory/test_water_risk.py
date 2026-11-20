"""Observable invariants of the general water-risk screen, not fixture IDs."""

import copy
import json
from pathlib import Path
import unittest

import numpy as np

from water_risk import assess, classify, measure
from water_risk_corpus import native_outcome
from calibrate_water_risk import calibrate, metrics


class WaterRiskTests(unittest.TestCase):
    def inputs(self):
        ground = np.full((1081, 1081), 100 * 64, dtype=np.uint16)
        water = np.zeros_like(ground)
        ground[500:503, 200:700] = 98 * 64
        water[500:503, 200:700] = 64
        hydro = {
            "sea_level_m": None,
            "sources": [
                {
                    "name": "original",
                    "position": [0, 0, 0],
                    "target": 99,
                    "capacity": 0.01,
                }
            ],
            "rivers": [],
        }
        return ground, water, hydro

    def test_names_and_place_ids_never_select_a_repair_or_prediction(self):
        terrain, water, hydro = self.inputs()
        before = (terrain.copy(), water.copy(), copy.deepcopy(hydro))
        first = measure(terrain, water, hydro)
        renamed = copy.deepcopy(hydro)
        renamed.update(map_id="any-other-square", map_name="not-a-fixture")
        renamed["sources"][0].update(name="another place", id=999999)
        self.assertEqual(first, measure(terrain, water, renamed))
        self.assertTrue(np.array_equal(terrain, before[0]))
        self.assertTrue(np.array_equal(water, before[1]))
        self.assertEqual(hydro, before[2])

    def test_translation_of_ground_and_targets_preserves_physical_flags(self):
        terrain, water, hydro = self.inputs()
        first = measure(terrain, water, hydro)
        hydro["sources"][0]["target"] += 10
        translated = measure(terrain + 10 * 64, water, hydro)
        self.assertEqual(classify(first), classify(translated))
        for key in first:
            self.assertAlmostEqual(first[key], translated[key], places=8)

    def test_ocean_does_not_dilute_inland_channel_statistics(self):
        terrain, water, hydro = self.inputs()
        base = measure(terrain, water, hydro)
        terrain[:100] = 35 * 64
        water[:100] = 5 * 64
        hydro["sea_level_m"] = 40
        ocean = measure(terrain, water, hydro)
        self.assertEqual(base["thin_fraction"], ocean["thin_fraction"])
        self.assertEqual(base["wet_fraction"], ocean["wet_fraction"])
        self.assertGreater(ocean["ocean_fraction"], 0)

    def test_one_shared_rule_flags_each_physical_pattern(self):
        features = measure(*self.inputs())
        features.update(
            ocean_fraction=0,
            emitter_exposure_km2=0,
            bank_limited_fraction=0,
            input_output_ratio=1,
            unforced_fraction=0,
            profile_overbank_p95_m=0,
        )
        self.assertFalse(any(classify(features).values()))
        for key, value, expected in [
            ("emitter_exposure_km2", 0.02, "flood"),
            ("bank_limited_fraction", 0.2, "drying"),
            ("input_output_ratio", 3, "drying"),
            ("unforced_fraction", 0.01, "drying"),
            ("profile_overbank_p95_m", 4, "drying"),
        ]:
            changed = {**features, key: value}
            self.assertTrue(classify(changed)[expected])
        coastal = {**features, "ocean_fraction": 0.2, "shore_freeboard_p10_m": 0}
        self.assertTrue(all(classify(coastal).values()))

    def test_incomplete_inputs_decline_instead_of_silently_exporting(self):
        terrain, water, hydro = self.inputs()
        self.assertEqual(assess(terrain[:2], water, hydro)["status"], "declined")
        bad = terrain.astype(float)
        bad[0, 0] = np.nan
        self.assertEqual(assess(bad, water, hydro)["status"], "declined")
        hydro["sources"][0]["capacity"] = float("inf")
        self.assertEqual(assess(terrain, water, hydro)["status"], "declined")

    def test_model_has_no_place_or_package_lookup(self):
        model = json.loads(
            (Path(__file__).parent / "water-risk-model.json").read_text()
        )
        self.assertEqual(
            set(model),
            {"schema", "version", "rules", "features", "ranges", "calibration"},
        )
        self.assertFalse(set(model) & {"records", "fingerprints", "cases", "places"})

    def test_short_passing_runs_are_censored_not_long_run_negatives(self):
        verdict = {
            "checks": [
                {"name": "no_flooding", "status": "pass", "value": {"worst_km2": 0}},
                {
                    "name": "probes_wet_end",
                    "status": "pass",
                    "value": {"wet": 10, "required": 10},
                },
            ]
        }
        self.assertEqual(
            native_outcome({"game_minutes": 5}, verdict)["labels"],
            {"flood": None, "drying": None},
        )
        self.assertEqual(
            native_outcome(
                {"game_minutes": 60, "points": [{"wet_start": True, "wet_end": True}]},
                verdict,
            )["labels"],
            {"flood": False, "drying": False},
        )

    def test_display_rounding_cannot_erase_an_original_flood_failure(self):
        verdict = {
            "checks": [
                {"name": "no_flooding", "status": "fail", "value": {"worst_km2": 0.05}}
            ]
        }
        self.assertTrue(native_outcome({"game_minutes": 5}, verdict)["labels"]["flood"])

    def test_advisory_water_loss_does_not_relabel_the_original_gate(self):
        verdict = {
            "checks": [
                {
                    "name": "probes_wet_end",
                    "status": "pass",
                    "value": {"wet": 99, "required": 100},
                }
            ]
        }
        result = native_outcome({"game_minutes": 60}, verdict)
        self.assertTrue(result["labels"]["drying"])
        self.assertFalse(result["original_dry_gate_failed"])

    def test_optional_water_loss_and_exact_thinning_remain_distinct(self):
        verdict = {
            "checks": [
                {
                    "name": "probes_wet_end",
                    "status": "pass",
                    "value": {"wet": 10, "required": 10},
                }
            ]
        }
        report = {
            "game_minutes": 60,
            "points": [
                {"wet_start": True, "wet_end": False, "wet_within_64m_end": True},
                {"wet_start": True, "wet_end": False, "wet_within_64m_end": False},
            ],
        }
        result = native_outcome(report, verdict)
        self.assertTrue(result["labels"]["drying"])
        self.assertFalse(result["required_water_loss"])
        self.assertFalse(result["original_dry_gate_failed"])
        self.assertEqual(result["exact_point_wet_loss_end"], 2)
        self.assertEqual(result["initialized_water_loss_end"], 1)

    def test_no_negative_observations_cannot_establish_specificity(self):
        result = metrics([{"outcome": "tp"}, {"outcome": "tp"}])
        self.assertEqual(result["precision"], 1)
        self.assertIsNone(result["specificity"])
        self.assertEqual(result["negative_runs"], 0)

    def test_committed_calibration_reproduces_from_bound_corpus(self):
        root = Path(__file__).parent
        contract = json.loads(
            (root / "fixtures/contracts/pl912-water-risk-v1/current.json").read_text()
        )
        rows = json.loads((root / "fixtures" / contract["corpus_file"]).read_text())
        coverage = json.loads(
            (root / "fixtures" / contract["coverage_file"]).read_text()
        )
        model, _ = calibrate(rows, coverage)
        self.assertEqual(
            model, json.loads((root / "water-risk-model.json").read_text())
        )


if __name__ == "__main__":
    unittest.main()
