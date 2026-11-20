"""Target-reader behavior using real place_model writers and committed models."""

import gzip
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pyarrow as pa
from PIL import Image
from place_input import Frame, compile_geometry, export, preprocess, sample_grid
from place_model import (
    SCHEMAS,
    provenance,
    read_manifest,
    read_table,
    write_grid,
    write_manifest,
    write_table,
)
from prepare import pixel
from pyproj import Transformer
from region import raster
from shapely.geometry import LineString, Polygon
from surface_water import surface_geometry

ROOT = Path(__file__).resolve().parent
PLACES = Path(
    os.environ.get(
        "PLACE_MODEL_PLACES",
        ROOT.parents[1].parent / "agentic-research-workbench/place-model/places",
    )
)


def model(
    root,
    *,
    water=(),
    roads=(),
    connectors=(),
    source_water=(),
    source_segment=(),
    sampling="vertex",
):
    evidence = provenance("fixture", "synthetic source measurements")
    layers = {}
    for name, rows in [
        ("hydrography", water),
        ("transportation_segments", roads),
        ("transportation_connectors", connectors),
        ("buildings", []),
        ("trees", []),
    ]:
        layers[name] = write_table(
            root, name, [{**row, "provenance": evidence} for row in rows]
        )
    bounds = [100, 200, 2100, 4200]
    fractions = (
        np.linspace(0, 1, 5) if sampling == "vertex" else (np.arange(5) + 0.5) / 5
    )
    x, z = np.meshgrid(100 + fractions * 2000, 200 + fractions * 4000)
    layers["terrain"] = write_grid(
        root, "terrain", 1500 + x * 0.005 + z * 0.01, bounds, evidence, sampling
    )
    layers["landcover"] = write_grid(
        root,
        "landcover",
        np.array([[10, 20], [40, 50]], "u1"),
        bounds,
        evidence,
        "cell",
    )
    for name, rows in [
        ("source_water", source_water),
        ("source_segment", source_segment),
    ]:
        if rows:
            layers[name] = write_table(
                root,
                name,
                [
                    {
                        "id": ident,
                        "properties": json.dumps(props),
                        "provenance": evidence,
                    }
                    for ident, props in rows
                ],
                schema=pa.schema(
                    [
                        ("id", pa.string()),
                        ("properties", pa.string()),
                        ("provenance", SCHEMAS["hydrography"].field("provenance").type),
                    ]
                ),
            )
    return write_manifest(
        root,
        {
            "schema": "polli.place/0",
            "id": "synthetic",
            "title": "Synthetic",
            "access": "public",
            "frame": {
                "source_crs": "EPSG:2264",
                "origin": [2_000_000, 700_000],
                "horizontal_unit_metres": 1200 / 3937,
                "axes": ["east", "up", "south"],
                "vertical_datum": "synthetic absolute datum",
                "elevation_origin_metres": 1400,
            },
            "extent": bounds,
            "tiling": {"tile_size_metres": 512},
            "sources": {
                "fixture": {
                    "url": "https://example.org/synthetic",
                    "license": "CC0",
                    "access": "public",
                }
            },
            "layers": layers,
            "presentation": {},
        },
    )


class PlaceInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.place = self.root / "model"

    def test_axes_feet_origin_crop_and_elevation_datum(self):
        manifest = model(self.place)
        frame = Frame(manifest)
        np.testing.assert_equal(frame.crop, [100, 1200, 2100, 3200])
        self.assertAlmostEqual(frame.report()["game_metres_per_source_metre"], 8.64)
        unit = manifest["frame"]["horizontal_unit_metres"]
        expected = Transformer.from_crs(2264, 4326, always_xy=True).transform(
            2_000_000 + 1100 / unit, 700_000 - 2200 / unit
        )
        np.testing.assert_allclose(frame.geographic(1100, 2200), expected, atol=1e-10)
        corners = frame.points([(100, 1200), (2100, 1200), (2100, 3200), (100, 3200)])
        np.testing.assert_allclose(
            [pixel(frame.sq, p) for p in corners],
            [[0, 0], [1080, 0], [1080, 1080], [0, 1080]],
            atol=1e-7,
        )
        png, geometry, banks, landcover = preprocess(self.place, self.root / "inputs")
        geo = json.loads(geometry.read_text())
        self.assertGreater(
            geo["fit"]["base"], 1500
        )  # not 100 after a second datum shift
        self.assertEqual(
            geo["placeInput"]["vertical_datum"], "synthetic absolute datum"
        )
        bank = np.fromfile(banks, "<f4").reshape(1081, 1081)
        self.assertGreater(bank[540, -1], bank[540, 0])
        self.assertGreater(bank[-1, 540], bank[0, 540])
        absolute_center = 1500 + 1100 * 0.005 + 2200 * 0.01
        self.assertAlmostEqual(
            bank[540, 540],
            (absolute_center - geo["fit"]["base"]) * geo["fit"]["verticalScale"] + 50,
            places=3,
        )
        np.testing.assert_allclose(
            np.asarray(Image.open(png)) * (1024 / 65535), bank, atol=1024 / 65535
        )
        land = np.frombuffer(gzip.decompress(landcover.read_bytes()), "u1").reshape(
            1728, 1728
        )
        self.assertEqual(
            [int(land[y, x]) for y, x in [(0, 0), (0, -1), (-1, 0), (-1, -1)]],
            [10, 20, 40, 50],
        )

    def test_cell_terrain_is_inscribed_in_sample_support(self):
        manifest = model(self.place, sampling="cell")
        frame = Frame(manifest)
        np.testing.assert_equal(frame.crop, [300, 1400, 1900, 3000])
        desc = manifest["layers"]["terrain"]
        x, z = np.meshgrid(np.linspace(300, 1900, 5), np.linspace(600, 3800, 5))
        values = 1500 + x * 0.005 + z * 0.01
        sampled = sample_grid(values, desc, frame.crop, 3)
        np.testing.assert_allclose(
            sampled,
            [
                [1515.5, 1519.5, 1523.5],
                [1523.5, 1527.5, 1531.5],
                [1531.5, 1535.5, 1539.5],
            ],
        )
        with self.assertRaisesRegex(ValueError, "coverage"):
            sample_grid(values, desc, manifest["extent"], 3)

    def test_full_graph_identity_and_scoped_source_properties_survive(self):
        rows = [
            {
                "id": "ground",
                "geometry": LineString([(0, 2200), (2200, 2200)]).wkb,
                "connectors": [
                    {"connector_id": "west", "at": 0.0},
                    {"connector_id": "ground-middle", "at": 0.5},
                    {"connector_id": "east", "at": 1.0},
                ],
                "class": "7",
                "width": 6.6,
                "bridge": False,
                "tunnel": False,
                "level": 0,
            },
            {
                "id": "bridge",
                "geometry": LineString([(1100, 0), (1100, 4400)]).wkb,
                "connectors": [
                    {"connector_id": "north", "at": 0.0},
                    {"connector_id": "bridge-middle", "at": 0.5},
                    {"connector_id": "south", "at": 1.0},
                ],
                "class": "residential",
                "width": 8.0,
                "bridge": True,
                "tunnel": True,
                "level": 1,
            },
        ]
        connectors = [
            {"id": name, "x": x, "z": z}
            for name, x, z in [
                ("west", 0, 2200),
                ("ground-middle", 1100, 2200),
                ("east", 2200, 2200),
                ("north", 1100, 0),
                ("bridge-middle", 1100, 2200),
                ("south", 1100, 4400),
            ]
        ]
        scoped = {
            "road_flags": [{"values": ["is_tunnel"], "between": [0.25, 0.5]}],
            "level_rules": [{"value": 2, "between": [0.25, 0.5]}],
        }
        manifest = model(
            self.place,
            roads=rows,
            connectors=connectors,
            source_segment=[("bridge", scoped)],
        )
        geo = compile_geometry(self.place, manifest, Frame(manifest))
        for before, after in zip(rows, geo["roads"]):
            for key in [
                "id",
                "connectors",
                "class",
                "bridge",
                "tunnel",
                "level",
                "width",
            ]:
                self.assertEqual(before[key], after[key])
        self.assertEqual(len(geo["roadConnectors"]), 6)
        self.assertEqual(geo["roads"][1]["sourceFeature"]["properties"], scoped)
        self.assertLess(
            pixel(geo["sq"], geo["roads"][0]["pts"][0])[0], 0
        )  # not clipped, refs still original
        middle = [c for c in geo["roadConnectors"] if c["id"].endswith("middle")]
        self.assertEqual([(c["x"], c["z"]) for c in middle], [(0, 0), (0, 0)])
        self.assertNotEqual(middle[0]["id"], middle[1]["id"])

    def test_water_lines_holes_and_explicit_culvert_are_not_conflated(self):
        shell = [(300, 1400), (1900, 1400), (1900, 3000), (300, 3000)]
        hole = [(900, 2000), (1300, 2000), (1300, 2400), (900, 2400)]
        water = [
            {
                "id": "area",
                "geometry": Polygon(shell, [hole]).wkb,
                "height": 1527.5,
                "kind": "surface",
            },
            {
                "id": "line",
                "geometry": LineString([(100, 1700), (2100, 1700)]).wkb,
                "height": 1520,
                "kind": "river",
            },
            {
                "id": "culvert",
                "geometry": LineString([(100, 1800), (2100, 1800)]).wkb,
                "height": 1520,
                "kind": "stream",
            },
        ]
        properties = {
            "source_tags": [["tunnel", "culvert"]],
            "level": -1,
            "is_intermittent": True,
        }
        manifest = model(
            self.place, water=water, source_water=[("culvert", properties)]
        )
        geo = compile_geometry(self.place, manifest, Frame(manifest))
        self.assertEqual(len(geo["riverAreas"]), 1)
        self.assertEqual(len(geo["lakes"]), 0)
        self.assertEqual(len(geo["rivers"]), 1)
        self.assertEqual(len(geo["undergroundWaterways"]), 1)
        underground = geo["undergroundWaterways"][0]
        self.assertEqual(underground["sourceFeature"]["properties"], properties)
        self.assertEqual(underground["height"], 1520)
        self.assertEqual(surface_geometry(geo)[1]["underground_pieces"], 1)
        mask = raster(geo["sq"], geo["riverAreas"], polygons=True)
        self.assertFalse(mask[540, 540])
        self.assertTrue(mask[250, 250])
        # Real carving helpers also preserve the large island in the PNG.
        png, _geometry, banks, _ = preprocess(self.place, self.root / "water-inputs")
        game = np.asarray(Image.open(png)) * (1024 / 65535)
        bank = np.fromfile(banks, "<f4").reshape(1081, 1081)
        self.assertLess(abs(game[540, 540] - bank[540, 540]), 0.02)
        self.assertGreater(bank[800, 250] - game[800, 250], 1)

    def test_invalid_checksum_fails_before_any_output(self):
        model(self.place)
        with (self.place / "terrain.arrow").open("ab") as stream:
            stream.write(b"corrupt")
        with self.assertRaisesRegex(ValueError, "checksum"):
            preprocess(self.place, self.root / "must-not-exist")
        self.assertFalse((self.root / "must-not-exist").exists())

    def test_undeclared_water_role_stops_instead_of_inventing_semantics(self):
        manifest = model(
            self.place,
            water=[
                {
                    "id": "ambiguous",
                    "geometry": LineString([(100, 1200), (2100, 3200)]).wkb,
                    "height": 1500,
                    "kind": "unknown",
                }
            ],
        )
        with self.assertRaisesRegex(ValueError, "needs canonical watercourse kind"):
            compile_geometry(self.place, manifest, Frame(manifest))

    def test_executable_inputs_cli_and_existing_generator(self):
        model(self.place)
        # Use the current uv interpreter's environment, including --with model.
        cli = subprocess.run(
            [
                sys.executable,
                str(ROOT / "place_input.py"),
                str(self.place),
                str(self.root / "cli"),
                "--inputs-only",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(cli.returncode, 0, cli.stderr)
        self.assertEqual(
            json.loads(cli.stdout)["place_input"]["game_metres_per_source_metre"], 8.64
        )
        report, code = export(self.place, self.root / "export")
        self.assertIn(code, [0, 5])
        self.assertFalse(report["generation"]["in_game_verified"])
        self.assertIn("calibration", report["water_risk"])
        self.assertEqual(bool(list((self.root / "export").rglob("*.crp"))), code == 0)
        self.assertEqual(report["exported"], code == 0)

    def test_unavailable_water_check_cannot_be_overridden(self):
        model(self.place)
        unavailable = {
            "schema": 1,
            "status": "declined",
            "reasons": ["Synthetic unavailable-check fixture"],
        }
        with patch("water_risk.assess", return_value=unavailable):
            report, code = export(
                self.place, self.root / "declined", allow_water_risk=True
            )
        self.assertEqual(code, 5)
        self.assertFalse(list((self.root / "declined").rglob("*.crp")))
        self.assertIsNone(report["generation"]["package"]["output"])
        self.assertEqual(report["water_risk"]["reasons"], unavailable["reasons"])

    def test_export_receipts_reference_delivered_package_not_quarantine(self):
        model(self.place)
        # This isolates delivery mechanics, not the water classifier. Existing
        # classifier behavior is exercised by the unmocked generation test.
        lower = {
            "schema": 1,
            "status": "lower",
            "reasons": [],
            "calibration": {"squares": 5},
            "features": {"synthetic": True},
            "outside_calibration": [],
            "risks": {k: {"level": "not_flagged"} for k in ["flood", "drying"]},
        }
        output = self.root / "delivered"
        with patch("water_risk.assess", return_value=lower):
            report, code = export(self.place, output)
        self.assertEqual(code, 0)
        crp = Path(report["generation"]["package"]["output"])
        self.assertTrue(crp.is_file())
        self.assertEqual(crp.parent, (output / "generated").resolve())
        for name in ["generation.json", "resources.json"]:
            self.assertEqual(
                json.loads((output / "generated" / name).read_text())["package"][
                    "output"
                ],
                str(crp),
            )
        with self.assertRaisesRegex(ValueError, "empty"):
            export(self.place, output)


class CommittedModelsTests(unittest.TestCase):
    @unittest.skipUnless(
        PLACES.is_dir(),
        "set PLACE_MODEL_PLACES to the pinned workbench places directory",
    )
    def test_real_committed_models_compile_with_no_acquisition(self):
        for name, side in [
            ("amherst-center", 2000),
            ("central-boston", 2000),
            ("asheville", 6000),
            ("charleston-center", 2000),
        ]:
            with self.subTest(place=name), tempfile.TemporaryDirectory() as temporary:
                place = PLACES / name
                paths = preprocess(place, Path(temporary))
                self.assertTrue(all(p.exists() for p in paths))
                geometry = json.loads(paths[1].read_text())
                self.assertEqual(geometry["placeInput"]["source_side_metres"], side)
                self.assertEqual(geometry["placeInput"]["game_side_metres"], 17280)
                m = read_manifest(place)
                self.assertEqual(
                    len(geometry["roads"]),
                    m["layers"]["transportation_segments"]["records"],
                )
                self.assertEqual(
                    len(geometry["roadConnectors"]),
                    m["layers"]["transportation_connectors"]["records"],
                )
                self.assertEqual(
                    [r["connectors"] for r in geometry["roads"]],
                    read_table(place, "transportation_segments")[
                        "connectors"
                    ].to_pylist(),
                )
                if name == "amherst-center":
                    self.assertEqual(len(geometry["undergroundWaterways"]), 4)
                if name == "asheville":
                    self.assertEqual(
                        geometry["placeInput"]["crop_local_metres"],
                        [-3000, -4000, 3000, 2000],
                    )
                    self.assertEqual(
                        geometry["rivers"], []
                    )  # no graph recovered from triangles


if __name__ == "__main__":
    unittest.main()
