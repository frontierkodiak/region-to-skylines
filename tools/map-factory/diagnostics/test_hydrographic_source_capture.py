import unittest
import numpy as np

from hydrographic_source_capture import complete_ids, geographic, rectangle
from prepare import pixel


class CaptureTests(unittest.TestCase):
    def test_frame_inverse_covers_original_rotated_square_not_new_neighborhood(self):
        sq = {"lon": 153, "lat": -27.4, "rotation": 23, "scale": 1.25}
        box = rectangle(sq)
        for x, z in [
            (-8640, -8640),
            (-8640, 8640),
            (8640, 8640),
            (8640, -8640),
            (0, 0),
        ]:
            lon, lat = geographic(sq, [x, z])
            c, r = pixel(sq, [lon, lat])
            np.testing.assert_allclose(
                [c, r], [x / 16 + 540, 540 - z / 16], atol=1e-7, rtol=0
            )
            self.assertTrue(
                box["xmin"] <= lon <= box["xmax"] and box["ymin"] <= lat <= box["ymax"]
            )

    def test_missing_duplicate_or_extra_feature_is_not_repaired(self):
        def f(ids):
            return [{"attributes": {"OBJECTID": n}} for n in ids]

        for ids in [[1], [1, 1], [1, 3], [1, 2, 3]]:
            with self.assertRaises(ValueError):
                complete_ids([1, 2], f(ids))
        complete_ids([1, 2], f([2, 1]))
        complete_ids([], [])
        with self.assertRaises(ValueError):
            complete_ids([1], f([True]))


if __name__ == "__main__":
    unittest.main()
