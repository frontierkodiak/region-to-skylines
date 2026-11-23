"""Coordinate/nodata and cache checks for canopy area sampling; no network."""

import tempfile
import unittest
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

import canopy
import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import Affine
from rasterio.warp import transform


class RasterSamplingTests(unittest.TestCase):
    def test_projected_rotated_raster_mask_and_zero(self):
        """An affine-rotated projected source must not transpose/shift samples."""
        affine = (
            Affine.translation(100000, 200000)
            @ Affine.rotation(27)
            @ Affine.scale(5, -5)
        )
        raw = np.array([[0, 7, 255], [13, 29, 41]], dtype=np.uint8)
        with MemoryFile() as memory:
            with memory.open(
                driver="GTiff",
                width=3,
                height=2,
                count=1,
                dtype="uint8",
                crs="EPSG:3857",
                transform=affine,
            ) as dst:
                dst.write(raw, 1)
                mask = np.full((2, 3), 255, np.uint8)
                mask[1, 1] = 0  # A real non-255 value hidden by the cloud mask.
                dst.write_mask(mask)
            with memory.open() as src:
                cols = np.array([0.5, 1.5, 2.5, 0.5, 1.5, 2.5, -0.5])
                rows = np.array([0.5, 0.5, 0.5, 1.5, 1.5, 1.5, 0.5])
                x, y = affine @ (cols, rows)
                lon, lat = transform("EPSG:3857", "EPSG:4326", x.tolist(), y.tolist())
                values, window = canopy._sample_dataset(
                    src, np.array(lon), np.array(lat)
                )
        np.testing.assert_equal(values, [0, 7, np.nan, 13, np.nan, 41, np.nan])
        self.assertEqual(values.dtype, np.float32)
        self.assertEqual(window, [0, 0, 3, 2])

    def test_rotated_square_samples_real_projected_raster_north_first(self):
        """At +90° game north is geographic east, not geographic north."""
        sq = {"lon": 0.01, "lat": 0.01, "rotation": 90, "scale": 80 / 17280}
        affine = Affine.translation(1000, 1250) @ Affine.scale(2, -2)
        raw = np.arange(160 * 160, dtype=np.float32).reshape(160, 160) / 1000
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.tif"
            with rasterio.open(
                path,
                "w",
                driver="GTiff",
                width=160,
                height=160,
                count=1,
                dtype="float32",
                crs="EPSG:3857",
                transform=affine,
            ) as dst:
                dst.write(raw, 1)

            def local_tile(key, lon, lat, step_m):
                with rasterio.open(path) as src:
                    values, _ = canopy._sample_dataset(src, lon, lat)
                return values, {"tile": key, "status": "read"}

            with patch.object(canopy, "_read_tile", side_effect=local_tile):
                heights, receipt = canopy.sample(sq, 20)
            # Independently construct +90° centres: east=z, north=-x.
            a, e2 = 6378137, 0.00669437999014
            w = 1 - e2 * np.sin(np.deg2rad(sq["lat"])) ** 2
            m = a * (1 - e2) / w**1.5
            nc = a / np.sqrt(w) * np.cos(np.deg2rad(sq["lat"]))
            east, north = np.meshgrid(
                np.array([30, 10, -10, -30]), np.array([30, 10, -10, -30])
            )
            east = east.T
            north = north.T
            # east changes by row, north changes by column in this rotated frame.
            lon = sq["lon"] + np.rad2deg(east / nc)
            lat = sq["lat"] + np.rad2deg(north / m)
            xp, yp = transform(
                "EPSG:4326", "EPSG:3857", lon.ravel().tolist(), lat.ravel().tolist()
            )
            cols, rows = (~affine) @ (np.array(xp), np.array(yp))
            expected = raw[
                np.floor(rows).astype(int), np.floor(cols).astype(int)
            ].reshape(4, 4)
        np.testing.assert_equal(heights, expected)
        self.assertGreater(heights[0, 0], heights[3, 0])
        self.assertGreater(heights[0, 3], heights[0, 0])
        self.assertEqual(receipt["shape"], [4, 4])
        self.assertAlmostEqual(receipt["step_m"], 20)


class SampleContractTests(unittest.TestCase):
    SQ: ClassVar[dict] = {
        "lat": 35.58,
        "lon": -82.555,
        "rotation": 0,
        "scale": 40 / 17280,
    }

    def test_quadkey_leading_zeroes(self):
        self.assertEqual(canopy.quadkey(0, 0), "0000000000")
        self.assertEqual(canopy.quadkey(277, 403), "0320030123")

    def test_cached_samples_preserve_unknown_and_valid_zero(self):
        def tile(key, lon, lat, step_m):
            return np.array([0, np.nan, 12, 27], np.float32), {
                "tile": key,
                "status": "read",
            }

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(canopy, "_read_tile", side_effect=tile) as read:
                first, receipt = canopy.sample(self.SQ, 20, cache_dir=tmp)
                second, cached = canopy.sample(self.SQ, 20, cache_dir=tmp)
                self.assertEqual(read.call_count, 1)
            self.assertEqual(len(list(Path(tmp).glob("*.npz"))), 1)
        np.testing.assert_equal(first, second)
        self.assertEqual(receipt["coverage_fraction"], 0.75)
        self.assertFalse(receipt["cache_hit"])
        self.assertTrue(cached["cache_hit"])

    def test_read_failure_is_unknown_and_not_cached(self):
        def fail(key, lon, lat, step_m):
            return np.full(lon.shape, np.nan, np.float32), {
                "tile": key,
                "status": "read_error",
            }

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(canopy, "_read_tile", side_effect=fail):
                heights, receipt = canopy.sample(self.SQ, 20, cache_dir=tmp)
            self.assertEqual(list(Path(tmp).iterdir()), [])
        self.assertTrue(np.isnan(heights).all())
        self.assertEqual(receipt["status"], "unavailable")
        self.assertEqual(receipt["coverage_fraction"], 0)

    def test_spacing_and_extent_validation(self):
        for step in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                canopy.sample(self.SQ, step)
        with self.assertRaises(ValueError):
            canopy.sample({**self.SQ, "lat": 90})


if __name__ == "__main__":
    unittest.main()
