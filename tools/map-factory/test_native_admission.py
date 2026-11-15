"""Source binding and conservative reach eligibility, not hydraulic acceptance."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from native_admission import (
    dry_pieces,
    native_evidence,
    retain_startup_support,
    write_grid,
)


class DryPieceTests(unittest.TestCase):
    def setUp(self):
        def point(x, z):
            return [
                np.rad2deg(x / 6378137),
                np.rad2deg(z / (6378137 * (1 - 0.00669437999014))),
            ]

        self.geometry = {
            "sq": {"lat": 0, "lon": 0, "rotation": 0, "scale": 1},
            "rivers": [
                {"name": "same name", "pts": [point(0, 0), point(160, 0)]},
                {"name": "same name", "pts": [point(1000, 0), point(1160, 0)]},
            ],
        }
        self.hydro = {
            "rivers": [
                {
                    "name": "same name",
                    "class": "river",
                    "bank_limited": True,
                    "upstream": [540, 540],
                }
            ]
        }

    def test_disconnected_namesake_is_not_a_bank_limited_component(self):
        chosen = dry_pieces(self.geometry, self.hydro, np.zeros((1081, 1081), bool))
        self.assertEqual([i for i, _ in chosen], [0])

    def test_one_supported_cell_keeps_the_complete_piece(self):
        near = np.zeros((1081, 1081), bool)
        near[540, 545] = True
        self.assertEqual(dry_pieces(self.geometry, self.hydro, near), [])

    def test_feasible_stream_uses_the_same_native_rule(self):
        self.geometry["streams"] = self.geometry.pop("rivers")
        self.hydro["rivers"][0].update({"class": "stream", "bank_limited": False})
        chosen = dry_pieces(self.geometry, self.hydro, np.zeros((1081, 1081), bool))
        self.assertEqual([i for i, _ in chosen], [0])
        self.hydro["rivers"][0]["unforced_infeasible_stream"] = True
        self.assertEqual(
            dry_pieces(self.geometry, self.hydro, np.zeros((1081, 1081), bool)), []
        )


class NativeBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.prepared = Path(self.temp.name) / "prepared"
        self.native = Path(self.temp.name) / "native"
        self.prepared.mkdir()
        (self.native / "grids").mkdir(parents=True)
        raw = b"test-only package, not native evidence"
        (self.prepared / "test.crp").write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        self.write(self.prepared / "generation.json", {"package": {"sha256": digest}})
        self.write(self.prepared / "hydrology.json", {"map_id": "test"})
        self.write(
            self.native / "session-receipt.json",
            {"map": {"sha256": digest}, "cleanup": {}},
        )
        self.write(self.native / "report.json", {"game_minutes": 5.1})
        zero = np.zeros((1081, 1081), "<u2")
        for name in ["terrain", "water"]:
            write_grid(self.prepared / f"{name}.u16", zero)
            write_grid(self.native / f"grids/t000-{name}.u16", zero)
        wet = zero.copy()
        wet[540, 540] = 7
        write_grid(self.native / "grids/t005-water.u16", wet)

    @staticmethod
    def write(path, data):
        path.write_text(json.dumps(data))

    def test_exact_64m_disk_and_later_water_both_retain_support(self):
        later = np.zeros((1081, 1081), "<u2")
        later[500, 500] = 1  # Even a native film is protected, not qualified wet.
        write_grid(self.native / "grids/t015-water.u16", later)
        _, _, wet, near, _ = native_evidence(self.prepared, self.native)
        self.assertTrue(near[540, 544])
        self.assertFalse(near[541, 544])
        self.assertTrue(wet[500, 500])
        self.assertFalse(near[500, 500])

    def test_wrong_package_is_rejected_before_classification(self):
        (self.prepared / "test.crp").write_bytes(b"different terrain/source package")
        with self.assertRaisesRegex(ValueError, "different package"):
            native_evidence(self.prepared, self.native)

    def test_changed_native_initial_grid_is_rejected(self):
        with (self.native / "grids/t000-water.u16").open("r+b") as stream:
            stream.write(b"\x01\x00")
        with self.assertRaisesRegex(ValueError, "initial water mismatch"):
            native_evidence(self.prepared, self.native)

    def test_no_five_minute_sample_is_not_evidence(self):
        (self.native / "grids/t005-water.u16").unlink()
        with self.assertRaisesRegex(ValueError, "actual five-minute"):
            native_evidence(self.prepared, self.native)


class StartupSupportTests(unittest.TestCase):
    def test_dry_restoration_cannot_change_a_retained_water_patch(self):
        terrain = np.zeros((1081, 1081), "<u2")
        candidate = terrain.copy()
        candidate[100, 100] = 64
        water = terrain.copy()
        water[100, 101] = 7
        empty = np.zeros_like(terrain, bool)
        result = retain_startup_support(terrain, candidate, water, empty, empty)
        self.assertEqual(result[100, 100], 0)

    def test_omitted_startup_film_does_not_block_its_own_restoration(self):
        terrain = np.zeros((1081, 1081), "<u2")
        candidate = terrain.copy()
        candidate[100, 100] = 64
        water = terrain.copy()
        water[100, 100] = 7
        zone = np.zeros_like(terrain, bool)
        zone[100, 100] = True
        result = retain_startup_support(
            terrain, candidate, water, zone, np.zeros_like(zone)
        )
        self.assertEqual(result[100, 100], 64)


if __name__ == "__main__":
    unittest.main()
