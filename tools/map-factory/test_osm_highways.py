"""Synthetic OSM inputs for the motorway graph builder."""

import math
import unittest

import numpy as np

import osm_highways as oh

SQ = {"lon": -82.555, "lat": 35.58, "rotation": 0, "scale": 1}


def lonlat(x, z):
    """Inverse of prepare.pixel for an unrotated, true-scale square."""
    a, e2 = 6378137, 0.00669437999014
    w = 1 - e2 * math.sin(math.radians(SQ["lat"])) ** 2
    m = a * (1 - e2) / w**1.5
    nc = a / math.sqrt(w) * math.cos(math.radians(SQ["lat"]))
    return [SQ["lon"] + math.degrees(x / nc), SQ["lat"] + math.degrees(z / m)]


def road(points, **tags):
    return {
        "class": "motorway",
        "oneway": 1,
        "pts": [lonlat(x, z) for x, z in points],
        **tags,
    }


def line(x0, z0, x1, z1, step=200):
    n = max(2, int(math.hypot(x1 - x0, z1 - z0) / step) + 1)
    return [(x0 + (x1 - x0) * t, z0 + (z1 - z0) * t) for t in np.linspace(0, 1, n)]


def build(roads, ground=None):
    geometry = {"sq": SQ, "zoom": 14, "roads": roads}
    ground = np.full((1081, 1081), 100.0) if ground is None else ground
    return oh.build_highway_graph(geometry, ground, np.zeros((1081, 1081))), ground


def degree(graph):
    d = np.zeros(len(graph["nodes"]), int)
    for e in graph["edges"]:
        d[e["a"]] += 1
        d[e["b"]] += 1
    return d


class HighwayGraphTests(unittest.TestCase):
    def test_tile_fragments_merge_into_one_way(self):
        # Split an east-west line at a z14 tile boundary, each piece running 30 m
        # into the neighbour's buffer, as OpenMapTiles fragments do.
        n = 2**14
        boundary = math.floor((SQ["lon"] + 180) / 360 * n) + 1
        lon_b = boundary / n * 360 - 180
        x_b = (lon_b - SQ["lon"]) / math.degrees(
            1 / (6378137 * math.cos(math.radians(SQ["lat"])))
        )
        west = road(line(x_b - 1500, 300, x_b + 30, 300))
        east = road(line(x_b - 30, 300, x_b + 1500, 300))
        frags, _ = oh.fragments({"sq": SQ, "zoom": 14, "roads": [west, east]})
        ways, _ = oh.chain(oh.join_touching(frags))
        self.assertEqual(len(ways), 1)
        self.assertAlmostEqual(oh.arc(ways[0]["pts"])[-1], 3000, delta=5)

    def test_ramp_end_on_highway_makes_junction(self):
        main = road(line(-9000, 0, 9000, 0))
        ramp = road([(1000, 0.5), (1150, -60), (1400, -300), (1600, -600)], ramp=1)
        graph, _ = build([main, ramp])
        d = degree(graph)
        self.assertEqual(int((d == 3).sum()), 1)
        node = graph["nodes"][int(np.flatnonzero(d == 3)[0])]["xyz"]
        self.assertAlmostEqual(node[0], 1000, delta=4)

    def test_middle_nodes_have_opposite_directions(self):
        curve = [(x, 2000 * math.sin(x / 3000)) for x in np.linspace(-9000, 9000, 120)]
        graph, _ = build([road(curve)])
        arriving = {e["b"]: e for e in graph["edges"]}
        checked = 0
        for e in graph["edges"]:
            if e["a"] in arriving:
                dot = np.dot(arriving[e["a"]]["end_dir"], e["start_dir"])
                self.assertAlmostEqual(dot, -1, places=5)
                checked += 1
        self.assertGreater(checked, 100)
        for e in graph["edges"]:
            self.assertLessEqual(e["length"], 115)

    def test_outside_nodes_sit_on_the_edge(self):
        graph, _ = build(
            [road(line(-9500, -300, 9500, 900)), road(line(9500, 1000, -9500, -200))]
        )
        outside = [n for n in graph["nodes"] if n["outside"]]
        self.assertEqual(
            sorted(n["outside"] for n in outside), ["east", "east", "west", "west"]
        )
        for n in outside:
            self.assertAlmostEqual(abs(n["xyz"][0]), oh.HALF, places=3)
        self.assertEqual(
            sorted(x["direction"] for x in graph["report"]["outside"]),
            ["in", "in", "out", "out"],
        )

    def test_two_way_trunk_becomes_two_carriageways(self):
        graph, _ = build(
            [road(line(-9500, 0, 9500, 0), oneway=None, **{"class": "trunk"})]
        )
        outside = sorted(
            (n["outside"], round(n["xyz"][2])) for n in graph["nodes"] if n["outside"]
        )
        self.assertEqual([o[0] for o in outside], ["east", "east", "west", "west"])
        self.assertAlmostEqual(abs(outside[0][1] - outside[1][1]), 24, delta=1)

    def test_grade_limit_and_earthworks(self):
        rows = np.arange(1081)[:, None] * np.ones(1081)
        ground = 100 + 300 * np.exp(
            -(((rows - 540) / 40) ** 2)
        )  # a steep east-west ridge
        before = ground.copy()
        graph, ground = build([road(line(0, -8000, 0, 8000))], ground)
        nodes = graph["nodes"]
        for e in graph["edges"]:
            a, b = nodes[e["a"]]["xyz"], nodes[e["b"]]["xyz"]
            self.assertLessEqual(
                abs(b[1] - a[1]) / e["length"], oh.GRADE["highway"] + 1e-9
            )
        self.assertLessEqual(np.abs(ground - before).max(), oh.CUT_FILL + 1e-9)
        self.assertTrue(any(e["structure"] == "bridge" for e in graph["edges"]))

    def test_two_way_rail_reaches_two_edges(self):
        def track(points, **tags):
            return {
                "class": "rail",
                "subclass": "rail",
                "pts": [lonlat(x, z) for x, z in points],
                **tags,
            }

        curve = [(x, 1500 * math.sin(x / 4000)) for x in np.linspace(-9300, 9300, 150)]
        twin = [(x, z + 12) for x, z in curve]  # a parallel OSM track 12 m away
        yard = [(500, 60), (700, 300), (900, 400)]
        rows = np.arange(1081)[:, None] * np.ones(1081)
        ground = 100 + 0.2 * np.clip(rows - 540, 0, None) ** 1.5
        roads = [
            track(curve),
            track(twin),
            track(yard, service="yard"),
            road(line(-9500, 3000, 9500, 3000)),
        ]
        geometry = {"sq": SQ, "zoom": 14, "roads": roads}
        depth = np.zeros((1081, 1081))
        plain = oh.build_highway_graph(geometry, ground.copy(), depth)
        self.assertFalse(any(e["kind"] == "rail" for e in plain["edges"]))
        graph = oh.build_highway_graph(geometry, ground.copy(), depth, rail=True)
        rail = [e for e in graph["edges"] if e["kind"] == "rail"]
        ids = {e["a"] for e in rail} | {e["b"] for e in rail}
        outside = sorted(
            graph["nodes"][i]["outside"] for i in ids if graph["nodes"][i]["outside"]
        )
        self.assertEqual(outside, ["east", "west"])  # twin collapsed, yard dropped
        for i in ids:
            n = graph["nodes"][i]
            if n["outside"]:
                self.assertAlmostEqual(abs(n["xyz"][0]), oh.HALF, places=3)
        self.assertFalse(ids & {e["a"] for e in graph["edges"] if e["kind"] != "rail"})
        outward = {}
        for e in rail:
            outward.setdefault(e["a"], []).append(e["start_dir"])
            outward.setdefault(e["b"], []).append(e["end_dir"])
            a, b = graph["nodes"][e["a"]]["xyz"], graph["nodes"][e["b"]]["xyz"]
            self.assertLessEqual(
                abs(b[1] - a[1]) / e["length"], oh.GRADE["rail"] + 1e-9
            )
            self.assertLessEqual(e["length"], 115)
        middles = [d for d in outward.values() if len(d) == 2]
        self.assertGreater(len(middles), 100)
        for d0, d1 in middles:
            self.assertAlmostEqual(np.dot(d0, d1), -1, places=5)
        self.assertAlmostEqual(graph["report"]["rail"]["km"]["rail"], 18.6, delta=1.0)


if __name__ == "__main__":
    unittest.main()
