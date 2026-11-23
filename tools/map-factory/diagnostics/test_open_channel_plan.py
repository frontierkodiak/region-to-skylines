import tempfile
from pathlib import Path
import unittest

import numpy as np

from open_channel_plan import graph, profile, reporting_notes
from test_maintained_water_inventory import line
from unprepared_stream_ledger import geometry_only


def geometry(lines):
    return {
        "sq": {"lon": 0, "lat": 0, "rotation": 0, "scale": 1},
        "streams": lines,
        "rivers": [],
        "lakes": [],
        "riverAreas": [],
        "oceans": [],
    }


class OpenPlanTests(unittest.TestCase):
    def test_literal_branch_keeps_every_piece_and_joins_actual_source_vertex(self):
        g = geometry(
            [line((-64, 0), (0, 0)), line((0, 64), (0, 0)), line((0, 0), (64, 0))]
        )
        result = graph(g, geometry_only(g))
        self.assertEqual(len(result["eligible_clip_ids"]), 3)
        self.assertEqual(len(result["components"]), 1)
        self.assertTrue(
            any(
                r["joined_in_geometric_hypothesis"]
                for r in result["literal_source_junctions"]
            )
        )
        self.assertTrue(
            all(
                r["hydraulic_junction_authority"] is None
                for r in result["literal_source_junctions"]
            )
        )

    def test_nearby_same_name_native_coincidence_is_not_joined(self):
        g = geometry(
            [line((0, 0), (64, 0), name="same"), line((1, 1), (65, 1), name="same")]
        )
        result = graph(g, geometry_only(g))
        self.assertEqual(len(result["components"]), 2)
        self.assertTrue(result["raster_coincidence_not_joined"])

    def test_excluded_branch_incidence_stays_explicit_not_surface_join(self):
        g = geometry([line((-64, 0), (0, 0)), line((0, 0), (64, 0), intermittent=True)])
        result = graph(g, geometry_only(g))
        self.assertEqual(len(result["eligible_clip_ids"]), 1)
        self.assertTrue(
            any(
                r["excluded_or_unsupported_incidence"]
                for r in result["literal_source_junctions"]
            )
        )

    def test_variable_stage_respects_full_bank_no_fill_and_cut_bounds(self):
        floor = np.full((11, 11), 7200, np.uint16)
        floor[4:7, 2:7] = np.array([7100, 7000, 6900, 6800, 6700])
        floor[5, 3:6] = [6400, 6336, 6272]
        before = floor.copy()
        result = profile(
            [[5, 3], [5, 4], [5, 5]], [(0, 1), (1, 2)], floor, np.zeros_like(floor)
        )
        self.assertEqual(result["status"], "feasible")
        self.assertGreater(result["distinct_stages"], 1)
        self.assertTrue(
            all(a >= b for a, b in zip(result["target_q"], result["target_q"][1:]))
        )
        self.assertTrue(np.array_equal(before, floor))
        self.assertLessEqual(result["maximum_cut_q"], 192)

    def test_local_bank_conflict_not_repaired_by_choosing_direction(self):
        floor = np.full((5, 5), 6400, np.uint16)
        floor[2, 2] = 9000
        result = profile([[2, 2]], [], floor, np.zeros_like(floor))
        self.assertEqual(result["status"], "infeasible_bounds")

    def test_open_boundary_missing_lateral_authority_stays_unknown(self):
        floor = np.full((5, 5), 6400, np.uint16)
        result = profile([[0, 2], [1, 2]], [(1, 0)], floor, np.zeros_like(floor))
        self.assertEqual(
            result["status"], "unresolved_open_port_lateral_or_exterior_bank"
        )
        self.assertIsNone(result["target_q"])

    def test_reporting_feasible_minimum_null_and_counts_separated_by_kind(self):
        g = geometry([line((0, 0), (64, 0))])
        floor = np.full((1081, 1081), 6400, np.uint16)
        old = {
            "case": "example",
            "models": [
                {
                    "adjacency": 8,
                    "source_footprints": [
                        {"id": "streams:0", "minimum_stage_for_any_1m_source_q": 6464}
                    ],
                    "contracts": [
                        {
                            "kind": k,
                            "optimistic_any_nearby_raster": {"numeric_fit_only": True},
                            "restricted_own_source_raster": {"numeric_fit_only": True},
                        }
                        for k in ("natural", "engineered")
                    ],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            (np.full_like(floor, 6464, dtype=np.int32)).astype("<i4").tofile(
                Path(tmp) / "example-adj8-escape.i32"
            )
            result = reporting_notes(old, floor, g, Path(tmp))["models"][0]
        self.assertIsNone(
            result["source_footprints"][0]["minimum_feasible_stage_for_any_1m_source_q"]
        )
        self.assertEqual(
            result["numeric_fit_counts_by_kind"]["natural"][
                "optimistic_any_nearby_raster"
            ],
            1,
        )
        self.assertEqual(
            result["numeric_fit_counts_by_kind"]["engineered"][
                "optimistic_any_nearby_raster"
            ],
            1,
        )


if __name__ == "__main__":
    unittest.main()
