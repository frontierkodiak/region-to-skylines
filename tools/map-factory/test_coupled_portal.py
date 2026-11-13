"""The rejected coupled classifier requires topology AND a gravity contradiction."""

import unittest
import numpy as np
from region import raster
from coupled_portal_experiment import portal_gravity_status


class CoupledPortalTests(unittest.TestCase):
    def test_missing_polygons_or_literal_class_is_not_a_minor_classifier(self):
        f = {"pts": [[-0.01, 0], [0.01, 0]], "class": "river"}
        g = {"sq": {"lat": 0, "lon": 0, "rotation": 0, "scale": 1}, "rivers": [f]}
        line = raster(g["sq"], [f])
        path = np.array([[540, x] for x in range(470, 611)])
        banks = np.full((1081, 1081), 100.0)
        banks[:, 580:] = 110
        result = portal_gravity_status(path, banks, g, [f], line)
        self.assertGreater(result["minimum_gravity_profile_above_bank_ceiling_m"], 0)
        self.assertFalse(result["defer_browser_cut"])
        g["undergroundWaterways"] = [
            {"pts": [[-0.02, 0], [-0.01, 0]]},
            {"pts": [[0.01, 0], [0.02, 0]]},
        ]
        self.assertTrue(
            portal_gravity_status(path, banks, g, [f], line)["defer_browser_cut"]
        )
        banks.fill(100)
        self.assertFalse(
            portal_gravity_status(path, banks, g, [f], line)["defer_browser_cut"]
        )


if __name__ == "__main__":
    unittest.main()
