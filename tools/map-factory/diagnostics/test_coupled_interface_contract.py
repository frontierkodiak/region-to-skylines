"""Conditional algebra and source-boundary semantics, no physical admission."""

import unittest

from coupled_interface_contract import (
    SCHEMA,
    ROOT,
    coupled_interval,
    entry_site_kind,
    load,
    potential_interface,
    site,
)


class CoupledTests(unittest.TestCase):
    def test_authored_control_is_not_a_mapped_polygon(self):
        self.assertEqual(
            entry_site_kind({"id": "authored:sources:0", "status": "natural_control"}),
            "authored-plan-domain",
        )
        self.assertEqual(
            entry_site_kind({"id": "lakes:0", "field": "lakes"}), "body-domain"
        )
        self.assertIsNone(entry_site_kind({"id": "streams:0", "field": "streams"}))
        self.assertEqual(
            entry_site_kind({"id": "missing:0"}), "unsupported-entry-domain"
        )

    def test_quantized_cut_limit_and_no_permission(self):
        a = coupled_interval(1000, 0, 904)
        self.assertEqual(a["minimum_cut_needed_q"], 192)
        self.assertEqual(a["bed_q"], [808, 808])
        self.assertEqual(a["stage_q"], [904, 904])
        self.assertFalse(a["positive_cut_allowed_under_current_terrain_contract"])
        self.assertIsNone(a["selected_bed_stage_depth"])
        self.assertEqual(
            coupled_interval(1000, 0, 903)["status"], "no_bounded_cut_interval"
        )

    def test_keep_old_depth_and_no_fill(self):
        a = coupled_interval(1000, 200, 1200)
        self.assertEqual(a["minimum_depth_q"], 200)
        self.assertEqual(a["bed_q"], [808, 1000])
        self.assertEqual(a["minimum_cut_needed_q"], 0)
        self.assertEqual(coupled_interval(10, 0, 96)["bed_q"], [0, 0])

    def test_projected_ranges_retain_coupling(self):
        a = coupled_interval(1000, 0, 1050)
        for bed in range(a["bed_q"][0], a["bed_q"][1] + 1):
            self.assertLessEqual(bed + a["minimum_depth_q"], a["stage_q"][1])
            self.assertLessEqual(1000 - bed, 192)
        self.assertEqual(a["minimum_cut_needed_q"], 46)

    def test_no_float_or_invalid_quantization(self):
        for a in [(1.5, 0, 100), (100, -1, 200), (100, 0, 65536)]:
            with self.assertRaises(ValueError):
                coupled_interval(*a)

    def test_proximity_is_not_an_interface_or_direction(self):
        self.assertFalse(potential_interface({"classification": "proximity_only"}))
        self.assertTrue(potential_interface({"shared_native_nodes_rc": [[0, 0]]}))
        self.assertTrue(potential_interface({"path_vertex_membership": ["inside"]}))
        self.assertTrue(potential_interface({}))
        self.assertFalse(
            potential_interface(
                {
                    "path_vertex_membership": ["outside"],
                    "minimum_projected_distance_m": 3,
                }
            )
        )

    def test_geometry_and_sea_cannot_fill_authority_fields(self):
        schema = load(ROOT / SCHEMA)
        a = site(
            "body",
            0,
            {
                "classification": "captured_vertex_incidence",
                "serialized_sea": 90,
                "target": 90,
            },
            ["stream", "ocean"],
            schema,
        )
        self.assertTrue(all(v is None for v in a["authority"].values()))
        self.assertFalse(a["hydraulic_connection_direction_or_capacity_asserted"])
        self.assertEqual(a["status"], "missing_boundary_contract")

    def test_packing_row_direction_is_explicit_not_compass_label(self):
        p = load(ROOT / SCHEMA)["packing_coordinates"]
        self.assertIn("wet[r+1,c]", p["actual_domain_relations"][2])
        self.assertEqual(p["physical_south_first_r_plus_1"], "world +z (north)")
        self.assertFalse(p["physical_vector_or_flow_direction_inferred"])


if __name__ == "__main__":
    unittest.main()
