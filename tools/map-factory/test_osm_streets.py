"""Street topology and actual shared-codec output, without starting the game."""

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

import netcodec as nc
import network_writer as nw
from osm_streets import bounds, build_street_graph, extract_pbf
from test_osm_highways import SQ, lonlat
from test_real_roads import payload


def source(points, ways):
    return {
        "sq": SQ,
        "osm": {
            "elements": [
                {
                    "type": "node",
                    "id": i,
                    "lon": lonlat(x, z)[0],
                    "lat": lonlat(x, z)[1],
                }
                for i, (x, z) in points.items()
            ]
            + [
                {
                    "type": "way",
                    "id": i + 100,
                    "nodes": ids,
                    "tags": {"highway": "residential", **tags},
                }
                for i, (ids, tags) in enumerate(ways)
            ]
        },
    }


def build(data):
    ground = np.full((1081, 1081), 100.0)
    depth = np.zeros_like(ground)
    graph = build_street_graph(data, SQ, ground, depth)
    np.testing.assert_array_equal(ground, 100)
    np.testing.assert_array_equal(depth, 0)
    return graph


def written(graph):
    data, report = nw.apply_highways(payload(), graph, lambda x, z: 100)
    net = nc.NetSection(data, nw.section_start(data, "NetManager"))
    buildings = nc.BuildingSection(data, nw.section_start(data, "BuildingManager"))
    for section, name in ((net, "NetManager"), (buildings, "BuildingManager")):
        assert section.encode() == data[nw.section_start(data, name) : section.end]
    return net, buildings, report


class Streets(unittest.TestCase):
    def test_playable_pilot_keeps_private_roads_inside_and_highways_outside(self):
        data = source(
            {1: (0, 0), 2: (6000, 0), 3: (0, 6000), 4: (-100, 0)},
            [
                ([1, 2], {"highway": "service", "service": "driveway"}),
                ([1, 3], {"highway": "motorway", "oneway": "yes"}),
                ([1, 4], {"highway": "service", "service": "alley"}),
            ],
        )
        all_roads = build(data)
        ground = np.full((1081, 1081), 100.0)
        streets = build_street_graph(data, SQ, ground, ground * 0, "playable")
        self.assertEqual(all_roads["report"]["represented_osm_ways"], 3)
        self.assertEqual(streets["report"]["represented_osm_ways"], 3)
        self.assertTrue(any(abs(n["xyz"][0] - 4800) < 1e-6 for n in streets["nodes"]))
        self.assertTrue(any(n["xyz"][2] > 4800 for n in streets["nodes"]))
        self.assertFalse(any(n["outside"] for n in streets["nodes"]))

    def test_curve_fit_retains_way_coverage_across_source_boundaries(self):
        graph = build(
            source({1: (0, 0), 2: (80, 0), 3: (160, 0)}, [([1, 2], {}), ([2, 3], {})])
        )
        self.assertEqual(len(graph["edges"]), 1)
        self.assertEqual(graph["edges"][0]["osm_ways"], [100, 101])
        self.assertEqual(graph["report"]["represented_osm_ways"], 2)
        written(graph)

    def test_writer_rejects_network_capacity_before_allocating(self):
        with self.assertRaisesRegex(ValueError, "native capacities"):
            nw.apply_highways(
                payload(), {"nodes": [{}] * nc.NODES, "edges": []}, lambda x, z: 100
            )

    def test_parallel_routes_survive_without_duplicate_native_node_pairs(self):
        graph = build(
            source(
                {
                    1: (-100, 0),
                    2: (100, 0),
                    3: (0, 5),
                    4: (0, -5),
                    5: (-200, 0),
                    6: (200, 0),
                },
                [([1, 3, 2], {}), ([1, 4, 2], {}), ([5, 1], {}), ([2, 6], {})],
            )
        )
        pairs = [frozenset((e["a"], e["b"])) for e in graph["edges"]]
        self.assertEqual(len(pairs), len(set(pairs)))
        self.assertEqual(graph["report"]["represented_osm_ways"], 4)
        written(graph)

    @unittest.skipUnless(
        importlib.util.find_spec("osmium"), "PBF extraction needs osmium"
    )
    def test_reference_complete_osm_file_extracts_shared_ids(self):
        data = source(
            {1: (-100, 0), 2: (0, 0), 3: (100, 0), 4: (0, 100)},
            [([1, 2, 3], {}), ([2, 4], {})],
        )
        xml = ['<osm version="0.6">']
        for e in data["osm"]["elements"]:
            if e["type"] == "node":
                xml.append(f'<node id="{e["id"]}" lat="{e["lat"]}" lon="{e["lon"]}"/>')
            else:
                xml.append(f'<way id="{e["id"]}">')
                xml.extend(f'<nd ref="{n}"/>' for n in e["nodes"])
                xml.append('<tag k="highway" v="residential"/></way>')
        xml.append("</osm>")
        with tempfile.TemporaryDirectory() as directory:
            path, out = Path(directory) / "input.osm", Path(directory) / "extract.json"
            path.write_text("".join(xml))
            extracted = extract_pbf(SQ, path, out)
            self.assertEqual(json.loads(out.read_text()), extracted)
            self.assertEqual(build(extracted)["report"]["motor_ways_in_square"], 2)
            with self.assertRaisesRegex(FileExistsError, "already exists"):
                extract_pbf(SQ, path, out)

    def test_query_envelope_covers_rotated_scaled_corners(self):
        from prepare import pixel

        sq = {**SQ, "rotation": 35, "scale": 1.5}
        south, west, north, east = bounds(sq)
        envelope = np.array(
            [pixel(sq, (lon, lat)) for lon in (west, east) for lat in (south, north)]
        )
        self.assertLess(envelope[:, 0].min(), 0)
        self.assertGreater(envelope[:, 0].max(), 1080)
        self.assertLess(envelope[:, 1].min(), 0)
        self.assertGreater(envelope[:, 1].max(), 1080)

    def test_shared_node_joins_but_geometric_crossing_and_nearby_ends_do_not(self):
        data = source(
            {
                1: (-100, 0),
                2: (0, 0),
                3: (100, 0),
                4: (0, 100),
                5: (1, 0),
                6: (1, -100),
                7: (-50, -50),
                8: (-50, 50),
            },
            [([1, 2, 3], {}), ([2, 4], {}), ([5, 6], {}), ([7, 8], {})],
        )
        graph = build(data)
        junction = next(i for i, n in enumerate(graph["nodes"]) if n["osm_node"] == 2)
        self.assertEqual(sum(junction in (e["a"], e["b"]) for e in graph["edges"]), 3)
        net, _, report = written(graph)
        self.assertEqual(len(report["segment_ids"]), len(graph["edges"]))
        road_nodes = {
            net.segments[s][end]
            for s in report["segment_ids"]
            for end in ("start_node", "end_node")
        }
        self.assertEqual(
            sum(bool(net.node_flags[n - 1] & nw.JUNCTION) for n in road_nodes), 1
        )

    def test_two_way_edge_connections_are_incoming_and_outgoing(self):
        graph = build(source({1: (-9000, 0), 2: (9000, 0)}, [([1, 2], {})]))
        net, buildings, report = written(graph)
        self.assertEqual((report["incoming_roads"], report["outgoing_roads"]), (2, 2))
        outside = [
            n
            for n in net.nodes
            if net.node_flags[n - 1] & nw.OUTSIDE
            and net.prefabs.names[net.node_prefab[n]] == "Basic Road"
        ]
        self.assertEqual(len(outside), 2)
        for n in outside:
            self.assertEqual(
                net.node_flags[n - 1] & (nw.ONE_WAY_IN | nw.ONE_WAY_OUT), 0
            )
            b = net.nodes[n]["building"]
            self.assertEqual(buildings.prefab(b), "Road Connection")
            self.assertEqual(buildings.flags[b - 1] & 0xC0, 0xC0)

    def test_reverse_oneway_and_short_disconnected_streets_survive(self):
        graph = build(source({1: (-10, 0), 2: (10, 0)}, [([1, 2], {"oneway": "-1"})]))
        net, _, report = written(graph)
        self.assertEqual(graph["nodes"][graph["edges"][0]["a"]]["osm_node"], 2)
        self.assertEqual(report["network_prefabs"], ["Oneway Road"])
        self.assertTrue(
            all(net.segments[s]["lanes"] == 0 for s in report["segment_ids"])
        )

    def test_roundabout_is_a_directed_closed_loop(self):
        graph = build(
            source(
                {1: (0, 0), 2: (50, 0), 3: (50, 50), 4: (0, 50)},
                [([1, 2, 3, 4, 1], {"junction": "roundabout"})],
            )
        )
        self.assertEqual({e["kind"] for e in graph["edges"]}, {"street_oneway"})
        self.assertEqual(graph["edges"][0]["a"], graph["edges"][-1]["b"])
        written(graph)

    def test_unsupported_and_outside_ways_are_accounted_for(self):
        graph = build(
            source(
                {1: (0, 0), 2: (100, 0), 3: (10000, 0), 4: (10100, 0)},
                [([1, 2], {}), ([1, 2], {"highway": "footway"}), ([3, 4], {})],
            )
        )
        report = graph["report"]
        self.assertEqual(report["excluded_highway_classes"], {"footway": 1})
        self.assertEqual(report["motor_ways_in_extract"], 2)
        self.assertEqual(report["motor_ways_in_square"], 1)
        self.assertEqual(report["ways_outside_scope"], 1)

    def test_tunnel_has_native_portals_and_bridge_has_pillar(self):
        graph = build(
            source(
                {
                    1: (-200, 0),
                    2: (-100, 0),
                    3: (100, 0),
                    4: (200, 0),
                    5: (0, 100),
                    6: (100, 100),
                },
                [
                    ([1, 2], {}),
                    ([2, 3], {"tunnel": "yes"}),
                    ([3, 4], {}),
                    ([5, 6], {"bridge": "yes"}),
                ],
            )
        )
        _, buildings, report = written(graph)
        self.assertTrue(
            {"Basic Road Tunnel", "Basic Road Slope", "Basic Road Elevated"}
            <= set(report["network_prefabs"])
        )
        self.assertIn(
            "RoadSmallBridgePillar", {buildings.prefab(b) for b in buildings.ids}
        )

    def test_rejects_wrong_square_missing_nodes_and_partial_responses(self):
        data = source({1: (0, 0), 2: (100, 0)}, [([1, 2], {})])
        for change, message in (
            (lambda d: d.update(sq={}), "identical square"),
            (lambda d: d["osm"]["elements"].pop(0), "Missing nodes"),
            (lambda d: d["osm"].update(remark="timed out"), "Incomplete"),
        ):
            broken = copy.deepcopy(data)
            change(broken)
            with self.assertRaisesRegex(ValueError, message):
                build(broken)


if __name__ == "__main__":
    unittest.main()
