"""Current place decisions and a test that the held-out labels cannot tune Land."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from survey import fit_place_rules as fit

ROOT = Path(__file__).resolve().parent


class PlaceFit(unittest.TestCase):
    def test_test_labels_and_features_cannot_change_training_threshold(self):
        saved = json.loads((ROOT / "survey/place-fit.json").read_text())
        by = {r["file"]: r for r in saved["rows"]}
        keys = ["package_format", "data_version", "geometry", "native", "start"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            maps = root / "maps"
            maps.mkdir()
            for name in by:
                (maps / name).touch()
            output = root / "fit.json"

            def run(changed):
                def read(path):
                    row = copy.deepcopy(by[path.name])
                    if changed and row["split"] == "test":
                        row["native"]["buildable_area"] = 0
                        row["geometry"]["buildable_fraction"] = 1
                    return {k: row[k] for k in keys}

                with (
                    patch.object(sys, "argv", ["fit", str(maps), str(output)]),
                    patch.object(fit, "measure_stock", side_effect=read),
                ):
                    fit.main()
                return json.loads(output.read_text())

            before, after = run(False), run(True)
            self.assertEqual(before["split"], after["split"])
            self.assertEqual(
                before["rules"]["land_yes_fraction"],
                after["rules"]["land_yes_fraction"],
            )
            self.assertEqual(
                before["summary"]["land"]["train"], after["summary"]["land"]["train"]
            )
            self.assertNotEqual(
                before["summary"]["land"]["heldout"],
                after["summary"]["land"]["heldout"],
            )
            self.assertEqual(len(before["split"]["test"]), 21)
            self.assertEqual(len(before["split"]["train"]), 83)


if __name__ == "__main__":
    unittest.main()
