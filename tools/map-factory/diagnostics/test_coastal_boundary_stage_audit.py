import unittest
from coastal_boundary_stage_audit import stratum_id, boundary_strip_ids


class BoundaryAxesTests(unittest.TestCase):
    def test_boundary_strips_hold_control_far_and_vary_boundary(self):
        self.assertEqual(boundary_strip_ids(), [67, 71, 75, 79])
        self.assertNotEqual(boundary_strip_ids(), [76, 77, 78, 79])

    def test_equal_far_axes_primary_domain_stays79(self):
        self.assertEqual(stratum_id(ocean=1, bed=0, boundary=3, control=3), 79)

    def test_metadata_axis_coordinates_roundtrip_all128(self):
        for i in range(128):
            self.assertEqual(
                stratum_id(
                    ocean=i // 64, bed=i // 16 % 4, boundary=i // 4 % 4, control=i % 4
                ),
                i,
            )

    def test_invalid_axes_are_not_silently_wrapped(self):
        with self.assertRaises(ValueError):
            stratum_id(ocean=1, bed=0, boundary=4, control=0)
