import unittest
from copy import deepcopy

import numpy as np
from scipy import ndimage

from playable_water import (
    capacity,
    component_outlet_intakes,
    cover_component_emitters,
    hydrology,
    join_nearby_water,
    raster,
    section,
    source_pool,
    source_walk,
    stage_tree,
)


class PlayableWaterTests(unittest.TestCase):
    @staticmethod
    def emitter(row, col, setting=0.01):
        return {
            "class": "river",
            "role": "catchment_inlet",
            "position": [col * 16 - 8640, 0, 8640 - row * 16],
            "target": 100,
            "capacity": setting,
            "output_capacity": setting,
        }

    def test_unsupplied_component_gets_one_catchment_inlet_without_changing_prefix(
        self,
    ):
        ground = np.full((81, 81), 98.0)
        depth = np.zeros_like(ground)
        depth[5:15, 5:15] = 2
        depth[50:60, 50:60] = 2
        channel = depth > 0
        levels = np.full_like(ground, 100)
        levels[55, 55] = 110
        area = np.full_like(ground, 25)
        classes = np.ones(ground.shape, np.uint8)
        drain = self.emitter(52, 52)
        drain["output_capacity"] = 0
        sources = [self.emitter(10, 10), drain]
        prefix = deepcopy(sources)
        added = cover_component_emitters(
            ground,
            depth,
            levels,
            np.zeros_like(channel),
            channel,
            area,
            classes,
            sources,
            depth.copy(),
        )
        self.assertEqual(sources[:2], prefix)
        self.assertEqual(added, [2])
        self.assertEqual(sources[2]["class"], "stream")
        self.assertEqual(sources[2]["position"], [55 * 16 - 8640, 0, 8640 - 55 * 16])
        self.assertEqual(sources[2]["output_capacity"], 0.04)
        self.assertGreaterEqual(
            sources[2]["footprint_pool"]["minimum_authored_core_depth_m"], 1
        )
        self.assertEqual(
            cover_component_emitters(
                ground,
                depth,
                levels,
                np.zeros_like(channel),
                channel,
                area,
                classes,
                sources,
                depth.copy(),
            ),
            [],
        )

    def test_fallback_inlet_requests_guide_minimum_without_renaming_a_stream_lake(self):
        ground = np.full((31, 31), 98.0)
        depth = np.zeros_like(ground)
        depth[14:17, 14:17] = 2
        channel = depth > 0
        sources = []
        cover_component_emitters(
            ground,
            depth,
            np.full_like(ground, 100),
            np.zeros_like(channel),
            channel,
            np.zeros_like(ground),
            np.ones(ground.shape, np.uint8),
            sources,
            depth.copy(),
        )
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["class"], "stream")
        self.assertEqual(sources[0]["capacity"], 0.01)
        self.assertEqual(sources[0]["position"], [14 * 16 - 8640, 0, 8640 - 14 * 16])

    def test_outlets_ignore_emitter_spacing_and_change_only_the_control_table(self):
        channel = np.zeros((31, 31), bool)
        channel[:8, :8] = True
        channel[15:25, 15:25] = True
        depth = channel.astype(float) * 2
        levels = np.full(depth.shape, 100.0)
        ports = [
            {"component": 1, "row": 0, "col": 0, "role": "map_edge"},
            {"component": 2, "row": 15, "col": 15, "role": "closed_component"},
        ]
        sources = [
            self.emitter(0, 0, 0.8),
            self.emitter(1, 1, 0.8),
            self.emitter(16, 16),
        ]
        prefix = deepcopy(sources)
        originals = [a.copy() for a in (channel, depth, levels)]
        receipt = component_outlet_intakes(channel, depth, levels, ports, sources)
        self.assertEqual(sources[:3], prefix)
        for before, after in zip(originals, (channel, depth, levels), strict=True):
            np.testing.assert_array_equal(before, after)
        self.assertEqual([r["intake_records"] for r in receipt], [2, 1])
        self.assertEqual(sources[3]["position"], sources[0]["position"])
        self.assertEqual(
            sources[-1]["outlet_kind"], "engineered_closed_component_drain"
        )
        for row in receipt:
            self.assertGreaterEqual(
                row["declared_intake_settings"], row["summed_output_settings"]
            )
            for index in row["intake_indices"]:
                intake = sources[index]
                self.assertEqual(intake["class"], "intake")
                self.assertEqual(intake["role"], "engineered_outlet_intake")
                self.assertEqual(intake["output_capacity"], 0)
                self.assertEqual(intake["target"], row["receiving_stage_m"])
                self.assertGreater(intake["capacity"], 0)
                self.assertLessEqual(intake["capacity"], 1)
                self.assertNotIn("footprint_pool", intake)

    def test_intake_skips_a_nearer_wet_anchor_above_the_receiving_stage(self):
        channel = np.zeros((5, 3), bool)
        channel[:, 1] = True
        levels = np.full(channel.shape, 100.0)
        levels[:, 1] = [100, 103, 102, 105, 106]
        depth = np.zeros(channel.shape)
        depth[:, 1] = [0.5, 1, 4, 1, 1]
        original_levels, original_depth = levels.copy(), depth.copy()
        sources = [self.emitter(4, 1)]
        receipt = component_outlet_intakes(
            channel,
            depth,
            levels,
            [{"component": 1, "row": 0, "col": 1, "role": "map_edge"}],
            sources,
        )[0]
        self.assertEqual(receipt["anchor_rc"], [2, 1])
        self.assertEqual(receipt["anchor_depth_at_receiving_stage_m"], 2)
        self.assertEqual(sources[-1]["target"], 100)
        np.testing.assert_array_equal(levels, original_levels)
        np.testing.assert_array_equal(depth, original_depth)

    def test_missing_legal_receiving_stage_anchor_does_not_change_controls_or_fields(
        self,
    ):
        channel = np.ones((3, 3), bool)
        levels = np.full(channel.shape, 110.0)
        levels[0, 0] = 100
        depth = np.ones(channel.shape)
        depth[0, 0] = 0.5
        sources = [self.emitter(1, 1)]
        prefix = deepcopy(sources)
        with self.assertRaisesRegex(
            ValueError, "no legal receiving-stage intake anchor"
        ):
            component_outlet_intakes(
                channel,
                depth,
                levels,
                [{"component": 1, "row": 0, "col": 0, "role": "map_edge"}],
                sources,
            )
        self.assertEqual(sources, prefix)
        self.assertEqual(levels[0, 0], 100)
        self.assertEqual(depth[0, 0], 0.5)

    def test_intake_budget_covers_per_record_packing_roundoff(self):
        channel = np.ones((3, 3), bool)
        depth = np.full(channel.shape, 2.0)
        sources = [self.emitter(1, 1, 0.1) for _ in range(10)]
        receipt = component_outlet_intakes(
            channel,
            depth,
            depth + 100,
            [{"component": 1, "row": 0, "col": 0, "role": "map_edge"}],
            sources,
        )[0]
        self.assertEqual(receipt["intake_records"], 2)
        self.assertEqual(receipt["summed_output_raw_settings"], 65540)
        self.assertEqual(receipt["declared_intake_raw_settings"], 65540)
        self.assertEqual(
            [round(sources[i]["capacity"] * 65535) for i in receipt["intake_indices"]],
            [65535, 5],
        )
        self.assertGreaterEqual(
            receipt["declared_intake_settings"],
            receipt["summed_packed_output_settings"],
        )

    def test_outlet_source_table_overflow_is_explicit_without_partial_append(self):
        channel = np.ones((3, 3), bool)
        depth = np.full(channel.shape, 2.0)
        sources = [self.emitter(1, 1)] * 65535
        with self.assertRaisesRegex(ValueError, "UInt16 source-table count"):
            component_outlet_intakes(
                channel,
                depth,
                depth + 100,
                [{"component": 1, "row": 0, "col": 0, "role": "map_edge"}],
                sources,
            )
        self.assertEqual(len(sources), 65535)
        sources[0]["output_capacity"] = 0
        with self.assertRaisesRegex(ValueError, "UInt16 source-table count"):
            cover_component_emitters(
                np.full(depth.shape, 98.0),
                depth,
                depth + 100,
                np.zeros_like(channel),
                channel,
                np.zeros_like(depth),
                np.ones(channel.shape, np.uint8),
                sources,
                depth.copy(),
            )
        self.assertEqual(len(sources), 65535)

    def test_packed_banks_clear_all_adjacent_water_after_footprint_expansion(self):
        rows, _ = np.indices((1081, 1081))
        ground = 100 + 30 * np.sin(rows / 80)
        ground[500:580, 544:550] = 30
        geometry = {
            "sq": {"lat": 0, "lon": 0, "scale": 1, "rotation": 0},
            "rivers": [{"name": "test river", "pts": [[0, -0.05], [0, 0.05]]}],
            "streams": [],
            "lakes": [],
            "riverAreas": [],
            "oceans": [],
            "undergroundWaterways": [
                {"brunnel": "tunnel", "pts": [[0.0006, -0.02], [0.0006, 0.02]]}
            ],
        }
        depth, report = hydrology(ground, ground.copy(), geometry)
        t = np.floor(ground * 64 + 0.5).astype(np.int32)
        w = np.floor(depth * 64 + 0.5).astype(np.int32)
        wet = w > 0
        rim = ndimage.maximum_filter(wet, size=3) & ~wet
        head = np.where(wet, t + w, -1000000)
        self.assertTrue(wet.any())
        self.assertTrue(rim.any())
        tunnel = ndimage.binary_dilation(
            raster(geometry["sq"], geometry["undergroundWaterways"]), iterations=2
        ) & ~raster(geometry["sq"], geometry["rivers"])
        self.assertTrue((rim & tunnel).any())
        self.assertFalse(wet[tunnel].any())
        self.assertGreater(len(report["sources"]), 1)
        self.assertGreaterEqual(
            int((t - ndimage.maximum_filter(head, size=3))[rim].min()), 128
        )
        self.assertEqual(report["joint_profile"]["packed_adverse_downstream_edges"], 0)
        self.assertEqual(report["away_land_changed_cells"], 0)
        self.assertEqual(
            len(report["functional_water_components"]),
            report["joint_profile"]["model_components"],
        )
        for component in report["functional_water_components"]:
            self.assertGreater(component["summed_output_settings"], 0)
            self.assertGreaterEqual(
                component["declared_intake_settings"],
                component["summed_output_settings"],
            )

    def test_chosen_source_gets_a_deep_broad_pool_without_filling_its_bed(self):
        ground = np.full((31, 31), 99.0)
        ground[15, 15] = 70
        before = ground.copy()
        depth = np.zeros_like(ground)
        level = np.full_like(ground, 100)
        source = {
            "position": [15 * 16 - 8640, 0, 8640 - 15 * 16],
            "target": 100,
            "class": "river",
            "capacity": 0.12,
            "output_capacity": 0.12,
        }
        source_pool(ground, depth, level, np.zeros(ground.shape, bool), source)
        self.assertGreaterEqual(
            source["footprint_pool"]["minimum_authored_core_depth_m"], 8
        )
        self.assertTrue(np.all(ground <= before))
        self.assertEqual(ground[15, 15], 70)
        self.assertEqual(depth[15, 15], 30)
        self.assertEqual(source["capacity"], 0.12)
        self.assertEqual(ground[0, 0], 99)

    def test_pool_does_not_cut_a_tunnel_gap_to_fit_a_large_source(self):
        ground = np.full((31, 31), 99.0)
        depth = np.zeros_like(ground)
        forbidden = np.zeros(ground.shape, bool)
        forbidden[:, 17] = True
        source = {
            "position": [15 * 16 - 8640, 0, 8640 - 15 * 16],
            "target": 100,
            "class": "river",
            "capacity": 0.12,
            "output_capacity": 0.12,
        }
        source_pool(ground, depth, np.full_like(ground, 100), forbidden, source)
        self.assertLess(source["capacity"], 0.12)
        self.assertEqual(source["requested_capacity"], 0.12)
        self.assertEqual(source["footprint_pool"]["tunnel_gap_cells_changed"], 0)
        np.testing.assert_array_equal(ground[forbidden], 99)
        np.testing.assert_array_equal(depth[forbidden], 0)
        self.assertGreaterEqual(
            source["footprint_pool"]["minimum_authored_core_depth_m"], 8
        )

    def test_channel_has_volume_and_sloping_sides(self):
        result = section(np.array([0, 16, 32, 48, 64]), 32, 8)
        self.assertEqual(result[0], 8)
        self.assertTrue(np.all(np.diff(result) <= 0))
        self.assertGreater(result[2], 1)
        self.assertEqual(result[-1], 0)

    def test_capacity_grows_with_local_catchment_and_is_bounded(self):
        values = [capacity(a, "river") for a in [0, 1, 10, 100, 100000]]
        self.assertEqual(values, sorted(values))
        self.assertGreater(values[0], 0)
        self.assertLessEqual(values[-1], 0.12)
        self.assertLess(capacity(0, "stream"), capacity(0, "river"))

    def test_trunk_and_branch_drain_to_the_same_low_edge(self):
        mask = np.zeros((9, 9), bool)
        mask[:, 4] = True
        mask[4, 4:] = True
        desired = np.full(mask.shape, 100.0)
        desired[0, 4] = 90
        stage, arc, outlets = stage_tree(
            mask, desired, np.zeros_like(mask), np.zeros_like(mask)
        )
        self.assertEqual(len(outlets), 1)
        self.assertEqual(outlets[0]["role"], "map_edge")
        self.assertTrue(np.all(np.isfinite(stage[mask])))
        self.assertGreater(stage[8, 4], stage[0, 4])
        self.assertGreater(arc[4, 8], arc[4, 4])

    def test_closed_captured_water_has_an_explicit_terminal(self):
        mask = np.zeros((7, 7), bool)
        mask[2:5, 2:5] = True
        level = np.full(mask.shape, 20.0)
        stage, _, outlets = stage_tree(mask, level, mask, np.zeros_like(mask))
        self.assertEqual(outlets[0]["role"], "closed_sink")
        np.testing.assert_array_equal(stage[mask], 20)

    def test_crossing_line_is_clipped_without_moving_it_to_a_corner(self):
        walk = source_walk(np.array([[-20.0, 540.0], [1100.0, 540.0]]))
        self.assertEqual(tuple(walk[0]), (540, 0))
        self.assertEqual(tuple(walk[-1]), (540, 1080))
        self.assertTrue(np.all(walk[:, 0] == 540))

    def test_sill_is_deepened_not_propagated_as_a_wall(self):
        mask = np.zeros((9, 9), bool)
        mask[:, 4] = True
        desired = np.full(mask.shape, 100.0)
        desired[0, 4] = 20
        desired[4, 4] = 400
        desired[6, 4] = 50
        stage, _, _ = stage_tree(
            mask, desired, np.zeros_like(mask), np.zeros_like(mask)
        )
        self.assertLess(stage[4, 4], 50)
        self.assertTrue(np.all(np.diff(stage[:, 4]) >= 0))

    def test_short_authored_join_respects_an_underground_gap(self):
        water = np.zeros((1081, 1081), bool)
        water[540, 530:534] = True
        water[540, 538:542] = True
        joined, links = join_nearby_water(water, np.zeros_like(water))
        self.assertEqual(len(links), 1)
        self.assertTrue(joined[540, 530:542].all())
        forbidden = np.zeros_like(water)
        forbidden[:, 535] = True
        blocked, links = join_nearby_water(water, forbidden)
        self.assertFalse(links)
        np.testing.assert_array_equal(blocked, water)

    def test_no_water_never_changes_measured_land(self):
        ground = np.full((1081, 1081), 100.0)
        before = ground.copy()
        geometry = {
            "sq": {"lat": 0, "lon": 0, "scale": 1, "rotation": 0},
            "rivers": [],
            "streams": [],
            "lakes": [],
            "riverAreas": [],
            "oceans": [],
        }
        depth, report = hydrology(ground, ground.copy(), geometry)
        np.testing.assert_array_equal(ground, before)
        self.assertFalse(depth.any())
        self.assertEqual(report["sources"], [])


if __name__ == "__main__":
    unittest.main()
