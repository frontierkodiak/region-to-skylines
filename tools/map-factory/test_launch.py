"""Launch previews and controls, against unrelated frozen regions."""

import gzip
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from crp import begin_tag_size, read_package
from template import decode_array, manager_tag
from generate import generate
from map_metadata import listing_fields
from region import start_area

ROOT = Path(__file__).parent


class LaunchTests(unittest.TestCase):
    def test_preview_and_connection_flags_across_regions(self):
        for slug in ["asheville", "innsbruck"]:
            with self.subTest(region=slug), tempfile.TemporaryDirectory() as temp:
                out = Path(temp)
                case = ROOT / "fixtures" / slug
                geometry = json.loads(
                    gzip.decompress((case / "geometry.json.gz").read_bytes())
                )
                geometry["sq"]["disabledConnections"] = ["road_in", "rail_out"]
                geo = out / "geometry-input.json"
                geo.write_text(json.dumps(geometry))
                banks = out / "banks.f32"
                banks.write_bytes(gzip.decompress((case / "banks.f32.gz").read_bytes()))
                receipt = generate(
                    case / "input.png",
                    geo,
                    out / "map",
                    banks,
                    landcover=case / "landcover.u8.gz",
                )
                path = out / "map"
                listing = listing_fields(
                    path / (receipt["preparation"]["map_id"] + ".crp")
                )

                _, assets = read_package(
                    (path / (receipt["preparation"]["map_id"] + ".crp")).read_bytes()
                )
                data = next(a["payload"] for a in assets if a["kind"] == 52)
                at = data.find(manager_tag("BuildingManager"))
                flags, _ = decode_array(
                    data, 49151, at + begin_tag_size(data, at, "BuildingManager"), 4
                )
                spec = json.loads(
                    (ROOT / "templates/native-corridors.json").read_text()
                )
                rail = set(
                    next(r["nodes"] for r in spec["routes"] if r["kind"] == "rail")
                )
                rail_buildings = [
                    b["id"] for b in spec["buildings"] if b["node"] in rail
                ]
                self.assertTrue(rail_buildings)
                self.assertTrue(
                    all(int(flags[b - 1]) & 0x40 == 0 for b in rail_buildings)
                )
                self.assertEqual(listing["incomingTrainTracks"], 2)
                self.assertEqual(listing["outgoingTrainTracks"], 0)
                self.assertEqual(listing["incomingRoads"], 0)
                self.assertEqual(listing["outgoingRoads"], 1)
                self.assertNotEqual(listing["buildableArea"], 74)
                with Image.open(path / "preview.png") as image:
                    self.assertEqual(image.size, (1200, 1510))
                    self.assertGreater(np.asarray(image).std(), 20)

    def test_start_override_selects_and_rejects_unbuildable_tiles(self):
        ground = np.ones((1081, 1081)) * 100
        depth = np.zeros_like(ground)
        for tile in [0, 12, 24]:
            geo = {
                "sq": {"lon": 0, "lat": 0, "rotation": 0, "scale": 1, "startTile": tile}
            }
            self.assertEqual(start_area(ground, depth, geo)["index"], tile)
            with self.assertRaisesRegex(ValueError, "insufficient buildable"):
                start_area(ground, np.ones_like(depth), geo)


if __name__ == "__main__":
    unittest.main()
