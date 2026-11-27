import unittest
from unittest.mock import patch
from types import SimpleNamespace

import numpy as np

from channel_network import connect_channels, continuous_stage


class ChannelNetworkTest(unittest.TestCase):
    def test_an_isolated_unfed_stream_is_not_hand_filled(self):
        line = np.zeros((15, 15), bool)
        line[5, 5:10] = True
        empty = np.zeros_like(line)
        active, records, _ = connect_channels(
            line, empty, empty, empty, np.ones(line.shape)
        )
        self.assertFalse(active.any())
        self.assertEqual(records[0]["route"], "dry ground/marsh")

    def test_drainage_gap_can_join_an_existing_mapped_receiver(self):
        line = np.zeros((15, 15), bool)
        line[10, :] = True
        line[5:8, 7] = True
        empty = np.zeros_like(line)
        parent = np.full(line.shape, -1, dtype="i8")
        parent[5:10, 7] = np.arange(6, 11) * 15 + 7
        ground = np.zeros(line.shape)
        ground[5:8, 7] = [3, 2, 1]
        drainage = SimpleNamespace(
            parent=parent, filled_elevation=ground, area=np.ones(line.shape)
        )
        with patch("channel_network.priority_flood_drainage", return_value=drainage):
            active, records, _ = connect_channels(line, empty, empty, empty, ground)
        self.assertTrue(active[5:11, 7].all())
        self.assertEqual(
            sum(r["route"] == "connected to fed channel" for r in records), 1
        )

    def test_a_new_arbitrary_edge_outlet_is_not_allowed(self):
        line = np.zeros((15, 15), bool)
        line[10, :] = True
        line[5, 5:8] = True
        empty = np.zeros_like(line)
        parent = np.full(line.shape, -1, dtype="i8")
        parent[1:6, 5] = np.arange(0, 5) * 15 + 5
        drainage = SimpleNamespace(
            parent=parent,
            filled_elevation=np.ones(line.shape),
            area=np.ones(line.shape),
        )
        with patch("channel_network.priority_flood_drainage", return_value=drainage):
            active, records, _ = connect_channels(
                line, empty, empty, empty, np.ones(line.shape)
            )
        self.assertFalse(active[5, 5:8].any())
        self.assertEqual(records[0]["route"], "dry ground/marsh")

    def test_a_low_tributary_cap_lowers_ancestors_not_its_bank(self):
        mask = np.zeros((9, 9), bool)
        mask[4, :] = True
        mask[1:5, 4] = True
        cap = np.full(mask.shape, 100.0)
        cap[4, 0] = 20
        cap[4, 1:5] = [60, 70, 80, 90]
        cap[1, 4] = 50
        stage, reports = continuous_stage(mask, cap)
        self.assertTrue((stage[mask] <= cap[mask]).all())
        self.assertTrue((np.diff(stage[4, :5]) >= 0).all())
        self.assertTrue((np.diff(stage[1:5, 4]) <= 0).all())
        self.assertEqual(stage[4, 4], 50)
        self.assertEqual(reports[0]["status"], "continuous receiving tree")


if __name__ == "__main__":
    unittest.main()
