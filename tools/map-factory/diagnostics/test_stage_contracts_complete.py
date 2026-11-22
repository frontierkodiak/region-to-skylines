import unittest

from stage_contracts_complete import ocean_masks
from test_maintained_water_inventory import body


class OceanTests(unittest.TestCase):
    def test_literal_ocean_row_is_not_omitted_from_source_restriction(self):
        geometry = {
            "sq": {"lon": 0, "lat": 0, "rotation": 0, "scale": 1},
            "oceans": [
                body(-64, -64, 64, 64),
                body(128, 128, 256, 256, intermittent=True),
            ],
        }
        masks = ocean_masks(geometry)
        self.assertEqual([r[0] for r in masks], ["oceans:0"])
        self.assertTrue(masks[0][1][540, 540])
        self.assertFalse(masks[0][1][0, 0])


if __name__ == "__main__":
    unittest.main()
