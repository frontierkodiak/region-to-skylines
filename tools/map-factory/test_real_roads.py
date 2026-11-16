"""Network codec and real-road writer checks against the native template."""

import hashlib
import json
import unittest
from pathlib import Path

import numpy as np

import netcodec as nc
import network_writer as nw
from crp import read_package
from transport_paths import _clip_line, merge

ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "templates/native-corridors.crp"


def payload():
    _, assets = read_package(TEMPLATE.read_bytes())
    return next(a["payload"] for a in assets if a["kind"] == 52)


def carriageway(nodes, edges, x, inbound, n=12):
    ids = []
    for z in np.linspace(8640, 8640 - 90 * (n - 1), n):
        nodes.append({"xyz": [x, 120.0, float(z)], "outside": None})
        ids.append(len(nodes) - 1)
    nodes[ids[0]]["outside"] = "north"
    order = ids if inbound else ids[::-1]
    for a, b in zip(order, order[1:]):
        d = np.subtract(nodes[b]["xyz"], nodes[a]["xyz"])
        d[1] = 0
        d /= np.linalg.norm(d)
        edges.append(
            {
                "a": a,
                "b": b,
                "kind": "highway",
                "structure": "ground",
                "start_dir": d.tolist(),
                "end_dir": (-d).tolist(),
            }
        )
    return ids


class Codec(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = payload()

    def test_template_sections_round_trip_byte_exact(self):
        """Decoding and re-encoding reproduces the game's own bytes."""
        for name, section in [
            ("NetManager", nc.NetSection),
            ("BuildingManager", nc.BuildingSection),
        ]:
            start = nw.section_start(self.data, name)
            decoded = section(self.data, start)
            self.assertEqual(decoded.encode(), self.data[start : decoded.end], name)

    def test_exact_encoder_matches_decoder(self):
        from template import decode_array

        rng = np.random.default_rng(7)
        for width in [1, 2, 4, 8]:
            top = (1 << (8 * width)) - 1
            values = np.concatenate(
                [
                    np.zeros(300, np.uint64),
                    np.arange(200, dtype=np.uint64) * 3,
                    rng.integers(0, min(top, 2**62), 400, dtype=np.uint64),
                    np.full(130, 5, np.uint64),
                    (
                        np.arange(150, dtype=np.uint64) * 7
                        + rng.integers(0, 3, 150, dtype=np.uint64)
                    ),
                ]
            ) & np.uint64(top)
            encoded = nc.encode_exact(values, width)
            decoded, end = decode_array(encoded, len(values), 0, width)
            self.assertEqual(end, len(encoded))
            self.assertEqual(decoded.astype(np.uint64).tolist(), values.tolist(), width)

    def test_template_vocabulary(self):
        net = nc.NetSection(self.data, nw.section_start(self.data, "NetManager"))
        self.assertEqual((len(net.nodes), len(net.segments)), (288, 285))
        self.assertIn("Highway Connection Elevated", net.prefabs.names)


class Writer(unittest.TestCase):
    def test_dual_carriageway_replaces_template_roads(self):
        nodes, edges = [], []
        carriageway(nodes, edges, -24.0, inbound=True)
        carriageway(nodes, edges, 24.0, inbound=False)
        data, report = nw.apply_highways(
            payload(), {"nodes": nodes, "edges": edges}, lambda x, z: 100.0
        )
        self.assertEqual((report["incoming_roads"], report["outgoing_roads"]), (1, 1))
        net = nc.NetSection(data, nw.section_start(data, "NetManager"))
        buildings = nc.BuildingSection(data, nw.section_start(data, "BuildingManager"))
        names = net.prefabs.names
        used = {names[net.segment_prefab[s]] for s in net.segments}
        self.assertNotIn("Highway Elevated", used)
        self.assertIn("Highway", used)
        flags = {
            int(net.node_flags[i - 1])
            for i in net.nodes
            if names[net.node_prefab[i]] == "Highway"
        }
        # As the game computes them (7th Island Enhanced carries the same values):
        # middle 0x1404121, entry 0x404401, exit 0x1004401.
        self.assertTrue({0x1404121, 0x404401, 0x1004401} <= flags)
        for node_id, record in net.nodes.items():
            for segment in record["segments"]:
                self.assertIn(
                    node_id,
                    (
                        net.segments[segment]["start_node"],
                        net.segments[segment]["end_node"],
                    ),
                )
            if record["building"]:
                self.assertIn(record["building"], buildings.ids)
        connections = [
            b for b in buildings.ids if buildings.prefab(b) == "Road Connection"
        ]
        self.assertEqual(len(connections), 2)
        self.assertTrue(
            all(
                net.segments[s]["lanes"] == 0
                for s, r in net.segments.items()
                if names[net.segment_prefab[s]] == "Highway"
            )
        )

    def test_air_path_gets_two_way_connections(self):
        nodes, edges = [], []
        carriageway(nodes, edges, -24.0, inbound=True)
        carriageway(nodes, edges, 24.0, inbound=False)
        air = {"nodes": [], "edges": []}
        for x in np.linspace(-8640, 8640, 4):
            air["nodes"].append({"xyz": [float(x), 500.0, 3000.0], "outside": None})
        air["nodes"][0]["outside"], air["nodes"][-1]["outside"] = "west", "east"
        for a in range(3):
            air["edges"].append(
                {
                    "a": a,
                    "b": a + 1,
                    "kind": "air",
                    "structure": "ground",
                    "start_dir": [1, 0, 0],
                    "end_dir": [-1, 0, 0],
                }
            )
        graph = merge({"nodes": nodes, "edges": edges}, air)
        data, report = nw.apply_highways(payload(), graph, lambda x, z: 100.0)
        self.assertEqual(report["plane_paths"], 2)
        buildings = nc.BuildingSection(data, nw.section_start(data, "BuildingManager"))
        planes = [
            b for b in buildings.ids if buildings.prefab(b) == "Airplane Connection"
        ]
        self.assertEqual(len(planes), 2)
        self.assertTrue(all(int(buildings.flags[b - 1]) & 0xC0 == 0xC0 for b in planes))


class Paths(unittest.TestCase):
    def test_runway_axis_meets_two_edges(self):
        t0, t1 = _clip_line(np.array([0.0, -20000.0]), np.array([0.0, 1.0]))
        self.assertAlmostEqual(-20000 + t0, -8640, delta=1e-6)
        self.assertAlmostEqual(-20000 + t1, 8640, delta=1e-6)


class Grades(unittest.TestCase):
    def test_through_node_directions_carry_the_grade(self):
        from real_roads import grade_directions

        nodes = [{"xyz": [0.0, 100.0 + 6.0 * i, 100.0 * i]} for i in range(3)]
        edges = [
            {
                "a": i,
                "b": i + 1,
                "kind": "highway",
                "start_dir": [0, 0, 1],
                "end_dir": [0, 0, -1],
            }
            for i in range(2)
        ]
        grade_directions({"nodes": nodes, "edges": edges})
        self.assertAlmostEqual(edges[0]["start_dir"][1], 0.06)
        self.assertAlmostEqual(edges[0]["end_dir"][1], -0.06)
        self.assertEqual(edges[0]["end_dir"], [-v for v in edges[1]["start_dir"]])


class LandCoverPath(unittest.TestCase):
    """The full stage with land cover, on main's generation path (Asheville)."""

    @classmethod
    def setUpClass(cls):
        import gzip
        import tempfile

        import real_roads

        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        fixture = ROOT / "fixtures/asheville"
        (tmp / "geometry.json").write_bytes(
            gzip.decompress((fixture / "shipping-geometry.json.gz").read_bytes())
        )
        (tmp / "banks.f32").write_bytes(
            gzip.decompress((fixture / "banks.f32.gz").read_bytes())
        )
        cls.out = tmp / "maps/asheville"
        cls.receipt = real_roads.generate(
            fixture / "input.png",
            tmp / "geometry.json",
            cls.out,
            banks=tmp / "banks.f32",
            landcover=fixture / "landcover.u8.gz",
            evidence=fixture / "shipping-evidence.json",
        )

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_map_has_real_networks_and_resources(self):
        package = self.receipt["package"]
        self.assertTrue(
            {"Highway", "HighwayRamp", "Train Track"}
            <= set(package["highways"]["network_prefabs"])
        )
        self.assertEqual(package["highways"]["incoming_roads"], 4)
        self.assertIn("environment", self.receipt["resources"])
        self.assertIn("native_admission", self.receipt)

    def test_no_trees_on_roads_or_rail(self):
        from paint import load_plan
        from resources import TREE_UNIT

        result, _, _ = load_plan(self.out / "plan.npz")
        px, pz, _ = result["trees"]
        trees = np.column_stack([px * TREE_UNIT, pz * TREE_UNIT]).astype(float)
        graph = json.loads((self.out / "hydrology.json").read_text())["highways"]
        nodes = graph["nodes"]
        for e in graph["edges"]:
            if e["kind"] not in ("highway", "ramp", "rail"):
                continue
            a = np.asarray(nodes[e["a"]]["xyz"])[[0, 2]]
            b = np.asarray(nodes[e["b"]]["xyz"])[[0, 2]]
            d = b - a
            t = np.clip(((trees - a) @ d) / max(d @ d, 1e-9), 0, 1)
            gap = np.hypot(*(trees - (a + t[:, None] * d)).T).min()
            self.assertGreater(gap, 8.0, f"tree {gap:.1f} m from a {e['kind']} segment")

    def test_staging_reproduces_the_package(self):
        import tempfile

        from soak import stage_prepared

        with tempfile.TemporaryDirectory() as stage:
            staged = stage_prepared(self.out.parent, Path(stage), ["asheville"])
            crp = staged[0][1]
            self.assertEqual(
                hashlib.sha256(crp.read_bytes()).hexdigest(),
                self.receipt["package"]["sha256"],
            )


if __name__ == "__main__":
    unittest.main()
