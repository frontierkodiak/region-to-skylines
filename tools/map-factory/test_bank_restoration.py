"""Terrain-only bank restoration must retain wet beds and regulator headroom."""

import copy
import unittest

import numpy as np

from region import restore_unsupported_banks


class BankRestorationTests(unittest.TestCase):
    def test_restore_dry_shoulders_without_replaying_narrowing_failure(self):
        ground = np.full((1081, 1081), 100.0)
        banks = ground.copy()
        ground[539:542, 530:551] = 94
        depth = np.zeros_like(ground)
        depth[540, 530:551] = 1
        ground[541, 540] = 95.001
        source = {
            "position": [0, 0, 0],
            "target": 95.0,
            "capacity": 0.01,
        }
        report = {"sources": [source]}
        geometry = {"sq": {"lat": 0, "lon": 0, "rotation": 0, "scale": 1}}
        before = ground.copy()
        controls = copy.deepcopy(report["sources"])
        restore_unsupported_banks(ground, depth, banks, geometry, report)
        self.assertEqual(ground[539, 530], 100)
        np.testing.assert_array_equal(ground[depth > 0], before[depth > 0])
        # An unseeded cell within the existing regulator's footprint is also
        # supported: restoring it to DEM would put it above the unchanged head.
        self.assertEqual(ground[539, 540], 94)
        self.assertEqual(ground[541, 540], 95.001)
        self.assertLess(ground[540, 540], source["target"])
        self.assertEqual(report["sources"], controls)
        self.assertTrue(np.all(ground >= before))
        self.assertTrue(np.all(ground <= banks))
        self.assertGreater(report["bank_restoration"]["restored_cells"], 0)

    def test_tunnel_is_not_surface_support_but_crossing_is(self):
        def coord(x):
            return [float(np.rad2deg(x / 6378137)), 0]

        tunnel = {"pts": [coord(-320), coord(320)], "brunnel": "tunnel"}
        geometry = {
            "sq": {"lat": 0, "lon": 0, "rotation": 0, "scale": 1},
            "rivers": [tunnel],
        }
        ground = np.full((1081, 1081), 94.0)
        banks = ground + 6
        depth = np.zeros_like(ground)
        restore_unsupported_banks(ground, depth, banks, geometry, {"sources": []})
        self.assertEqual(ground[540, 540], 100)
        geometry["rivers"].append({"pts": [coord(-16), coord(16)]})
        ground.fill(94)
        restore_unsupported_banks(ground, depth, banks, geometry, {"sources": []})
        self.assertEqual(ground[540, 540], 94)


if __name__ == "__main__":
    unittest.main()
