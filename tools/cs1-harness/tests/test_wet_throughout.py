"""Persistence uses observed native samples, never just the final wet value."""

import copy
import json
import pathlib
import tempfile
import unittest

from cs1_harness.verdict import MAP_SOAK, map_soak, probes_wet_throughout


class WetThroughoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = pathlib.Path(self.tmp.name)
        self.points = [{"name": f"river {i}", "x": i * 16, "z": 0} for i in range(20)]
        self.meta = {"points": self.points}
        self.samples = [
            {
                "kind": "sample",
                "label": f"t{i:03d}",
                "stats": {"frame": i * 100},
                "water": {"samples": [{**p, "wet": True, "wet_within_64m": True} for p in self.points]},
            }
            for i in range(3)
        ]
        self.report = {
            "start_frame": 0,
            "end_frame": 200,
            "frames_per_game_minute": 100,
            "points": [{**p, "samples": 3, "wet_end": True} for p in self.points],
            "curve": [{"minute": i} for i in range(3)],
        }

    def assess(self):
        (self.out / "timeline.jsonl").write_text("\n".join(json.dumps(s) for s in self.samples) + "\n")
        return probes_wet_throughout(self.out, self.report, self.meta, MAP_SOAK)

    def dry(self, sample, point, nearby=False):
        self.samples[sample]["water"]["samples"][point].update(wet=False, wet_within_64m=nearby)

    def test_dry_most_run_rewet_at_end_fails_despite_end_gate_passing(self):
        for s in [0, 1]:
            for p in range(20):
                self.dry(s, p)
        self.assess()
        (self.out / "probes.json").write_text(json.dumps(self.meta))
        rows = {r["name"]: r for r in map_soak(self.out, self.report)}
        self.assertEqual(rows["probes_wet_end"]["status"], "pass")
        self.assertEqual(rows["probes_wet_throughout"]["status"], "fail")
        self.assertEqual(rows["probes_wet_throughout"]["value"]["without_water_probes"], 20)

    def test_nearby_rescues_exact_dry_with_explicit_diagnostic(self):
        self.dry(1, 0, nearby=True)
        result = self.assess()
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["value"]["exact_dry"]["observations"], 1)
        self.assertEqual(result["value"]["native_no_nearby"]["observations"], 0)
        self.assertEqual(result["value"]["wet_throughout"], 20)

    def test_same_95_percent_probe_tolerance_not_observation_average(self):
        self.dry(1, 0)
        self.assertEqual(self.assess()["status"], "pass")  # 19/20 persist
        self.dry(2, 1)
        self.assertEqual(self.assess()["status"], "fail")  # rotating per-sample 95% is not persistence
        self.assertEqual(self.assess()["value"]["wet_throughout"], 18)

    def test_exact_wet_legacy_needs_no_invented_nearby_fields(self):
        for s in self.samples:
            for p in s["water"]["samples"]:
                del p["wet_within_64m"]
        self.assertEqual(self.assess()["status"], "pass")
        self.samples[1]["water"]["samples"][0]["wet"] = False
        result = self.assess()
        self.assertEqual(result["status"], "fail")
        self.assertIn("no native nearby evidence", result["detail"])

    def test_missing_file_missing_samples_or_curve_coverage_fails(self):
        self.assertEqual(probes_wet_throughout(self.out, self.report, self.meta, MAP_SOAK)["status"], "fail")
        self.samples.pop(1)
        self.assertEqual(self.assess()["status"], "fail")
        self.report["curve"].pop(1)
        for p in self.report["points"]:
            p["samples"] = 2
        sparse = self.assess()
        self.assertEqual(sparse["status"], "pass")
        self.assertEqual(sparse["value"]["largest_sample_gap_minutes"], 2)
        self.assertIn("not continuous", sparse["detail"])
        self.samples = self.samples[:1]
        self.assertEqual(self.assess()["status"], "fail")

    def test_native_point_identity_missing_duplicate_or_shifted_fails(self):
        original = copy.deepcopy(self.samples)
        for defect in ["missing", "duplicate", "coordinates", "name"]:
            self.samples = copy.deepcopy(original)
            p = self.samples[1]["water"]["samples"]
            if defect == "missing":
                p.pop(0)
            if defect == "duplicate":
                p.append(copy.deepcopy(p[0]))
            if defect == "coordinates":
                p[0]["x"] += 1
            if defect == "name":
                p[0]["name"] = "other"
            with self.subTest(defect=defect):
                self.assertEqual(self.assess()["status"], "fail")
        self.samples = copy.deepcopy(original)
        self.samples[1]["water"]["samples"][0]["x"] += 0.0005
        self.assertEqual(self.assess()["status"], "pass")

    def test_malformed_flags_frames_and_json_fail_closed(self):
        original = copy.deepcopy(self.samples)
        for defect in ["wet", "nearby", "frame", "unordered"]:
            self.samples = copy.deepcopy(original)
            if defect == "wet":
                self.samples[1]["water"]["samples"][0]["wet"] = "true"
            if defect == "nearby":
                self.samples[1]["water"]["samples"][0]["wet_within_64m"] = 1
            if defect == "frame":
                del self.samples[1]["stats"]["frame"]
            if defect == "unordered":
                self.samples[1]["stats"]["frame"] = 0
            with self.subTest(defect=defect):
                self.assertEqual(self.assess()["status"], "fail")
        (self.out / "timeline.jsonl").write_text("not json")
        self.assertEqual(probes_wet_throughout(self.out, self.report, self.meta, MAP_SOAK)["status"], "fail")

    def test_frozen_required_identity_cannot_disappear_from_report(self):
        self.report["points"].pop(0)
        self.assertEqual(self.assess()["status"], "fail")

    def test_only_genuinely_empty_required_cohort_skips(self):
        self.meta["points"] = [{**p, "required": False} for p in self.points]
        self.assertEqual(self.assess()["status"], "skip")
        self.meta = {}
        self.assertEqual(self.assess()["status"], "pass")  # honest report-cohort legacy fallback
        self.report.pop("points")
        self.assertEqual(self.assess()["status"], "fail")

    def test_missing_interval_end_and_report_counts_fail_closed(self):
        original = copy.deepcopy(self.report)
        for defect in ["end", "counts", "curve", "interval"]:
            self.report = copy.deepcopy(original)
            if defect == "end":
                self.report["end_frame"] = 300
            if defect == "counts":
                self.report["points"][0]["samples"] = 2
            if defect == "curve":
                self.report["curve"][1]["minute"] = 1.5
            if defect == "interval":
                del self.report["frames_per_game_minute"]
            with self.subTest(defect=defect):
                self.assertEqual(self.assess()["status"], "fail")

    def test_subsets_are_counted_and_capped_not_hidden(self):
        self.points = [{"name": f"river {i}", "x": i * 16, "z": 0} for i in range(60)]
        self.meta = {"points": self.points}
        self.report["points"] = [{**p, "samples": 3, "wet_end": True} for p in self.points]
        for i, row in enumerate(self.samples):
            row["water"]["samples"] = [{**p, "wet": i != 1, "wet_within_64m": i != 1} for p in self.points]
        result = self.assess()
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["value"]["exact_dry"]["probes"], 60)
        self.assertEqual(result["value"]["native_no_nearby"]["observations"], 60)
        self.assertEqual(len(result["value"]["without_water_names"]), 40)
        self.assertEqual(result["value"]["without_water_names_truncated"], 20)

    def test_required_overrides_match_existing_cohort(self):
        self.meta["points"][0]["required"] = False
        self.dry(1, 0)
        result = self.assess()
        self.assertEqual(result["value"]["required"], 19)
        self.assertEqual(result["value"]["exact_dry"]["observations"], 0)
        self.assertEqual(result["status"], "pass")


if __name__ == "__main__":
    unittest.main()
