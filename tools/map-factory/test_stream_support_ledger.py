import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from crp import encode_u16, water_payload, write_package
from natural_storage_candidate import write
from stream_construction import assess, sha
from stream_support_ledger import geometry_ledger, package_controls, preflight, stage
from template import manager_tag
from test_maintained_water_inventory import body, line
import test_stream_construction as stream_fixture
from test_stream_construction import fixture


class InterfaceLedgerTests(unittest.TestCase):
    def build(self, g, h, f, w, layout):
        from natural_water_inventory import compile_natural_inventory
        from waterway_pieces import compile_piece_inventory

        pieces, plan = assess(g, h, f, w, layout)
        lake = {"source_features": [], "bodies": []}
        old = compile_natural_inventory(g, h, lake)
        inv = compile_piece_inventory(g, h, lake, pieces, plan)
        ledger = geometry_ledger(g, h, inv, pieces, plan, f, w, [])
        self.assertEqual(inv["points"], old["points"])
        return ledger, inv, plan

    def test_exact_geographic_branch_and_underground_endpoint_not_hydraulic_acceptance(
        self,
    ):
        g, h, f, w, layout = fixture()
        g["streams"].append(line((64, 0), (96, 0), brunnel="tunnel"))
        result, inv, plan = self.build(g, h, f, w, layout)
        self.assertEqual(len(result["clips"]), 3)
        self.assertEqual(
            sum(len(c["contract_ids"]) for c in result["clips"]),
            sum(
                len(e.get("contracts", []))
                for e in inv["entries"]
                if e.get("field") == "streams"
            ),
        )
        shared = [
            r
            for r in result["line_interfaces"]
            if r["classification"] == "captured_vertex_incidence"
        ]
        self.assertTrue(shared)
        self.assertTrue(
            all(r["hydraulic_connectivity"] == "unresolved" for r in shared)
        )
        self.assertTrue(result["native_stream_branches"])
        self.assertEqual(len(plan["clip_components"]), 2)

    def test_projected_crossing_without_captured_vertex_is_not_a_source_node(self):
        g, h, f, w, layout = fixture()
        g["streams"] = [line((-32, 0), (32, 0)), line((0, -32), (0, 32))]
        result, *_ = self.build(g, h, f, w, layout)
        relation = result["line_interfaces"][0]
        self.assertEqual(relation["classification"], "projected_1um_segment_incidence")
        self.assertFalse(relation["exact_captured_geographic_vertices"])
        self.assertEqual(relation["projected_1um_intersections"][0]["xz_m"], [0, 0])

    def test_square_clipping_sectors_and_same_name_disconnected_parts_survive(self):
        g, h, f, w, layout = fixture()
        g["streams"] = [
            line((-9000, 0), (1000, 0), name="same"),
            line((3000, 3000), (3001, 3000), name="same"),
        ]
        result, inv, _ = self.build(g, h, f, w, layout)
        self.assertEqual(len(result["clips"]), 2)
        first = result["clips"][0]
        self.assertTrue(first["endpoints"][0]["source_clipped"])
        self.assertTrue(first["endpoints"][0]["projected_square_boundary"])
        self.assertEqual(
            first["contract_ids"], [c["id"] for c in inv["entries"][0]["contracts"]]
        )
        self.assertEqual(len(result["clips"][1]["contract_ids"]), 1)

    def test_mapped_body_crossing_and_missing_rows_are_explicit(self):
        g, h, f, w, layout = fixture()
        g["lakes"] = [body(16, -8, 48, 8)]
        g["streams"].append(None)
        result, *_ = self.build(g, h, f, w, layout)
        self.assertEqual(result["line_rows"][-1]["status"], "unresolved")
        self.assertTrue(result["body_interfaces"])
        self.assertTrue(
            any(
                r["projected_1um_boundary_incidence"] for r in result["body_interfaces"]
            )
        )


class PhysicalLedgerProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stream_fixture.StreamProtocolTests.setUpClass()
        cls.addClassCleanup(stream_fixture.StreamProtocolTests.temp.cleanup)
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        import shutil
        from natural_water_inventory import compile_natural_inventory

        inputs = cls.root / "inputs"
        shutil.copytree(stream_fixture.StreamProtocolTests.source, inputs)
        hydro = json.loads((inputs / "hydrology.json").read_text())
        hydro["sources"] = [
            {
                "class": "stream",
                "position": [-7000, 0, -7000],
                "target": 100.5,
                "capacity": 0.1,
                "output_capacity": 0.2,
            }
        ]
        write(inputs / "hydrology.json", hydro)
        inventory = compile_natural_inventory(
            json.loads((inputs / "geometry.json").read_text()),
            hydro,
            json.loads((inputs / "natural-plan.json").read_text()),
        )
        write(inputs / "inventory.json", inventory)
        cls.source = cls.root / "source"
        stream_fixture.stage(inputs, cls.source, inputs / "layout.json")
        cls.physical = cls.root / "physical"
        cls.physical.mkdir()
        # A real-format CRP with explicit native managers; no native observation.
        f, w = [(cls.source / n).read_bytes() for n in ("terrain.u16", "water.u16")]
        terrain, water = [np.frombuffer(raw, "<u2") for raw in (f, w)]
        simulation = (
            manager_tag("TerrainManager")
            + encode_u16(terrain)
            + encode_u16(np.zeros(int((terrain != 0).sum()), np.uint16))
            + manager_tag("WaterSimulation")
            + water_payload(water, hydro["sources"], 123)
            + b"\0\0"
        )
        package = write_package(
            {"name": "fixture", "author": "", "version": 1, "main": "main"},
            [{"name": "simulation", "kind": 52, "payload": simulation}],
        )
        (cls.physical / "fixture.crp").write_bytes(package)
        for name in (
            "terrain.u16",
            "water.u16",
            "geometry.json",
            "hydrology.json",
            "mapped-water.u8",
            "natural-plan.json",
            "probes.json",
        ):
            (cls.physical / name).write_bytes((cls.source / name).read_bytes())
        (cls.physical / "inventory.json").write_bytes(
            (cls.source / "inventory-v2.json").read_bytes()
        )
        write(
            cls.physical / "generation.json",
            {
                "schema": "polli.replenished-natural-storage-candidate/1",
                "package": "fixture.crp",
                "physical_files_sha256": {
                    p.name: sha(p) for p in cls.physical.iterdir()
                },
            },
        )
        cls.output = cls.root / "protocol"
        stage(cls.source, cls.physical, cls.output)

    def test_physical_source_bytes_bound_but_no_new_native_qualification(self):
        preflight(self.output)
        ledger = json.loads((self.output / "ledger.json").read_text())
        self.assertEqual(
            ledger["forcing"]["package_sha256"], sha(self.physical / "fixture.crp")
        )
        control = ledger["forcing"]["controls"][0]
        self.assertEqual(len(bytes.fromhex(control["raw43_hex"])), 43)
        self.assertEqual(control["encoded"]["intake_rate"], 6554)
        self.assertEqual(control["encoded"]["output_rate"], 13107)
        self.assertEqual(control["physical_supply_budget"], "unmeasured")
        self.assertIsNone(ledger["new_physical_package"])
        self.assertFalse(ledger["native_observation"])
        self.assertEqual(ledger["stable_water_promise"], "unknown")
        self.assertTrue(
            any(
                c["status"] == "fail"
                for c in ledger["authored_initialization"]["contracts"]
            )
        )

    def test_coherent_interface_omission_rejects(self):
        path, fp = self.output / "ledger.json", self.output / "freeze.json"
        saved, frozen = path.read_bytes(), fp.read_bytes()
        try:
            ledger = json.loads(saved)
            ledger["clips"].pop()
            write(path, ledger)
            freeze = json.loads(frozen)
            freeze["files_sha256"]["ledger.json"] = sha(path)
            write(fp, freeze)
            with self.assertRaisesRegex(ValueError, "does not replay"):
                preflight(self.output)
        finally:
            path.write_bytes(saved)
            fp.write_bytes(frozen)

    def test_wrong_control_cohort_is_not_an_attributed_supply(self):
        hydro_path, gen_path = (
            self.physical / "hydrology.json",
            self.physical / "generation.json",
        )
        saved, frozen = hydro_path.read_bytes(), gen_path.read_bytes()
        temp = self.root / "wrong-source"
        import shutil

        shutil.copytree(self.source, temp)
        try:
            hydro = json.loads(saved)
            hydro["sources"].append(
                {"position": [0, 0, 0], "target": 100, "capacity": 0.1}
            )
            write(hydro_path, hydro)
            write(temp / "hydrology.json", hydro)
            generation = copy.deepcopy(json.loads(frozen))
            generation["physical_files_sha256"]["hydrology.json"] = sha(hydro_path)
            write(gen_path, generation)
            with self.assertRaisesRegex(ValueError, "Source count differs"):
                package_controls(temp, self.physical)
        finally:
            hydro_path.write_bytes(saved)
            gen_path.write_bytes(frozen)
