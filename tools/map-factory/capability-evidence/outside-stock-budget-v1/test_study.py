"""Behavior gates for literal labels, frozen selection, and reference semantics."""

import copy
import unittest

import study
import evaluate


class Labels(unittest.TestCase):
    def row(self):
        return {
            "plan": {"request": {"from": [1, 0, 0], "to": [2, 0, 255]}},
            "result": {
                "complete": True,
                "released": True,
                "success": True,
                "positions": [[1, 0, 0], [2, 0, 255]],
            },
        }

    def test_exact_released_success_only(self):
        row = self.row()
        self.assertEqual(evaluate.label(row), "success")
        row["result"]["positions"][-1][-1] = 128
        self.assertEqual(evaluate.label(row), "unknown")
        row["result"]["success"] = False
        self.assertEqual(evaluate.label(row), "no_path")
        row["result"]["released"] = False
        self.assertEqual(evaluate.label(row), "unknown")

    def test_error_is_not_negative(self):
        row = self.row()
        row["error"] = "timeout"
        row["result"]["success"] = False
        self.assertEqual(evaluate.label(row), "unknown")

    def test_unknowns_do_not_enter_confusion_counts(self):
        result = evaluate.metrics(
            [("success", "unknown"), (None, "unknown"), ("success", "no_path")]
        )
        self.assertEqual(result["FP"], 1)
        self.assertEqual(result["unknown_label"], 1)
        self.assertEqual(result["null_prediction"], 1)
        self.assertIsNone(result["recall"])


class Selection(unittest.TestCase):
    def test_quota_reciprocal_and_unqueried_are_conserved(self):
        rows = []
        for i in range(12):
            rows.append(
                {
                    "request": {"from": [i + 1, 0, 0], "to": [i + 20, 0, 255]},
                    "rules": {
                        study.RULES[0]: {
                            "prediction": "success" if i < 6 else "no_path"
                        }
                    },
                }
            )
        rows[1]["request"] = {
            "from": rows[0]["request"]["to"],
            "to": rows[0]["request"]["from"],
        }
        before = copy.deepcopy(rows)
        selected, rest = study.select_queries(rows)
        self.assertEqual(len(selected), 8)
        self.assertEqual(len(rest), 4)
        self.assertEqual(
            sum(
                r["rules"][study.RULES[0]]["prediction"] == "success" for r in selected
            ),
            4,
        )
        self.assertEqual(
            study.request_key(selected[0]), study.request_key(selected[1])[::-1]
        )
        self.assertEqual(rows, before)
        self.assertEqual(study.select_queries(rows), (selected, rest))

    def test_intervention_order_and_immutable_old_labels(self):
        rows = study.intervention()
        fps = [r for r in rows if r["selection"] == "first_four_false_positive"]
        self.assertEqual(len(fps), 4)
        self.assertTrue(all(r["old_label"] == "failure" for r in fps))
        keys = [(r["artifact_sha256"], r["canonical_request_sha256"]) for r in fps]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(len({r["canonical_request_sha256"] for r in rows}), 8)
        self.assertEqual(study.BUDGETS, [100000, 200000, 1000000])

    def test_modes_with_no_controls_are_unqualified(self):
        modes = evaluate.controls_from_observations({"controls": []}, {})
        self.assertTrue(all(not row["qualified"] for row in modes.values()))


if __name__ == "__main__":
    unittest.main()
