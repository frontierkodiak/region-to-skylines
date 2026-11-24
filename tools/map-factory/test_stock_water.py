import unittest
from unittest.mock import patch

import numpy as np

from stock_water import Design, hydrology

DESIGN = Design(40, 192, 40, 2, 54, 0.5, 0.01)
SQUARE = {"lat": 0, "lon": 0, "rotation": 0, "scale": 1}


def point(x, z):
    return [np.rad2deg(x / 6378137), np.rad2deg(z / 6335439.3272928195)]


class StockWaterTest(unittest.TestCase):
    def test_river_is_cut_only_with_one_sparse_upstream_control(self):
        ground = np.full((1081, 1081), 100.0)
        banks = ground.copy()
        geometry = {
            "sq": SQUARE,
            "rivers": [{"pts": [point(-9000, 0), point(9000, 0)], "name": "test"}],
            "riverAreas": [
                {
                    "rings": [
                        [
                            point(-9000, -32),
                            point(9000, -32),
                            point(9000, 32),
                            point(-9000, 32),
                            point(-9000, -32),
                        ]
                    ]
                }
            ],
        }
        with patch(
            "stock_water.local_catchment_area", return_value=np.full_like(ground, 75e6)
        ):
            depth, report = hydrology(ground, banks, geometry, DESIGN)
        self.assertTrue((ground <= banks).all())
        self.assertTrue(np.array_equal(ground[:100], banks[:100]))
        self.assertAlmostEqual(depth[540, 540], 40)
        self.assertEqual(len(report["sources"]), 1)
        self.assertEqual(report["sources"][0]["role"], "inlet")
        self.assertEqual(report["water_max_raise_m"], 0)
        self.assertEqual(report["sources"][0]["capacity"], 0.5)
        self.assertAlmostEqual(report["sea_level_m"], 98, delta=1 / 128)
        self.assertLessEqual(abs(report["sources"][0]["position"][0]), 8640 - 128)

    def test_line_only_side_channel_is_not_given_the_broad_river_profile(self):
        ground = np.full((1081, 1081), 100.0)
        geometry = {
            "sq": SQUARE,
            "rivers": [{"pts": [point(-9000, 0), point(9000, 0)]}],
        }
        with patch(
            "stock_water.local_catchment_area", return_value=np.full_like(ground, 75e6)
        ):
            depth, report = hydrology(ground, ground.copy(), geometry, DESIGN)
        self.assertAlmostEqual(depth[540, 540], 16)
        self.assertEqual(depth[545, 540], 0)
        self.assertEqual(len(report["sources"]), 1)
        self.assertEqual(report["sources"][0]["capacity"], 655 / 65535)

    def test_small_lake_left_as_ground_larger_lake_cut_without_bank_fill(self):
        ground = np.full((1081, 1081), 100.0)
        banks = ground.copy()

        def ring(x, radius):
            return [
                point(x - radius, -radius),
                point(x + radius, -radius),
                point(x + radius, radius),
                point(x - radius, radius),
                point(x - radius, -radius),
            ]

        geometry = {
            "sq": SQUARE,
            "lakes": [{"rings": [ring(-1000, 16)]}, {"rings": [ring(1000, 200)]}],
        }
        depth, report = hydrology(ground, banks, geometry, DESIGN)
        self.assertTrue((ground <= banks).all())
        self.assertEqual(len(report["sources"]), 1)
        self.assertEqual(report["sources"][0]["role"], "lake-level")
        self.assertEqual(depth[540, round((-1000 + 8640) / 16)], 0)
        self.assertAlmostEqual(depth[540, round((1000 + 8640) / 16)], 40)
        self.assertEqual(len(report["lake_components"]), 2)

    def test_stream_uses_continuous_narrow_channel_not_regulator_pools(self):
        ground = np.full((1081, 1081), 100.0)
        banks = ground.copy()
        geometry = {
            "sq": SQUARE,
            "streams": [
                {"pts": [point(-9000, 0), point(9000, 0)], "name": "test stream"}
            ],
        }
        with patch(
            "stock_water.local_catchment_area", return_value=np.full_like(ground, 75e6)
        ):
            depth, report = hydrology(ground, banks, geometry, DESIGN)
        self.assertAlmostEqual(depth[540, 540], 16)
        self.assertEqual(depth[545, 540], 0)
        self.assertTrue((ground <= banks).all())
        self.assertEqual(len(report["sources"]), 1)
        self.assertEqual(report["sources"][0]["role"], "inlet")
        self.assertTrue(report["samples"])
        self.assertEqual(report["mapped_stream_nodes_without_initial_water"], 0)

        ground[:] = banks
        geometry["streams"][0]["intermittent"] = 1
        dry, unforced = hydrology(ground, banks, geometry, DESIGN)
        self.assertFalse(dry.any())
        self.assertEqual(unforced["sources"], [])
        self.assertGreater(unforced["mapped_stream_nodes_without_initial_water"], 0)


if __name__ == "__main__":
    unittest.main()
