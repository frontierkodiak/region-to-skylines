"""web.py's copies of rasterio's window arithmetic must give rasterio's answers.

The website runs the writer under Pyodide, which has no GDAL, so web.py repeats the few
lines of rasterio 1.5.2 and affine 3.0.1 that landcover.sample relies on. Compare them
against the real libraries on WorldCover-like transforms and the reference squares.
"""

import gzip
import json
import unittest
from pathlib import Path

import numpy as np
from affine import Affine
from rasterio import windows

import web

ROOT = Path(__file__).resolve().parent


class WindowArithmeticTests(unittest.TestCase):
    def test_from_bounds_and_window_transform_match_rasterio(self):
        rng = np.random.default_rng(0)
        res = 1 / 12000  # WorldCover's 3-degree tiles of 36000 pixels
        for lat0, lon0 in [
            (33, -84),
            (45, 9),
            (-24, -45),
            (39, -81),
            (30, -81),
            (-3, 141),
        ]:
            t = Affine(res, 0.0, float(lon0), 0.0, -res, float(lat0 + 3))
            for _ in range(200):
                w, s = lon0 + rng.uniform(0, 2.7), lat0 + rng.uniform(0, 2.7)
                e, n = w + rng.uniform(0.01, 0.3), s + rng.uniform(0.01, 0.3)
                ref = windows.from_bounds(w, s, e, n, t).round_offsets().round_lengths()
                mine = web._from_bounds(w, s, e, n, tuple(t)[:6])
                self.assertEqual(
                    mine, (ref.col_off, ref.row_off, ref.width, ref.height)
                )
                rt = windows.transform(ref, t)
                x, y = (
                    mine[0] * t.a + mine[1] * t.b + t.c,
                    mine[0] * t.d + mine[1] * t.e + t.f,
                )
                got = web._matmul((1.0, 0.0, x - t.c, 0.0, 1.0, y - t.f), tuple(t)[:6])
                self.assertEqual(got, tuple(rt)[:6])

    def test_plan_uses_landcover_tiles(self):
        for slug in ["asheville", "rio"]:
            geometry = json.loads(
                gzip.decompress(
                    (ROOT / "fixtures" / slug / "geometry.json.gz").read_bytes()
                )
            )
            sq = {k: geometry["sq"][k] for k in ["lon", "lat", "rotation", "scale"]}
            tiles = json.loads(web.landcover_plan(json.dumps(sq)))
            self.assertEqual(tiles, sorted(set(tiles)))
            self.assertTrue(tiles)


if __name__ == "__main__":
    unittest.main()
