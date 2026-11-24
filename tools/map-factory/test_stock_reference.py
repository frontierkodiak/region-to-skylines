import unittest

import numpy as np

from stock_reference import stock_cohort


class StockReferenceTest(unittest.TestCase):
    def test_keeps_tiny_bodies_and_native_orientation(self):
        depth = np.zeros((65, 65), dtype=np.uint16)
        depth[0, 0] = 7
        depth[-1, -1] = 6
        result = stock_cohort(depth, "definition")
        self.assertEqual(len(result["entries"]), 1)
        self.assertEqual(result["points"][0]["x"], -512)
        self.assertEqual(result["points"][0]["z"], -512)

    def test_large_body_is_split_without_repeated_probes(self):
        depth = np.full((65, 65), 64, dtype=np.uint16)
        result = stock_cohort(depth, "definition")
        self.assertEqual(len(result["entries"]), 1)
        contracts = result["entries"][0]["contracts"]
        self.assertEqual(len(contracts), 4)
        names = [p["name"] for p in result["points"]]
        self.assertEqual(len(names), len(set(names)))
        for contract in contracts:
            pts = np.array(contract["points_xz"])
            self.assertTrue((np.ptp(pts, axis=0) <= 512).all())

    def test_dry_map_has_no_invented_water(self):
        result = stock_cohort(np.zeros((33, 33), dtype=np.uint16), "definition")
        self.assertEqual(result["entries"], [])
        self.assertEqual(result["points"], [])


if __name__ == "__main__":
    unittest.main()
