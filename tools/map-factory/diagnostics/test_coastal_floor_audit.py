import unittest

import numpy as np

from coastal_floor_audit import connected, difference, indices, source_domains


class CoastalFloorTests(unittest.TestCase):
    def test_native_orientation_and_probe_edges(self):
        rows, cols = indices([{"x": -8640, "z": -8640}, {"x": 8640, "z": 8640}])
        self.assertEqual(rows.tolist(), [0, 1080])
        self.assertEqual(cols.tolist(), [0, 1080])
        with self.assertRaises(ValueError):
            indices([{"x": 8641, "z": 0}])

    def test_open_zero_margin_path_does_not_prove_half_metre_head(self):
        floor = np.full((7, 7), 6400, np.uint16)
        floor[3, :] = 5750
        ocean = np.zeros_like(floor, bool)
        ocean[3, 0] = True
        zero, _ = connected(floor, ocean, 90, 0, 4)
        half, _ = connected(floor, ocean, 90, 0.5, 4)
        self.assertTrue(zero[3, 6])
        self.assertFalse(half[3, 6])

    def test_source_scope_keeps_explicit_tunnel_and_stream_rows(self):
        geometry = {
            "sq": {"lon": 0, "lat": 0, "rotation": 0, "scale": 1},
            "rivers": [
                {"name": "Main Drain", "pts": [[0, 0], [0.001, 0]], "brunnel": "tunnel"}
            ],
            "streams": [{"name": "Bulimba Creek", "pts": [[0, 0], [0.001, 0]]}],
        }
        entries = [entry for entry, _ in source_domains(geometry)]
        self.assertEqual([e["id"] for e in entries], ["rivers:0", "streams:0"])
        self.assertEqual(
            [e["scope"] for e in entries], ["excluded", "perennial_surface"]
        )

    def test_signed_floor_change_is_not_raw_terrain_identity(self):
        result = difference(np.array([65, 63]), np.array([64, 64]))
        self.assertEqual(result["different_nodes"], 2)
        self.assertEqual(result["min_delta_m"], -1 / 64)
        self.assertEqual(result["max_delta_m"], 1 / 64)
