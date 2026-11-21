import unittest

from test_maintained_water_inventory import coord, line
from waterway_pieces import catalog


def geometry(streams):
    return {
        "sq": {"lon": 0, "lat": 0, "rotation": 0, "scale": 1},
        "rivers": [],
        "streams": streams,
        "lakes": [],
        "riverAreas": [],
        "oceans": [],
    }


class PieceCatalogTests(unittest.TestCase):
    def test_same_name_does_not_merge_source_rows_or_short_parts(self):
        rows = catalog(
            geometry(
                [
                    line((0, 0), (1, 0), name="same"),
                    line((300, 0), (332, 0), name="same"),
                ]
            )
        )["rows"]
        self.assertEqual([r["id"] for r in rows], ["streams:0", "streams:1"])
        self.assertTrue(all(r["status"] == "perennial_surface" for r in rows))
        self.assertEqual(len(rows[0]["clips"][0]["nodes_rc"]), 1)

    def test_multiple_clipped_parts_and_flags_remain_accounted(self):
        feature = {
            "pts": [
                coord(*p)
                for p in [
                    (-9000, 0),
                    (0, 0),
                    (9000, 0),
                    (9000, 400),
                    (0, 400),
                    (-9000, 400),
                ]
            ]
        }
        row = catalog(geometry([feature]))["rows"][0]
        self.assertEqual(len(row["clips"]), 2)
        self.assertTrue(
            all(c["start_clipped"] and c["end_clipped"] for c in row["clips"])
        )
        self.assertTrue(
            all(abs(v) <= 8640 for c in row["clips"] for p in c["points_xz"] for v in p)
        )

    def test_only_explicit_scope_exclusions_and_outside_evidence(self):
        rows = catalog(
            geometry(
                [
                    line((0, 0), (32, 0), intermittent=1),
                    line((0, 20), (32, 20), brunnel="tunnel"),
                    line((9000, 0), (9100, 0)),
                    line((0, 40), (32, 40), intermittent=0),
                ]
            )
        )["rows"]
        self.assertEqual(
            [r["status"] for r in rows],
            ["excluded", "excluded", "outside_square", "perennial_surface"],
        )
        self.assertTrue(rows[0]["clips"])

    def test_bad_and_missing_rows_are_unresolved_not_omitted(self):
        rows = catalog(geometry([None, {"pts": [[float("nan"), 0]]}]))["rows"]
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r["status"] == "unresolved" for r in rows))
        g = geometry([])
        del g["streams"]
        self.assertEqual(catalog(g)["rows"][0]["id"], "streams")
