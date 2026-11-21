"""Frozen native probes must cover the actual source-only feature inventory."""

import json
import unittest

from maintained_water_inventory import sha
from maintained_water_plan import preflight, stage
import test_closed_storage_observation as fixture


class MaintainedWaterPlanTests(unittest.TestCase):
    def setUp(self):
        # Reuse the real CRP writer fixture, not a mocked package or receipt.
        fixture.ClosedStorageObservationTests.setUp(self)
        self.output = self.folder.parent / "maintained"
        self.receipt = stage(self.folder, self.output)

    def test_actual_package_and_new_complete_probes_preflight(self):
        plan, inventory = preflight(self.output)
        self.assertTrue(inventory["coverage_complete"])
        self.assertTrue(self.receipt["new_probes"])
        package = plan["item"]["package"]
        self.assertEqual(
            plan["item"]["files_sha256"][package],
            self.generation["physical_files_sha256"][package],
        )
        self.assertEqual(
            json.loads((self.folder / "probes.json").read_text())["points"],
            json.loads((self.output / "probes.json").read_text())["points"][
                : -self.receipt["new_probes"]
            ],
        )

    def test_coherent_probe_omission_and_plan_rehash_still_rejects(self):
        path = self.output / "probes.json"
        probes = json.loads(path.read_text())
        probes["points"].pop()
        path.write_text(json.dumps(probes))
        plan_path = self.output / "native-plan.json"
        plan = json.loads(plan_path.read_text())
        plan["item"]["files_sha256"]["probes.json"] = sha(path)
        plan_path.write_text(json.dumps(plan))
        with self.assertRaisesRegex(ValueError, "omit or alter"):
            preflight(self.output)

    def test_coherent_inventory_omission_still_rejects(self):
        path = self.output / "inventory.json"
        inventory = json.loads(path.read_text())
        inventory["entries"] = []
        inventory["points"] = []
        path.write_text(json.dumps(inventory))
        plan_path = self.output / "native-plan.json"
        plan = json.loads(plan_path.read_text())
        plan["item"]["files_sha256"]["inventory.json"] = sha(path)
        plan_path.write_text(json.dumps(plan))
        with self.assertRaisesRegex(ValueError, "source-only compilation"):
            preflight(self.output)

    def test_changed_validator_is_rejected(self):
        path = self.output / "native-plan.json"
        plan = json.loads(path.read_text())
        plan["compiler_sources_sha256"]["maintained_water_inventory.py"] = "0" * 64
        path.write_text(json.dumps(plan))
        with self.assertRaisesRegex(ValueError, "Compiler or validator changed"):
            preflight(self.output)


if __name__ == "__main__":
    unittest.main()
