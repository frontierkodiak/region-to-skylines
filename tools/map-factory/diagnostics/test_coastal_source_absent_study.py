import unittest

import numpy as np

from coastal_source_absent_study import remove_records
from crp import N, water_payload
from template import manager_tag
from water_diagnostics import decode_water


class SourceAbsentTests(unittest.TestCase):
    def payload(self, output=0):
        depth = np.zeros(N, "<u2")
        depth[12:16] = [32, 96, 384, 1]
        sources = [
            dict(position=[i, 90, -i], target=90, capacity=0, output_capacity=output)
            for i in range(167)
        ]
        return (
            b"unchanged-prefix"
            + manager_tag("WaterSimulation")
            + water_payload(depth, sources, 123, 90)
            + b"\x00\x00unchanged-suffix"
        )

    def test_all_source_records_removed_but_water_velocity_and_trailer_unchanged(self):
        original = self.payload()
        new, before, after = remove_records(original)
        self.assertEqual(len(original) - len(new), 43 * 167)
        self.assertEqual(len(before["sources"]), 167)
        self.assertEqual(after["sources"], [])
        self.assertTrue(np.array_equal(before["depth"], after["depth"]))
        for key in ["frame", "sea_level_m", "velocities", "tail"]:
            self.assertEqual(before[key], after[key])
        self.assertTrue(new.startswith(b"unchanged-prefix"))
        self.assertTrue(new.endswith(b"unchanged-suffix"))

    def test_not_a_positive_rate_or_already_empty_parent(self):
        with self.assertRaisesRegex(ValueError, "rate-zero"):
            remove_records(self.payload(output=1 / 65535))
        empty, _, _ = remove_records(self.payload())
        with self.assertRaisesRegex(ValueError, "Exact167"):
            remove_records(empty)

    def test_no_source_records_does_not_change_or_delete_sea_stage(self):
        new, _, _ = remove_records(self.payload())
        self.assertEqual(decode_water(new)["sea_level_m"], 90)
        self.assertIn(b"unchanged-suffix", new)


if __name__ == "__main__":
    unittest.main()
