"""Semantic road access and truthful absent-rail behavior, without a game."""

import gzip
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

import netcodec as nc
import network_writer as nw
from crp import write_map
from real_roads import choose_start, finish, road_eligibility
from soak import panel_expectations, probes_for
from test_real_roads import TEMPLATE, payload


def node(x, z=0, outside=None):
    return {"xyz": [float(x), 100.0, float(z)], "outside": outside}


def edge(a, b, kind="highway"):
    return {"a": a, "b": b, "kind": kind, "structure": "ground"}


def interchange():
    return {
        "nodes": [
            node(-8640, outside="west"),
            node(-100),
            node(100),
            node(8640, outside="east"),
        ],
        "edges": [edge(0, 1), edge(2, 3)],
    }


class RoadEligibility(unittest.TestCase):
    def test_two_directed_start_links_are_eligible(self):
        report = road_eligibility(interchange(), 12)
        self.assertEqual(report["status"], "eligible")
        self.assertEqual(report["reason_codes"], [])
        self.assertEqual(report["interchange"]["gap_m"], 200)

    def test_counts_and_nearby_stubs_do_not_prove_outside_reachability(self):
        graph = interchange()
        graph["nodes"] += [node(-2000), node(2000), node(-200), node(200)]
        graph["edges"] = [edge(0, 4), edge(5, 3), edge(6, 1), edge(2, 7)]
        report = road_eligibility(graph, 12)
        self.assertEqual(report["incoming_road_nodes"], 1)
        self.assertEqual(report["outgoing_road_nodes"], 1)
        self.assertEqual(report["status"], "no_outside_link")
        self.assertIn("no_outside_reachable_start_arrival", report["reason_codes"])
        self.assertIn("no_start_departure_reaches_outside", report["reason_codes"])

    def test_reversed_one_way_departure_is_not_an_outside_exit(self):
        graph = interchange()
        graph["edges"][1] = edge(3, 2)
        report = road_eligibility(graph, 12)
        self.assertEqual(report["status"], "no_outside_link")
        self.assertIn("no_outgoing_road_connection", report["reason_codes"])

    def test_reachable_stubs_too_far_apart_are_not_an_interchange(self):
        graph = interchange()
        graph["nodes"][1] = node(-500)
        graph["nodes"][2] = node(500)
        report = road_eligibility(graph, 12)
        self.assertEqual(report["status"], "no_outside_link")
        self.assertIn(
            "start_arrival_departure_more_than_400m_apart", report["reason_codes"]
        )

    def test_other_tile_or_transport_modes_cannot_satisfy_start_access(self):
        graph = interchange()
        self.assertEqual(road_eligibility(graph, 13)["status"], "no_outside_link")
        for kind in ["rail", "air", "ship"]:
            graph["edges"] = [edge(0, 1, kind), edge(2, 3, kind)]
            self.assertEqual(road_eligibility(graph, 12)["status"], "no_outside_link")

    def test_choose_start_rejects_a_disconnected_central_pair(self):
        graph = interchange()
        # Connected pair in tile13, isolated close pair in the preferred tile12.
        graph["nodes"][1] = node(1820)
        graph["nodes"][2] = node(2020)
        graph["nodes"] += [node(-200), node(-100), node(100), node(200)]
        graph["edges"] += [edge(4, 5), edge(6, 7)]
        ground = np.full((1081, 1081), 100.0)
        tile, _ = choose_start(graph, ground, np.zeros_like(ground), 12)
        self.assertEqual(tile, 13)
        self.assertEqual(road_eligibility(graph, tile)["status"], "eligible")

    def test_absence_has_explicit_fallback_not_synthesized_geometry(self):
        graph = {"nodes": [], "edges": []}
        report = road_eligibility(graph, 12)
        self.assertEqual(report["status"], "no_outside_link")
        self.assertEqual(report["fallback"], "explicit_no_outside_link")
        self.assertEqual(graph, {"nodes": [], "edges": []})


class AbsentNetworks(unittest.TestCase):
    def test_no_real_rail_removes_native_template_rail_and_outside_buildings(self):
        data, report = nw.apply_highways(
            payload(), {"nodes": [], "edges": []}, lambda x, z: 100.0
        )
        net = nc.NetSection(data, nw.section_start(data, "NetManager"))
        buildings = nc.BuildingSection(data, nw.section_start(data, "BuildingManager"))
        self.assertEqual(report["train_tracks"], 0)
        used = {net.prefabs.names[net.segment_prefab[s]] for s in net.segments}
        self.assertFalse(used & nw.TEMPLATE_RAIL)
        self.assertFalse(
            any(buildings.prefab(b) == "Train Connection" for b in buildings.ids)
        )

    def test_absent_networks_clear_native_new_game_counts_and_probe_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            crp = folder / "no-network.crp"
            fixture = TEMPLATE.parent.parent / "fixtures/asheville"
            for name in ["terrain.u16", "water.u16", "hydrology.json"]:
                (folder / name).write_bytes(
                    gzip.decompress((fixture / (name + ".gz")).read_bytes())
                )
            write_map(
                TEMPLATE,
                TEMPLATE.with_suffix(".json"),
                folder / "terrain.u16",
                folder / "water.u16",
                folder / "hydrology.json",
                crp,
            )
            graph = {"nodes": [], "edges": []}
            hydro = {"highways": graph, "start_tile": 12, "samples": {}}
            receipt = finish(crp, hydro)
            self.assertTrue(
                all(
                    value == 0
                    for value in panel_expectations(crp)["connections"].values()
                )
            )

            layout = json.loads((TEMPLATE.parent / "native-corridors.json").read_text())
            probes = probes_for(hydro, layout, receipt["highways"])
            self.assertEqual(probes["paths"], [])


if __name__ == "__main__":
    unittest.main()
