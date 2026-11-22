import unittest
import numpy as np
from coastal_sea_stage_study import change_sea_stage
from crp import N, water_payload
from template import manager_tag


class SeaStageTests(unittest.TestCase):
    def payload(self, sea=90, sources=None):
        d = np.zeros(N, "<u2")
        d[123:127] = [32, 96, 384, 20000]
        return (
            b"prefix"
            + manager_tag("WaterSimulation")
            + water_payload(d, sources or [], 127, sea)
            + b"\x00\x00suffix"
        )

    def test_only_sea_field_changes_water_and_velocity_unchanged(self):
        original = self.payload()
        new, a, b = change_sea_stage(original)
        self.assertEqual(len(original), len(new))
        self.assertEqual((a["sea_level_m"], b["sea_level_m"]), (90, 0))
        self.assertEqual(a["sources"], b["sources"])
        self.assertTrue(np.array_equal(a["depth"], b["depth"]))
        for key in ["velocities", "frame", "tail"]:
            self.assertEqual(a[key], b[key])
        at = a["end"] - 12
        self.assertEqual(original[:at], new[:at])
        self.assertEqual(original[at + 4 :], new[at + 4 :])

    def test_no_tuning_or_source_addition_parent_is_accepted(self):
        with self.assertRaises(ValueError):
            change_sea_stage(self.payload(sea=89))
        with self.assertRaises(ValueError):
            change_sea_stage(
                self.payload(
                    sources=[
                        dict(
                            position=[0, 90, 0],
                            target=90,
                            capacity=0,
                            output_capacity=0,
                        )
                    ]
                )
            )
