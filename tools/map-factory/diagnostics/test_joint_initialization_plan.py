import unittest

from joint_initialization_plan import (
    flag,
    literal_endpoint_facts,
    local_interval,
    obligations,
    requires_open_interface,
)


class JointPlanTests(unittest.TestCase):
    def context(self, **kw):
        return {
            "external_rim_unknown": False,
            "wet_rim_nodes": 0,
            "non_proximity_source_interfaces": [],
            "minimum_source_rim_terrain_q": 200,
            **kw,
        }

    def test_multiple_obligations_not_scalar_precedence(self):
        value = obligations([1, 4, 1, 1, 1, 2, 0, 0, 0], "streams", False)
        for name in [
            "old_corridor_112m",
            "foreign_or_excluded_line_128m",
            "other_water_or_excluded_geometry",
            "open_line_lateral_direction_unknown",
        ]:
            self.assertTrue(value & flag(name))

    def test_own_buffer_and_other_body_stay_separate(self):
        value = obligations([1, 8, 1, 0, 2, 0, 1, 0, 0], "lakes", False)
        for name in [
            "old_mapped_body_128m",
            "other_water_or_excluded_geometry",
            "own_buffer_not_body",
            "overlapping_polygon_buffers",
        ]:
            self.assertTrue(value & flag(name))

    def test_rounded_edge_is_not_a_literal_endpoint(self):
        def clip(x, clipped):
            return {
                "id": "a:clip:0",
                "source_id": "a",
                "start_clipped": clipped,
                "end_clipped": False,
                "points_xz": [[x, 0], [0, 0]],
            }

        self.assertEqual(
            literal_endpoint_facts({"clips": {"a": clip(8639.99, True)}}), []
        )
        self.assertEqual(
            literal_endpoint_facts({"clips": {"a": clip(8640, False)}}), []
        )
        facts = literal_endpoint_facts({"clips": {"a": clip(8640, True)}})
        self.assertEqual(facts[0]["literal_faces"], ["east"])
        self.assertEqual(facts[0]["clip_id"], "a:clip:0")

    def test_coastal_interface_schema_is_not_silently_proximity(self):
        record = {
            "projected_1um_incidence": [],
            "path_vertex_membership": ["outside", "outside"],
            "native_raster_contact": [],
            "minimum_projected_distance_m": 12.0,
        }
        self.assertFalse(requires_open_interface(record))
        self.assertTrue(
            requires_open_interface({**record, "native_raster_contact": [[1, 2]]})
        )
        self.assertTrue(
            requires_open_interface({**record, "path_vertex_membership": ["boundary"]})
        )
        self.assertFalse(requires_open_interface({"classification": "proximity_only"}))
        self.assertTrue(
            requires_open_interface({"classification": "native_raster_only_contact"})
        )
        with self.assertRaises(ValueError):
            requires_open_interface({"polygon_id": "lakes:0"})

    def test_exact_fixed_bed_depth_and_margin_intervals(self):
        value = local_interval(64, 0, self.context(), True)
        self.assertEqual(value["stage_q"], [160, 168])
        self.assertEqual(value["depth_q"], [96, 104])
        self.assertEqual(value["bed_q"], [64, 64])
        self.assertIsNone(value["chosen_stage_q"])
        self.assertFalse(value["physical_admission"])

    def test_old_water_never_removed_and_empty_bounds_retained(self):
        value = local_interval(64, 110, self.context(), True)
        self.assertEqual(value["status"], "empty_source_space_interval")
        self.assertEqual(value["stage_q"], [174, 168])
        self.assertEqual(value["initial_depth_delta_q"], [0, -6])

    def test_open_boundary_or_interface_never_gets_closed_cap(self):
        for ctx in [
            self.context(external_rim_unknown=True),
            self.context(wet_rim_nodes=1),
            self.context(
                non_proximity_source_interfaces=[{"classification": "raster_contact"}]
            ),
        ]:
            value = local_interval(64, 0, ctx, True)
            self.assertNotIn("stage_q", value)
            self.assertEqual(value["status"], "unresolved_open_or_wet_rim_interface")
        self.assertEqual(
            local_interval(64, 0, self.context(), False)["status"],
            "unresolved_obligations",
        )


if __name__ == "__main__":
    unittest.main()
