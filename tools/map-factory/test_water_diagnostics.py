"""Matched-factor behavior on real-format CRP/source bytes, not native acceptance."""

import copy
import hashlib
import struct
import unittest

import numpy as np

from crp import N, metadata_bytes, read_package, string, water_payload, write_package
from template import manager_tag
from water_diagnostics import decode_water, transform


class WaterDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.terrain = np.full(N, 100 * 64, dtype=np.uint16)
        cls.terrain[:8] = 96 * 64
        cls.depth = np.zeros(N, dtype=np.uint16)
        cls.depth[:8] = 3 * 64
        cls.depth[N // 2] = 64
        sources = [
            {
                "position": [0, 100, 0],
                "target": 101.25,
                "capacity": 0.2,
                "output_capacity": 0.8,
                "short_surface_river": True,
            },
            {
                "position": [16, 100, 0],
                "target": 100.25,
                "capacity": 0.1,
                "output_capacity": 0,
                "short_surface_river": True,
            },
            {
                "position": [32, 100, 0],
                "target": 101,
                "capacity": 0.2,
                "output_capacity": 0.2,
            },
            {
                "position": [48, 100, 0],
                "target": 101,
                "capacity": 0.2,
                "output_capacity": 0.1,
                "short_surface_river": True,
            },
            {
                "position": [64, 100, 0],
                "target": 101,
                "capacity": 0.06,
                "class": "lake",
            },
        ]
        cls.hydro = {"sources": sources, "sea_level_m": 99}
        cls.prefix, cls.suffix = (
            b"frozen-terrain-network-camera-prefix",
            b"frozen-resource-tree-suffix",
        )
        simulation = (
            cls.prefix
            + manager_tag("WaterSimulation")
            + water_payload(cls.depth, sources, 123, 99)
            + b"\0\0"
            + cls.suffix
        )
        cls.simulation = simulation
        checksum = hashlib.md5(simulation).hexdigest()
        fields = [
            ("ColossalFramework.Packaging.Package+Asset", "assetRef", checksum),
            ("ColossalFramework.Packaging.Package+Asset", "imageRef", "frozen-image"),
            (
                "ColossalFramework.Packaging.Package+Asset",
                "steamPreviewRef",
                "frozen-steam-image",
            ),
            ("System.Int32", "buildableArea", 37),
            ("System.UInt32", "waterAmount", 123456),
            ("System.String", "mapName", "Frozen diagnostic fixture"),
        ]
        metadata = (
            b"\0"
            + string("MapMetaData, Assembly-CSharp")
            + string("fixture")
            + struct.pack("<i", len(fields))
        )
        for typename, name, value in fields:
            metadata += (
                b"\0"
                + string(typename)
                + string(name)
                + metadata_bytes(typename, value)
            )
        cls.source = write_package(
            {"name": "fixture", "author": "", "version": 1, "main": "main"},
            [
                {"name": "simulation", "kind": 52, "payload": simulation},
                {"name": "metadata", "kind": 100, "payload": metadata},
                {"name": "preview", "kind": 3, "payload": b"original preview"},
                {
                    "name": "steam-preview",
                    "kind": 3,
                    "payload": b"original steam preview",
                },
            ],
        )

    def unpack(self, package):
        assets = read_package(package)[1]
        simulation = next(a["payload"] for a in assets if a["kind"] == 52)
        return assets, simulation, decode_water(simulation)

    def test_decoder_reads_actual_native_count_positions_and_rate_order(self):
        _, _, water = self.unpack(self.source)
        self.assertEqual(len(water["sources"]), 5)
        self.assertEqual(water["sources"][0]["position"], [0, 100, 0])
        self.assertEqual(water["sources"][0]["target_fixed"], 101.25 * 64)
        self.assertEqual(water["sources"][0]["intake_rate"], 13107)
        self.assertEqual(water["sources"][0]["output_rate"], 52428)
        self.assertEqual(water["sources"][1]["output_rate"], 0)
        self.assertEqual(water["frame"], 123)

    def test_short_output_off_changes_only_two_positive_short_output_rates(self):
        package, hydro, depth, receipt = transform(
            self.source, self.hydro, self.terrain, "short-output-off"
        )
        original_assets, _, before = self.unpack(self.source)
        assets, simulation, after = self.unpack(package)
        self.assertEqual(receipt["changed_output_indices"], [0, 3])
        self.assertEqual(receipt["positive_output_controls_before"], 4)
        self.assertEqual(receipt["positive_output_controls_after"], 2)
        self.assertEqual(
            [s["output_rate"] for s in after["sources"]], [0, 0, 13107, 0, 3932]
        )
        self.assertEqual(
            [s["intake_rate"] for s in after["sources"]],
            [s["intake_rate"] for s in before["sources"]],
        )
        np.testing.assert_array_equal(depth, self.depth)
        self.assertTrue(
            simulation.startswith(self.prefix) and simulation.endswith(self.suffix)
        )
        self.assertEqual(
            [a for a in assets if a["kind"] == 3],
            [a for a in original_assets if a["kind"] == 3],
        )
        self.assertEqual(hydro["sources"][1], self.hydro["sources"][1])
        self.assertEqual(hydro["sources"][2], self.hydro["sources"][2])

    def test_sea_only_changes_initial_water_not_a_single_control_or_preview(self):
        package, hydro, depth, receipt = transform(
            self.source, self.hydro, self.terrain, "sea-only"
        )
        original_assets, _, before = self.unpack(self.source)
        assets, simulation, after = self.unpack(package)
        self.assertEqual(before["sources"], after["sources"])
        self.assertEqual(hydro, self.hydro)
        self.assertEqual(receipt["changed_output_indices"], [])
        self.assertEqual(receipt["initial_water_changed_cells"], 1)
        np.testing.assert_array_equal(depth[:8], np.full(8, 3 * 64))
        self.assertEqual(np.count_nonzero(depth[8:]), 0)
        self.assertEqual(
            [a for a in assets if a["kind"] == 3],
            [a for a in original_assets if a["kind"] == 3],
        )
        self.assertTrue(
            simulation.startswith(self.prefix) and simulation.endswith(self.suffix)
        )

    def test_control_receipt_mismatch_fails_closed(self):
        bad = copy.deepcopy(self.hydro)
        bad["sources"][0]["capacity"] = 0.5
        with self.assertRaisesRegex(ValueError, "target/rates differ"):
            transform(self.source, bad, self.terrain, "short-output-off")


if __name__ == "__main__":
    unittest.main()
