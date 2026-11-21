import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from crp import read_package
from synthetic_source_response import ROOT, channel, export, patch_outputs, validate
from synthetic_source_protocol import replay
from water_diagnostics import decode_water


class SyntheticGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layout = json.loads((ROOT / "templates/native-corridors.json").read_text())
        cls.g, cls.h, cls.f, cls.w, cls.plan = channel(cls.layout)

    def test_every_branch_node_full_rim_and_port_obeys_fixed_bounds(self):
        validate(self.f, self.w, self.g, self.h, self.plan, self.layout)
        self.assertEqual(len(self.plan["nodes"]), 73)
        self.assertEqual(len(self.h["sources"]), 3)
        self.assertTrue(self.plan["source_radius_model_m"] < 16)
        self.assertLessEqual(self.plan["maximum_cut_m"], 3)
        self.assertGreaterEqual(self.plan["minimum_freeboard_m"], 0.5)
        self.assertTrue(np.all(self.w[self.w > 0] == 96))

    def test_outside_prefill_rim_omission_and_excess_cut_fail(self):
        bad = self.w.copy()
        bad[0, 0] = 96
        with self.assertRaises(ValueError):
            validate(self.f, bad, self.g, self.h, self.plan, self.layout)
        plan = copy.deepcopy(self.plan)
        plan["rim_rc"].pop()
        with self.assertRaisesRegex(ValueError, "rim"):
            validate(self.f, self.w, self.g, self.h, plan, self.layout)
        floor = self.f.copy()
        floor[tuple(self.plan["nodes"][0]["node_rc"])] = 6000
        with self.assertRaises(ValueError):
            validate(floor, self.w, self.g, self.h, self.plan, self.layout)


class SyntheticPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.output = Path(cls.temp.name) / "prepared"
        cls.generation = export(cls.output)

    def test_source_replay_rejects_a_coherently_shortened_cohort(self):
        replay(self.output)
        path = self.output / "parent/inventory.json"
        original = path.read_bytes()
        try:
            inventory = json.loads(original)
            inventory["points"].pop()
            path.write_text(json.dumps(inventory))
            with self.assertRaisesRegex(ValueError, "source-derived cohort"):
                replay(self.output)
        finally:
            path.write_bytes(original)

    def test_source_replay_rejects_changed_fixed_intakes(self):
        path = self.output / "output-000/hydrology.json"
        original = path.read_bytes()
        try:
            hydro = json.loads(original)
            hydro["sources"][0]["capacity"] = 0
            path.write_text(json.dumps(hydro))
            with self.assertRaisesRegex(ValueError, "fixed intake"):
                replay(self.output)
        finally:
            path.write_bytes(original)

    def test_real_packages_change_only_declared_outputs_and_simulation_reference(self):
        parent = next((self.output / "parent").glob("*.crp")).read_bytes()
        original = read_package(parent)[1]
        for arm in self.generation["arms"]:
            folder = self.output / arm["folder"]
            raw = (folder / arm["package"]).read_bytes()
            self.assertEqual(raw, patch_outputs(parent, arm["setting"]))
            assets = read_package(raw)[1]
            for a, b in zip(original, assets):
                if a["kind"] not in (52, 100):
                    self.assertEqual(a, b)
            decoded = decode_water(
                next(a["payload"] for a in assets if a["kind"] == 52)
            )
            self.assertEqual(
                [s["intake_rate"] for s in decoded["sources"]], [128, 128, 128]
            )
            self.assertEqual(
                [s["output_rate"] for s in decoded["sources"]],
                [arm["setting"], arm["setting"], 0],
            )

    def test_complete_source_sectors_and_three_exact_port_anchors_are_fixed(self):
        inventory = json.loads((self.output / "parent/inventory.json").read_text())
        contracts = [c for e in inventory["entries"] for c in e.get("contracts", [])]
        self.assertEqual(sum(c["kind"] == "natural" for c in contracts), 3)
        self.assertEqual(sum(c["kind"] == "engineered" for c in contracts), 3)
        self.assertTrue(inventory["coverage_complete"])
        initial = json.loads(
            (self.output / "parent/authored-initialization.json").read_text()
        )
        self.assertTrue(all(c["status"] == "pass" for c in initial["contracts"]))
        for name in [
            "probes.json",
            "inventory.json",
            "water.u16",
            "terrain.u16",
            "mapped-water.u8",
        ]:
            self.assertEqual(
                len(
                    {
                        (self.output / a["folder"] / name).read_bytes()
                        for a in self.generation["arms"]
                    }
                ),
                1,
            )
