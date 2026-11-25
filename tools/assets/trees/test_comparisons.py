"""Reference selection must not silently substitute a stock or unloaded tree."""

import json
from pathlib import Path
import tempfile
import unittest

from comparisons import load_plan, resolve_plan, specimen_references


class ComparisonTests(unittest.TestCase):
    def test_retained_defaults(self):
        plan = load_plan(["KudzuTilia15sand3d", "OtherRouteElm"], "Tree2")
        self.assertEqual(plan["KudzuTilia15sand3d"]["prefab"], "mp9-YoungLinden")
        self.assertEqual(plan["OtherRouteElm"]["prefab"], "Tree2")

    def test_explicit_reference_and_missing_prefab(self):
        override = {
            "NewElm": {
                "prefab": "123456789.Mature Elm_Data",
                "basis": "Supply ledger reviewed mature match",
                "evidence": "PL-1326 pinned review record",
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(json.dumps(override))
            plan = load_plan(["NewElm"], "Tree2", path)
        with self.assertRaisesRegex(ValueError, "did not load"):
            resolve_plan(plan, [{"name": "Tree2"}])
        tree = {"name": override["NewElm"]["prefab"], "main_triangles": 1200}
        bound = resolve_plan(plan, [tree])
        self.assertEqual(bound["NewElm"]["catalog"], tree)
        self.assertEqual(bound["NewElm"]["evidence"], override["NewElm"]["evidence"])

    def test_invalid_plan_rejected_before_native_work(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            for value in (
                [],
                {"TypoElm": {}},
                {"Elm": {"prefab": "Tree2"}},
                {"Elm": {"prefab": " ", "basis": "x", "evidence": "x"}},
            ):
                with self.subTest(value=value):
                    path.write_text(json.dumps(value))
                    with self.assertRaises(ValueError):
                        load_plan(["Elm"], "Tree2", path)

    def test_gallery_uses_actual_placed_reference_not_genus(self):
        pairs = [
            {
                "specimens": [
                    {"name": "KudzuTilia15new.KudzuTilia15new_Data"},
                    {"name": "123456789.Old Linden_Data"},
                ],
                "comparison_basis": "Reviewed mature match",
            }
        ]
        reference = specimen_references(pairs)["KudzuTilia15new"]
        self.assertEqual(reference["prefab"], "123456789.Old Linden_Data")
        self.assertEqual(reference["basis"], "Reviewed mature match")
        self.assertIsNone(reference["evidence"])


if __name__ == "__main__":
    unittest.main()
