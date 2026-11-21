"""Tests for the rail junction-fit study, its binding, its freeze and its scores.

The invariance tests carry the study's guard rails: a prediction must not depend
on how the export numbers segments or nodes, on the order records appear in, or
on which end of a segment the game calls "start". The orientation-reversal test
on a real frozen package is also the empirical check of the tangent convention:
if the study read `end_direction` at the start node, reversing every segment
would change predictions, and it must not.

Run:  cd tools/map-factory && .venv/bin/python -m unittest discover \
        -s capability-evidence/rail-junction-fit-v1 -p 'test_*.py'
"""

import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[1]), str(HERE)]

import binding  # noqa: E402
import diagnose  # noqa: E402
import export_topology as exports  # noqa: E402
import junction_model as jm  # noqa: E402
import topology  # noqa: E402

TRAIN = ("Vehicle", "Train", "All")


def model_can_leave(pkg, query):
    """Does the requested source lane allow travel away from the boundary node?"""
    import model

    segments, _ = model.train_index(pkg)
    source = segments[int(query["from"][0])]
    lane = model.lane_at(source, int(query["from"][1]))
    node = model.endpoint_node(source, query["from"][2])
    return bool(lane) and model.can_travel(source, lane, node)


def lane(index, forward, backward):
    return {
        "index": index,
        "forward": forward,
        "backward": backward,
        "lane_type": TRAIN[0],
        "vehicle": [TRAIN[1]],
        "category": TRAIN[2],
    }


def segment(
    identity,
    start,
    end,
    a,
    b,
    lanes=None,
    flags=("Created", "Original"),
    start_direction=None,
    end_direction=None,
    prefab="Train Track",
):
    lanes = lanes or [lane(0, False, True), lane(1, True, False)]
    record = {
        "id": identity,
        "start": start,
        "end": end,
        "a": tuple(a),
        "b": tuple(b),
        "flags": set(flags),
        "prefab": prefab,
        "lanes": lanes,
    }
    if start_direction is not None:
        record["start_direction"] = tuple(start_direction)
    if end_direction is not None:
        record["end_direction"] = tuple(end_direction)
    return record


def package(segments):
    nodes = {}
    for item in segments:
        nodes.setdefault(item["start"], {"flags": set(), "position": item["a"]})
        nodes.setdefault(item["end"], {"flags": set(), "position": item["b"]})
    return {
        "name": "fixture",
        "segments": {item["id"]: item for item in segments},
        "nodes": nodes,
    }


def request(source, source_lane, source_offset, target, target_lane, target_offset):
    return {
        "from": [source, source_lane, source_offset],
        "to": [target, target_lane, target_offset],
        "name": "directed-outside-to-outside",
        "position_kind": "boundary",
        "diagnostic": False,
        "endpoint_edges": ["north", "south"],
    }


def straight_chain(with_tangents=True):
    """Two collinear segments; tangents agree with the chord."""
    return package(
        [
            segment(
                10,
                1,
                2,
                (0.0, 0.0, 0.0),
                (0.0, 0.0, 100.0),
                start_direction=(0.0, 0.0, 1.0),
                end_direction=(0.0, 0.0, -1.0),
            )
            if with_tangents
            else segment(10, 1, 2, (0.0, 0.0, 0.0), (0.0, 0.0, 100.0)),
            segment(
                11,
                2,
                3,
                (0.0, 0.0, 100.0),
                (0.0, 0.0, 200.0),
                start_direction=(0.0, 0.0, 1.0),
                end_direction=(0.0, 0.0, -1.0),
            )
            if with_tangents
            else segment(11, 2, 3, (0.0, 0.0, 100.0), (0.0, 0.0, 200.0)),
        ]
    )


def geometry_knot():
    """A degree-3 node where the chord and the authored tangent disagree.

    A leaves the node to the west, B to the north, C to the east. By chord,
    A-C is straight (0 degrees) and B is left over. B's authored direction at
    the node points east instead, so by tangent A-B is straight and C is the
    leftover. That is the smallest fixture where the two measures derive
    different junction pairings at the same node.
    """
    return package(
        [
            # 10 runs from node 1 (west) into node 2 at the origin.
            segment(
                10,
                1,
                2,
                (-100.0, 0.0, 0.0),
                (0.0, 0.0, 0.0),
                start_direction=(-1.0, 0.0, 0.0),
                end_direction=(-1.0, 0.0, 0.0),
            ),
            # 11 leaves node 2 northward by chord, but its authored direction
            # at node 2 points east, so the tangent says A-B is straight.
            segment(
                11,
                2,
                3,
                (0.0, 0.0, 0.0),
                (0.0, 0.0, -100.0),
                start_direction=(1.0, 0.0, 0.0),
                end_direction=(0.0, 0.0, -1.0),
            ),
            # 12 leaves node 2 eastward by chord, but its authored direction
            # points north, so the tangent refuses the straight A-C pairing.
            segment(
                12,
                2,
                4,
                (0.0, 0.0, 0.0),
                (100.0, 0.0, 0.0),
                start_direction=(0.0, 0.0, -1.0),
                end_direction=(-1.0, 0.0, 0.0),
            ),
        ]
    )


class GeometryTest(unittest.TestCase):
    def test_tangent_convention_matches_the_chord_on_a_straight_segment(self):
        pkg = straight_chain()
        self.assertAlmostEqual(jm.turn_degrees(pkg, 2, 10, 11, "chord"), 0.0, places=6)
        self.assertAlmostEqual(
            jm.turn_degrees(pkg, 2, 10, 11, "tangent"), 0.0, places=6
        )

    def test_outward_heading_is_into_the_segment_at_both_ends(self):
        pkg = straight_chain()
        self.assertEqual(
            jm.outward(pkg, 1, 10, "chord"), jm.outward(pkg, 1, 10, "tangent")
        )
        # Leaving the end node of 10 the tangent points back along the segment.
        self.assertEqual(jm.outward(pkg, 2, 10, "tangent"), (0.0, -1.0))

    def test_chord_and_tangent_derive_different_pairings_at_one_node(self):
        pkg = geometry_knot()
        chord = jm.node_alternatives(pkg, {2: [10, 11, 12]}, "continuation", "chord")
        tangent = jm.node_alternatives(
            pkg, {2: [10, 11, 12]}, "continuation", "tangent"
        )

        def chosen(resolutions):
            return {
                frozenset({a, b}) for partners in resolutions for a, b in partners[2]
            }

        self.assertEqual(chosen(chord), {frozenset({10, 12})})
        self.assertEqual(chosen(tangent), {frozenset({10, 11})})

    def test_shared_node_geometry_changes_the_reachability_answer(self):
        pkg = geometry_knot()
        # Travel forward from A's start into node 2, then onto B, and arrive at
        # B's end: the accepted study's chain request.
        query = request(10, 1, 0, 11, 1, 255)
        chord = jm.Engine(pkg).predict(query, "chord:continuation:any_lane")
        tangent = jm.Engine(pkg).predict(query, "tangent:continuation:any_lane")
        self.assertEqual(chord["prediction"], jm.NO_PATH)
        self.assertEqual(tangent["prediction"], jm.SUCCESS)

    def test_turn_threshold_admits_only_pairs_inside_it(self):
        pkg = geometry_knot()
        query = request(10, 1, 0, 11, 1, 255)
        engine = jm.Engine(pkg)
        # A-B is 90 degrees by chord: refused at 45, admitted at 90.
        self.assertEqual(
            engine.predict(query, "chord:turn:45:any_lane")["prediction"], jm.NO_PATH
        )
        self.assertEqual(
            engine.predict(query, "chord:turn:90:any_lane")["prediction"], jm.SUCCESS
        )

    def test_symmetric_tie_is_represented_not_broken_by_id(self):
        # Two straight candidates at node 2, so the greedy pairing ties.
        pkg = package(
            [
                segment(10, 1, 2, (-100.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
                segment(11, 2, 3, (0.0, 0.0, 0.0), (100.0, 0.0, 0.0)),
                segment(12, 2, 4, (0.0, 0.0, 0.0), (100.0, 0.0, 0.0)),
                segment(13, 2, 5, (0.0, 0.0, 0.0), (100.0, 0.0, 0.0)),
            ]
        )
        alternatives = jm.node_alternatives(
            pkg, {2: [10, 11, 12, 13]}, "continuation", "chord"
        )
        self.assertIsNotNone(alternatives)
        self.assertGreater(len(alternatives), 1)
        # Renaming every id keeps the same number of resolutions.
        renamed = copy.deepcopy(pkg)
        mapping = {key: key + 1000 for key in renamed["segments"]}
        renamed["segments"] = {
            mapping[key]: {
                **value,
                "id": mapping[key],
                "start": value["start"] + 2000,
                "end": value["end"] + 2000,
            }
            for key, value in renamed["segments"].items()
        }
        renamed["nodes"] = {
            key + 2000: value for key, value in renamed["nodes"].items()
        }
        again = jm.node_alternatives(
            renamed,
            {2002: [mapping[10], mapping[11], mapping[12], mapping[13]]},
            "continuation",
            "chord",
        )
        self.assertEqual(len(again), len(alternatives))

    def test_missing_tangents_abstain_and_leave_chord_rules_working(self):
        pkg = straight_chain(with_tangents=False)
        query = request(10, 1, 0, 11, 1, 255)
        engine = jm.Engine(pkg)
        self.assertEqual(
            engine.predict(query, "tangent:continuation:any_lane")["prediction"],
            jm.ABSTAIN,
        )
        self.assertEqual(
            engine.predict(query, "chord:continuation:any_lane")["prediction"],
            jm.SUCCESS,
        )


class DomainTest(unittest.TestCase):
    """The accepted corrected semantics, exercised through this study's rules."""

    def test_non_contiguous_train_lane_indexes_use_ordinals_not_renumbering(self):
        lanes = [
            lane(0, False, True),
            {
                "index": 1,
                "forward": True,
                "backward": True,
                "lane_type": "Vehicle",
                "vehicle": ["Car"],
                "category": "All",
            },
            lane(2, True, False),
        ]
        pkg = package(
            [
                segment(
                    10,
                    1,
                    2,
                    (0.0, 0.0, 0.0),
                    (0.0, 0.0, 100.0),
                    lanes=lanes,
                    start_direction=(0.0, 0.0, 1.0),
                    end_direction=(0.0, 0.0, -1.0),
                ),
                segment(
                    11,
                    2,
                    3,
                    (0.0, 0.0, 100.0),
                    (0.0, 0.0, 200.0),
                    lanes=lanes,
                    start_direction=(0.0, 0.0, 1.0),
                    end_direction=(0.0, 0.0, -1.0),
                ),
            ]
        )
        self.assertEqual(
            jm.Engine(pkg).predict(
                request(10, 2, 0, 11, 2, 255), "tangent:continuation:any_lane"
            )["prediction"],
            jm.SUCCESS,
        )
        # Lane 1 is a Car lane, so it is not a Train-capable request.
        self.assertEqual(
            jm.Engine(pkg).predict(
                request(10, 1, 0, 11, 1, 255), "tangent:continuation:any_lane"
            )["prediction"],
            jm.ABSTAIN,
        )

    def test_invert_swaps_the_required_travel_bit(self):
        lanes = [lane(0, True, False)]

        def build(flags):
            return package(
                [
                    segment(
                        10,
                        1,
                        2,
                        (0.0, 0.0, 0.0),
                        (0.0, 0.0, 100.0),
                        lanes=lanes,
                        flags=flags,
                    ),
                    segment(
                        11, 2, 3, (0.0, 0.0, 100.0), (0.0, 0.0, 200.0), lanes=lanes
                    ),
                ]
            )

        query = request(10, 0, 0, 11, 0, 255)
        plain = build(("Created", "Original"))
        inverted = build(("Created", "Original", "Invert"))
        self.assertTrue(model_can_leave(plain, query))
        self.assertEqual(
            jm.Engine(plain).predict(query, "chord:continuation:any_lane")[
                "prediction"
            ],
            jm.SUCCESS,
        )
        self.assertFalse(model_can_leave(inverted, query))
        self.assertEqual(
            jm.Engine(inverted).predict(query, "chord:continuation:any_lane")[
                "prediction"
            ],
            jm.NO_PATH,
        )

    def test_length_is_a_lower_bound_and_the_shortest_route_wins(self):
        lanes = [lane(0, True, True)]
        # Two routes from node 2 to node 3: a long detour (200 + 223.6) and a
        # straight 100. The rule that connects every pair is used so the
        # junction pairing does not remove one route before length matters.
        pkg = package(
            [
                segment(10, 0, 2, (0.0, 0.0, 0.0), (0.0, 0.0, 100.0), lanes=lanes),
                segment(20, 2, 6, (0.0, 0.0, 100.0), (200.0, 0.0, 100.0), lanes=lanes),
                segment(21, 6, 3, (200.0, 0.0, 100.0), (0.0, 0.0, 200.0), lanes=lanes),
                segment(22, 2, 7, (0.0, 0.0, 100.0), (0.0, 0.0, 150.0), lanes=lanes),
                segment(23, 7, 3, (0.0, 0.0, 150.0), (0.0, 0.0, 200.0), lanes=lanes),
                segment(30, 3, 4, (0.0, 0.0, 200.0), (0.0, 0.0, 300.0), lanes=lanes),
            ]
        )
        result = jm.Engine(pkg).predict(
            request(10, 0, 0, 30, 0, 255), "chord:turn:180:any_lane"
        )
        self.assertEqual(result["prediction"], jm.SUCCESS)
        self.assertAlmostEqual(result["detail"]["path_lower_bound_length"], 300.0)

    def test_orientation_reversal_on_a_real_package_keeps_every_prediction(self):
        accepted = binding.accepted_openings(
            binding.load_manifest(), verify_observations=False
        )
        entry = next(
            item
            for item in accepted["openings"]["openings"]
            if item["package"] == "stock-1"
        )
        container = exports.cached_net(accepted["packages"]["stock-1"]["locator"])
        native = topology.from_native(
            binding.load_json(binding.raw_dir(entry) / "networks.json.gz"), "stock-1"
        )
        pkg = exports.attach(native, exports.tangents(container["net"]))
        flipped = copy.deepcopy(pkg)
        for segment_id, value in flipped["segments"].items():
            flipped["segments"][segment_id] = {
                **value,
                "start": value["end"],
                "end": value["start"],
                "a": value["b"],
                "b": value["a"],
                "start_direction": value["end_direction"],
                "end_direction": value["start_direction"],
                "lanes": [
                    {**item, "forward": item["backward"], "backward": item["forward"]}
                    for item in value["lanes"]
                ],
            }
        plan = binding.load_json(binding.raw_dir(entry) / "query-freeze.json.gz")
        queries = []
        for index, item in binding.selected_requests(plan):
            queries.append(
                {
                    "flipped": request(
                        item["from"][0],
                        item["from"][1],
                        255 - item["from"][2],
                        item["to"][0],
                        item["to"][1],
                        255 - item["to"][2],
                    ),
                    "original": item,
                }
            )
        self.assertGreater(len(queries), 0)
        engine = jm.Engine(pkg)
        flipped_engine = jm.Engine(flipped)
        for rule in jm.rule_names():
            for item in queries:
                self.assertEqual(
                    engine.predict(item["original"], rule)["prediction"],
                    flipped_engine.predict(item["flipped"], rule)["prediction"],
                    (rule, item["original"]["from"]),
                )

    def test_id_and_order_renaming_on_a_real_package_keeps_every_prediction(self):
        accepted = binding.accepted_openings(
            binding.load_manifest(), verify_observations=False
        )
        entry = next(
            item
            for item in accepted["openings"]["openings"]
            if item["package"] == "stock-1"
        )
        container = exports.cached_net(accepted["packages"]["stock-1"]["locator"])
        native = topology.from_native(
            binding.load_json(binding.raw_dir(entry) / "networks.json.gz"), "stock-1"
        )
        pkg = exports.attach(native, exports.tangents(container["net"]))
        segment_map = {key: key + 100000 for key in pkg["segments"]}
        node_map = {key: key + 200000 for key in pkg["nodes"]}
        renamed = {
            "name": "renamed",
            "segments": {
                segment_map[key]: {
                    **value,
                    "id": segment_map[key],
                    "start": node_map[value["start"]],
                    "end": node_map[value["end"]],
                }
                for key, value in reversed(list(pkg["segments"].items()))
            },
            "nodes": {
                node_map[key]: value
                for key, value in reversed(list(pkg["nodes"].items()))
            },
            "tangents": {
                segment_map[key]: value for key, value in pkg["tangents"].items()
            },
            "tangent_missing": [],
        }
        plan = binding.load_json(binding.raw_dir(entry) / "query-freeze.json.gz")
        engine = jm.Engine(pkg)
        renamed_engine = jm.Engine(renamed)
        for _, item in binding.selected_requests(plan):
            moved = request(
                segment_map[item["from"][0]],
                item["from"][1],
                item["from"][2],
                segment_map[item["to"][0]],
                item["to"][1],
                item["to"][2],
            )
            for rule in jm.rule_names():
                self.assertEqual(
                    engine.predict(item, rule)["prediction"],
                    renamed_engine.predict(moved, rule)["prediction"],
                    (rule, item["from"]),
                )


class EquivalenceTest(unittest.TestCase):
    """This study's chord rules must reproduce the accepted frozen predictions."""

    def test_chord_continuation_matches_the_accepted_freeze(self):
        accepted = binding.accepted_openings(
            binding.load_manifest(), verify_observations=False
        )
        frozen = binding.load_json(
            binding.accepted_paths(binding.load_manifest())[
                "corrected/predictions.json"
            ]
        )
        by_id = {query["query_id"]: query for query in frozen["queries"]}
        pairs = (
            ("chord:continuation:any_lane", "junction:continuation:any_lane"),
            (
                "chord:continuation:orientation_index",
                "junction:continuation:orientation_index",
            ),
        )
        for entry in accepted["openings"]["openings"]:
            container = exports.cached_net(
                accepted["packages"][entry["package"]]["locator"]
            )
            native = topology.from_native(
                binding.load_json(binding.raw_dir(entry) / "networks.json.gz"),
                entry["opening"],
            )
            engine = jm.Engine(
                exports.attach(native, exports.tangents(container["net"]))
            )
            plan = binding.load_json(binding.raw_dir(entry) / "query-freeze.json.gz")
            for index, item in binding.selected_requests(plan):
                query = by_id[f"{entry['opening']}:{index}"]
                for rule, alias in pairs:
                    got = engine.predict(item, rule)
                    want = query["predictions"][alias]
                    self.assertEqual(
                        got["prediction"], want["prediction"], (query["query_id"], rule)
                    )
                    if got["prediction"] == jm.SUCCESS:
                        self.assertAlmostEqual(
                            got["detail"]["path_lower_bound_length"],
                            want["detail"]["path_lower_bound_length"],
                            places=6,
                        )

    def test_witness_agrees_with_the_frozen_verdict(self):
        accepted = binding.accepted_openings(
            binding.load_manifest(), verify_observations=False
        )
        entry = next(
            item
            for item in accepted["openings"]["openings"]
            if item["package"] == "stock-1"
        )
        container = exports.cached_net(accepted["packages"]["stock-1"]["locator"])
        native = topology.from_native(
            binding.load_json(binding.raw_dir(entry) / "networks.json.gz"), "stock-1"
        )
        pkg = exports.attach(native, exports.tangents(container["net"]))
        plan = binding.load_json(binding.raw_dir(entry) / "query-freeze.json.gz")
        engine = jm.Engine(pkg)
        for _, item in binding.selected_requests(plan):
            for rule in (jm.PRIMARY_REFERENCE, jm.PRIMARY_EQUIVALENT):
                found = diagnose.witness(pkg, item, rule)
                self.assertEqual(
                    found["prediction"], engine.predict(item, rule)["prediction"], rule
                )


class BindingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = binding.load_manifest()
        cls.accepted = binding.accepted_openings(
            cls.manifest, verify_observations=False
        )
        cls.expected, cls.per_opening = binding.expected_query_set(
            cls.accepted["openings"], cls.accepted["integrity"]
        )
        cls.predictions = binding.load_json(binding.PREDICTIONS)

    def test_manifest_is_closed(self):
        mutated = json.loads(json.dumps(self.manifest))
        mutated["unexpected"] = 1
        path = HERE / "manifest.mutation.tmp.json"
        try:
            path.write_text(json.dumps(mutated))
            with self.assertRaises(binding.BindingError):
                binding.load_manifest(path)
        finally:
            path.unlink(missing_ok=True)

    def test_threshold_outside_the_grid_is_rejected(self):
        with self.assertRaises(ValueError):
            jm.parse_rule("tangent:turn:47:any_lane")

    def test_duplicate_missing_and_extra_queries_are_rejected(self):
        duplicated = copy.deepcopy(self.predictions)
        duplicated["queries"].append(duplicated["queries"][0])
        with self.assertRaises(binding.BindingError):
            binding.verify_query_set(
                duplicated, self.accepted["openings"], self.expected
            )
        missing = copy.deepcopy(self.predictions)
        missing["queries"].pop()
        with self.assertRaises(binding.BindingError):
            binding.verify_query_set(missing, self.accepted["openings"], self.expected)
        extra = copy.deepcopy(self.predictions)
        extra["queries"][0]["plan_index"] += 1
        with self.assertRaises(binding.BindingError):
            binding.verify_query_set(extra, self.accepted["openings"], self.expected)

    def test_mutated_plan_request_is_rejected(self):
        mutated = copy.deepcopy(self.predictions)
        mutated["queries"][0]["request"]["from"] = [1, 0, 0]
        with self.assertRaises(binding.BindingError):
            binding.verify_query_set(mutated, self.accepted["openings"], self.expected)

    def test_source_hash_mutation_is_rejected(self):
        mutated = copy.deepcopy(self.predictions)
        name = next(iter(mutated["sources"]["own"]))
        mutated["sources"]["own"][name] = "0" * 64
        protocol = binding.load_json(binding.PROTOCOL)
        features = binding.load_json(binding.FEATURES)
        with self.assertRaises(binding.BindingError):
            binding.bind_observations(
                mutated,
                protocol,
                features,
                self.accepted["openings"],
                self.accepted["packages"],
            )

    def test_protocol_hash_mutation_is_rejected(self):
        mutated = copy.deepcopy(self.predictions)
        mutated["protocol_sha256"] = "0" * 64
        protocol = binding.load_json(binding.PROTOCOL)
        features = binding.load_json(binding.FEATURES)
        with self.assertRaises(binding.BindingError):
            binding.bind_observations(
                mutated,
                protocol,
                features,
                self.accepted["openings"],
                self.accepted["packages"],
            )

    def test_labels_are_bound_to_the_plan_index_and_request(self):
        bundles = binding.bind_observations(
            self.predictions,
            binding.load_json(binding.PROTOCOL),
            binding.load_json(binding.FEATURES),
            self.accepted["openings"],
            self.accepted["packages"],
        )
        query_id = next(iter(self.expected))
        query = self.expected[query_id]
        mutated = copy.deepcopy(bundles)
        bundle = mutated[query["opening"]]
        bundle["rows"][query["plan_index"]]["request"]["from"] = [1, 2, 3]
        with self.assertRaises(binding.BindingError):
            binding.labels(mutated, {query_id: query})

    def test_label_mutations(self):
        row = {
            "request": {"from": [1, 0, 0], "to": [2, 0, 255]},
            "result": {
                "complete": True,
                "released": True,
                "success": True,
                "positions": [[1, 0, 0], [2, 0, 255]],
                "length": 1.0,
                "flags": 4,
            },
        }
        self.assertEqual(binding.label(row)[0], binding.SUCCESS)
        for field in ("complete", "released", "success"):
            broken = copy.deepcopy(row)
            broken["result"][field] = "yes"
            with self.assertRaises(binding.BindingError):
                binding.label(broken)
        incomplete = copy.deepcopy(row)
        incomplete["result"]["complete"] = False
        self.assertEqual(binding.label(incomplete)[0], binding.UNKNOWN)
        mismatch = copy.deepcopy(row)
        mismatch["result"]["positions"] = [[9, 0, 0], [2, 0, 255]]
        self.assertEqual(binding.label(mismatch)[0], binding.UNKNOWN)
        failure = copy.deepcopy(row)
        failure["result"].update({"success": False, "positions": []})
        self.assertEqual(binding.label(failure)[0], binding.NO_PATH)

    def test_fold_leakage_is_rejected(self):
        # A package listed in both splits is a leak, not a design choice.
        mutated = json.loads(json.dumps(self.manifest))
        mutated["expected"]["openings_by_split"]["cohort"].append("stock-1")
        with self.assertRaises(binding.BindingError):
            binding.fold_plan(mutated, self.per_opening)
        # A split that does not cover every frozen package is also refused.
        dropped = json.loads(json.dumps(self.manifest))
        dropped["expected"]["openings_by_split"]["cohort"].remove("rio")
        with self.assertRaises(binding.BindingError):
            binding.fold_plan(dropped, self.per_opening)

    def test_folds_are_disjoint_and_cover_the_labelled_cohort(self):
        folds = binding.fold_plan(self.manifest, self.per_opening)["folds"]
        for fold in folds:
            self.assertFalse(set(fold["train"]) & set(fold["held_out"]))
            self.assertFalse(set(fold["selection_train"]) & set(fold["held_out"]))
        cohort = [
            fold for fold in folds if fold["kind"] == "cohort_leave_one_package_out"
        ]
        self.assertEqual(
            sorted(fold["held_out"][0] for fold in cohort),
            sorted(
                name
                for name, row in self.per_opening.items()
                if row["selected"] > 0 and name not in ("stock-1", "stock-2")
            ),
        )
        self.assertEqual(
            sorted(
                fold["held_out"][0]
                for fold in folds
                if fold["kind"].startswith("stock")
            ),
            ["stock-1", "stock-2"],
        )

    def test_freeze_guard_refuses_an_observation(self):
        with self.assertRaises(RuntimeError):
            __import__("freeze").input_only(HERE / "observation.json.gz")


class FreezePurityTest(unittest.TestCase):
    def test_predict_path_never_reads_an_observation(self):
        for name in ("junction_model.py", "export_topology.py"):
            text = (HERE / name).read_text()
            self.assertNotIn("observation.json.gz", text, name)
        # The freeze's documented order and its guard are the only places the
        # label file is named; the freeze path is exercised with a load_json
        # that raises on any attempt to open one.
        original = binding.load_json

        def guarded(path):
            if Path(path).name == "observation.json.gz":
                raise AssertionError("the freeze opened an observation")
            return original(path)

        binding.load_json = guarded
        try:
            accepted = binding.accepted_openings(
                binding.load_manifest(), verify_observations=False
            )
            binding.expected_query_set(accepted["openings"], accepted["integrity"])
        finally:
            binding.load_json = original


class OutputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluation = binding.load_json(binding.HERE / "evaluation.json")
        cls.protocol = binding.load_json(binding.PROTOCOL)
        cls.features = binding.load_json(binding.FEATURES)
        cls.predictions = binding.load_json(binding.PREDICTIONS)
        cls.bridge = binding.load_json(binding.HERE / "bridge-audit.json")

    def test_query_and_label_census(self):
        self.assertEqual(len(self.predictions["queries"]), 276)
        self.assertEqual(self.evaluation["labels"]["counts"]["success"], 27)
        self.assertEqual(self.evaluation["labels"]["counts"]["no_path"], 249)
        self.assertEqual(self.evaluation["labels"]["counts"]["unknown"], 0)

    def test_reference_reproduces_the_accepted_fitted_confusion(self):
        counts = self.evaluation["rules"][jm.PRIMARY_REFERENCE]["all"]["counts"]
        self.assertEqual(
            (counts["tp"], counts["fp"], counts["tn"], counts["fn"], counts["abstain"]),
            (26, 4, 245, 1, 0),
        )

    def test_correspondence_is_reported_with_its_own_counts(self):
        counts = self.evaluation["rules"][jm.PRIMARY_EQUIVALENT]["all"]["counts"]
        self.assertEqual(
            (counts["tp"], counts["fp"], counts["tn"], counts["fn"]), (27, 0, 249, 0)
        )
        self.assertEqual(
            self.evaluation["rules"][jm.PRIMARY_EQUIVALENT]["all"]["rates"][
                "abstention"
            ],
            0.0,
        )

    def test_every_rule_is_reported_and_none_is_adopted(self):
        self.assertEqual(set(self.evaluation["rules"]), set(self.protocol["rules"]))
        self.assertEqual(len(self.protocol["rules"]), 58)
        self.assertIn("hypotheses", self.protocol)
        self.assertNotIn("adopted", self.protocol)

    def test_folds_do_not_leak(self):
        for fold in self.evaluation["folds"]:
            self.assertFalse(set(fold["train_packages"]) & set(fold["held_out"]))
            self.assertNotIn(fold["held_out"][0], fold["selection_train"])
        kinds = [fold["kind"] for fold in self.evaluation["folds"]]
        self.assertEqual(kinds.count("cohort_leave_one_package_out"), 6)
        self.assertEqual(kinds.count("stock_control_held_out"), 2)

    def test_predictions_carry_their_queries_digest(self):
        import hashlib

        encoded = json.dumps(self.predictions["queries"], sort_keys=True).encode()
        self.assertEqual(
            hashlib.sha256(encoded).hexdigest(), self.predictions["queries_sha256"]
        )

    def test_tangents_are_complete_for_every_train_segment(self):
        self.assertEqual(self.features["tangents"]["missing"], 0)
        self.assertEqual(
            self.features["tangents"]["covered"],
            self.features["tangents"]["train_segments"],
        )
        self.assertEqual(
            self.predictions["openings"]["pittsburgh"]["tangent_missing"], []
        )

    def test_bridge_covers_the_stock_format_eight_container(self):
        self.assertEqual(self.bridge["status"], "export_bridge_established")
        self.assertEqual(
            self.bridge["packages"]["stock-1"]["status"],
            "export_derivable_with_own_catalog",
        )
        self.assertEqual(self.bridge["packages"]["stock-1"]["crp"]["format"], 8)
        self.assertFalse(
            self.bridge["packages"]["stock-1"]["section"]["current_version_section"]
        )
        self.assertEqual(self.bridge["totals"]["tangent_missing"], 0)
        for field, value in self.bridge["totals"]["fields"].items():
            self.assertEqual(value["rate"], 1.0, field)

    def test_error_mechanics_name_the_two_differing_junctions(self):
        diagnostics = binding.load_json(binding.HERE / "diagnostics.json")
        differences = diagnostics["input_only_geometry"]["packages"]["pittsburgh"]
        self.assertEqual(differences["nodes_differing"], 2)
        self.assertEqual(sorted(differences["differing_nodes"]), [3975, 5128])
        rows = diagnostics["error_mechanics"][jm.PRIMARY_REFERENCE]
        self.assertEqual(len(rows), 5)
        reference_nodes = {
            crossing["node"]
            for row in rows
            for crossing in row["witness_transitions_differing_by_measure"]
        }
        self.assertEqual(reference_nodes, {3975, 5128})
        self.assertEqual(diagnostics["error_mechanics"][jm.PRIMARY_EQUIVALENT], [])


if __name__ == "__main__":
    unittest.main()
