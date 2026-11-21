"""Mutation and boundary tests for the prospective experiment contract."""

import copy
import unittest

import study
import evaluate


def request(a, b):
    return {"from": [a, 0, 0], "to": [b, 1, 255], "endpoint_edges": ["east", "west"]}


class ContractTests(unittest.TestCase):
    def frozen(self):
        q = request(1, 2)
        inventory = {"file": "A.crp", "sha256": "new", "stratum": study.STRATA[0]}
        return {
            "protocol": copy.deepcopy(study.PROTOCOL),
            "sources": study.source_files(),
            "selected": [{**inventory, "slug": "holdout-01", "selected_requests": [q]}],
            "inventory": [inventory],
            "excluded_hashes": ["old"],
            "predictions": [
                {
                    "id": "holdout-01:000",
                    "slug": "holdout-01",
                    "request": q,
                    "predictions": {r: {"prediction": "success"} for r in study.RULES},
                }
            ],
            "query_ids": ["holdout-01:000"],
        }

    def test_closed_source_maps(self):
        f = self.frozen()
        study.validate(f)
        f["sources"]["reader"].pop(next(iter(f["sources"]["reader"])))
        with self.assertRaisesRegex(ValueError, "source-map"):
            study.validate(f)

    def test_extra_inner_source_rejected(self):
        f = self.frozen()
        f["sources"]["reader"]["unread.py"] = "invented"
        with self.assertRaises(ValueError):
            study.validate(f)

    def test_closed_protocol(self):
        f = self.frozen()
        f["protocol"]["turn_threshold"] = 45
        with self.assertRaises(ValueError):
            study.validate(f)

    def test_missing_query_rejected(self):
        f = self.frozen()
        f["predictions"] = []
        with self.assertRaises(ValueError):
            study.validate(f)

    def test_duplicate_query_rejected(self):
        f = self.frozen()
        f["selected"][0]["selected_requests"] *= 2
        f["predictions"] *= 2
        f["query_ids"] *= 2
        with self.assertRaises(ValueError):
            study.validate(f)

    def test_unknown_prediction_rejected(self):
        f = self.frozen()
        f["predictions"][0]["predictions"][study.RULES[0]]["prediction"] = "probably"
        with self.assertRaises(ValueError):
            study.validate(f)

    def test_old_hash_excluded(self):
        f = self.frozen()
        f["selected"][0]["sha256"] = "old"
        with self.assertRaises(ValueError):
            study.validate(f)

    def test_exact_labels_not_truthiness(self):
        q = request(1, 2)
        good = {
            "request": q,
            "result": {
                "complete": True,
                "released": True,
                "success": True,
                "positions": [q["from"], q["to"]],
            },
        }
        self.assertEqual(study.label(good), "success")
        for field in ["complete", "released", "success"]:
            bad = copy.deepcopy(good)
            bad["result"][field] = "true"
            self.assertEqual(study.label(bad), "unknown")
        good["result"]["positions"][-1] = [2, 1, 128]
        self.assertEqual(study.label(good), "unknown")
        good["result"]["success"] = False
        self.assertEqual(study.label(good), "no_path")

    def test_reciprocal_and_budget(self):
        reciprocal = request(2, 1)
        reciprocal["from"][2] = 255
        reciprocal["to"][2] = 0
        rows = [request(1, b) for b in range(2, 90)] + [reciprocal]
        selected, unqueried = study.select_queries(rows)
        self.assertEqual(len(selected), 64)
        self.assertEqual(selected[1]["from"][0], 2)
        self.assertEqual(selected[1]["to"][0], 1)
        self.assertEqual(len(selected) + len(unqueried), len(rows))

    def test_consensus_only_model_flag(self):
        c = {
            "segment_names": {1: ["Created"]},
            "segment_name_conflicts": {1: {"Created": 5, "Created, NameVisible1": 2}},
        }
        self.assertFalse(study.model_flag(c, "segment", 1, "Invert"))
        self.assertIsNone(study.model_flag(c, "segment", 2, "Invert"))
        c["segment_name_conflicts"][1]["Created, Invert"] = 1
        self.assertIsNone(study.model_flag(c, "segment", 1, "Invert"))

    def test_empty_rates_and_unknown_accounting(self):
        self.assertIsNone(evaluate.score([], study.RULES[0])["precision"])
        rows = [
            {
                "label": "unknown",
                "predictions": {study.RULES[0]: {"prediction": "success"}},
            }
        ]
        s = evaluate.score(rows, study.RULES[0])
        self.assertEqual(s["unknown"], 1)
        self.assertEqual(s["coverage"], 0)
        self.assertIsNone(s["recall"])


if __name__ == "__main__":
    unittest.main()
