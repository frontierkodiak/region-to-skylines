"""Network codec and real-road writer checks against the native template."""

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

    def test_sections_reencode_to_what_they_decode(self):
        start = nw.section_start(self.data, "NetManager")
        net = nc.NetSection(self.data, start)
        again = nc.NetSection(net.encode(), 0)
        self.assertEqual(net.nodes, again.nodes)
        self.assertEqual(net.segments, again.segments)
        self.assertEqual(net.prefabs.names, again.prefabs.names)
        start = nw.section_start(self.data, "BuildingManager")
        buildings = nc.BuildingSection(self.data, start)
        again = nc.BuildingSection(buildings.encode(), 0)
        self.assertEqual(buildings.ids, again.ids)
        self.assertEqual(buildings.records, again.records)

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


if __name__ == "__main__":
    unittest.main()
