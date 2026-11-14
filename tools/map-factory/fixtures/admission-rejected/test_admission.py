"""Uncarved connector behavior, with source geography and neighbors retained."""

import copy
import unittest

import numpy as np

from admission import connector_status, feature_id, remove_connector_cuts
from region import hydrology, raster


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        def coord(x):
            return [float(np.rad2deg(x / 6378137)), 0]

        self.line = {"pts": [coord(-320), coord(320)], "class": "river"}
        self.geometry = {
            "sq": {"lat": 0, "lon": 0, "rotation": 0, "scale": 1},
            "fit": {"verticalScale": 1},
            "rivers": [self.line],
            "undergroundWaterways": [
                {"pts": [coord(-480), coord(-320)], "brunnel": "tunnel"},
                {"pts": [coord(320), coord(480)], "brunnel": "tunnel"},
            ],
        }
        self.banks = np.full((1081, 1081), 100.0)
        self.path = np.column_stack([np.full(41, 540), np.arange(520, 561)])
        self.channel = raster(self.geometry["sq"], [self.line])

    def status(self):
        return connector_status(
            self.path, self.banks, self.geometry, [self.line], self.channel, raster, 3
        )

    def test_portal_connectivity_alone_does_not_reject_a_feasible_reach(self):
        self.assertIsNone(self.status())
        # A crest at both ends contradicts either bounded gravity direction.
        self.banks[540, 520] = self.banks[540, 560] = 110
        status = self.status()
        self.assertGreater(min(status["gravity_excess_m"]), 1 / 64)
        self.geometry["undergroundWaterways"].pop()
        self.assertIsNone(self.status())

    def test_omitted_connector_has_no_excavation_water_or_controls(self):
        self.banks[540, 520] = self.banks[540, 560] = 110
        surveys = [self.status()]
        ground = self.banks.copy()
        ground[535:546, 515:566] -= 6
        original_geometry = copy.deepcopy(self.geometry)
        restored, report = remove_connector_cuts(
            ground, self.banks, self.geometry, surveys
        )
        # Actual inherited line incision is removed, not narrowed around water.
        self.assertEqual(restored[540, 540], self.banks[540, 540])
        depth, hydro = hydrology(
            restored, self.banks, self.geometry, deferred={feature_id(self.line)}
        )
        self.assertEqual(restored[540, 540], self.banks[540, 540])
        self.assertEqual(float(depth.max()), 0)
        self.assertEqual(hydro["sources"], [])
        self.assertTrue(hydro["samples"])
        self.assertEqual(self.geometry, original_geometry)
        self.assertGreater(report["restored_vertices"], 0)

    def test_polygon_contribution_does_not_leave_a_residual_trench(self):
        def point(x, y):
            return [float(np.rad2deg(x / 6378137)), float(np.rad2deg(y / 6335439.327))]

        self.geometry["riverAreas"] = [
            {
                "rings": [
                    [point(-200, -40), point(200, -40), point(200, 40), point(-200, 40)]
                ]
            }
        ]
        surveys = [{"features": [self.line], "gravity_excess_m": [1, 1]}]
        ground = self.banks - 5
        restored, report = remove_connector_cuts(
            ground, self.banks, self.geometry, surveys
        )
        self.assertEqual(restored[540, 540], self.banks[540, 540])
        self.assertGreater(report["deferred_polygon_vertices"], 0)


if __name__ == "__main__":
    unittest.main()
