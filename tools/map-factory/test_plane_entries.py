"""Plane entries are an exporter guarantee, not airport evidence."""

import unittest
import numpy as np
from transport_paths import air_path


class PlaneEntries(unittest.TestCase):
    def test_any_square_has_two_entries(self):
        for lon, lat, height in [
            (0, 0, 0),
            (114.17, 22.29, 100),
            (-119.575, 37.735, 900),
            (-112.11, 36.08, 500),
        ]:
            geometry = {"sq": {"lon": lon, "lat": lat, "scale": 1, "rotation": 0}}
            graph, report = air_path(
                geometry, np.full((1081, 1081), height, dtype=float)
            )
            self.assertEqual(
                [n["outside"] for n in graph["nodes"] if n["outside"]], ["west", "east"]
            )
            self.assertTrue(all(e["kind"] == "air" for e in graph["edges"]))
            self.assertEqual(report["air"]["source"], "authored_overflight")

    def test_runway_axis_that_misses_still_gets_entries(self):
        g = {
            "sq": {"lon": 0, "lat": 0, "scale": 1, "rotation": 0},
            "airport": {"name": "outside", "lon": 20, "lat": 20, "heading": 0},
        }
        graph, report = air_path(g, np.zeros((1081, 1081)))
        self.assertEqual(report["air"]["source"], "authored_overflight")
        self.assertEqual(sum(bool(n["outside"]) for n in graph["nodes"]), 2)

    def test_old_no_air_argument_cannot_suppress_the_guarantee(self):
        import json
        import tempfile
        from pathlib import Path
        from real_roads import prepare_roads

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ["terrain.u16", "water.u16"]:
                np.zeros((1081, 1081), dtype="<u2").tofile(root / name)
            (root / "hydrology.json").write_text(
                json.dumps({"start_tile": 12, "sea_level_m": 0})
            )
            geometry = {
                "sq": {"lon": 0, "lat": 0, "scale": 1, "rotation": 0},
                "roads": [],
                "rivers": [],
                "lakes": [],
                "oceans": [],
            }
            (root / "geometry.json").write_text(json.dumps(geometry))
            prepare_roads(root, root / "geometry.json", air=False, ship=False)
            hydro = json.loads((root / "hydrology.json").read_text())
            self.assertEqual(
                sum(n.get("outside") is not None for n in hydro["highways"]["nodes"]), 2
            )

    def test_shipping_writer_adds_air_without_replacing_existing_networks(self):
        import shutil
        import tempfile
        from pathlib import Path
        import netcodec as nc
        from crp import read_package
        from network_writer import section_start, OUTSIDE
        from plane_entries import ensure_plane_entries

        root = Path(__file__).resolve().parent

        def network(path):
            _, assets = read_package(path.read_bytes())
            data = next(a["payload"] for a in assets if a["kind"] == 52)
            return nc.NetSection(data, section_start(data, "NetManager"))

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = folder / "test.crp"
            shutil.copy(root / "templates/native-corridors.crp", path)
            np.zeros((1081, 1081), dtype="<u2").tofile(folder / "terrain.u16")
            before = network(path)
            original = {
                i: (
                    before.prefabs.names[before.node_prefab[i]],
                    tuple(before.nodes[i]["position"]),
                )
                for i in before.nodes
            }
            result = ensure_plane_entries(
                path, {"sq": {"lon": 0, "lat": 0, "rotation": 0, "scale": 1}}, folder
            )
            self.assertEqual(result["entries"], 2)
            after = network(path)
            self.assertTrue(
                all(
                    i in after.nodes
                    and (
                        after.prefabs.names[after.node_prefab[i]],
                        tuple(after.nodes[i]["position"]),
                    )
                    == v
                    for i, v in original.items()
                )
            )
            self.assertEqual(
                sum(
                    "Airplane" in after.prefabs.names[after.node_prefab[i]]
                    and bool(int(after.node_flags[i - 1]) & OUTSIDE)
                    for i in after.nodes
                ),
                2,
            )
            written = path.read_bytes()
            self.assertFalse(
                ensure_plane_entries(
                    path,
                    {"sq": {"lon": 0, "lat": 0, "rotation": 0, "scale": 1}},
                    folder,
                )["authored"]
            )
            self.assertEqual(path.read_bytes(), written)


if __name__ == "__main__":
    unittest.main()
