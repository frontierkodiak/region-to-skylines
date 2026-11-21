"""Tests for the outside-query model, its inventory, freeze and scoring.

Run from this directory:

    python3 -m unittest -v test_outside_query_model

The bridge tests need the map-factory's Python dependencies (numpy, Pillow) and
the accepted `.crp` packages on disk; they skip when either is absent.
"""

from __future__ import annotations

import collections
import gzip
import hashlib
import json
import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import evaluate  # noqa: E402
import inventory  # noqa: E402
import model  # noqa: E402
import predict  # noqa: E402
import topology  # noqa: E402

SOURCE = HERE.parent / "outside-v1"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(name):
    return json.loads((HERE / name).read_text())


def segment(segment_id, start, end, lanes, prefab="Highway", a=(0, 0, 0), b=(10, 0, 0)):
    return {
        "id": segment_id,
        "start": start,
        "end": end,
        "prefab": prefab,
        "a": tuple(a),
        "b": tuple(b),
        "lanes": lanes,
    }


def lane(index, direction, vehicle="Car", lane_type="Vehicle"):
    return {
        "index": index,
        "type": lane_type,
        "vehicle": vehicle,
        "category": "All",
        "direction": direction,
    }


def package(segments):
    return {
        "segments": {item["id"]: item for item in segments},
        "nodes": {},
        "node_flag_conflicts": [],
    }


class DirectionTests(unittest.TestCase):
    def test_all_direction_names_have_travel_bits(self):
        self.assertEqual(topology.DIRECTION_BITS["Forward"], (True, False))
        self.assertEqual(topology.DIRECTION_BITS["Backward"], (False, True))
        self.assertEqual(topology.DIRECTION_BITS["Both"], (True, True))
        self.assertEqual(topology.DIRECTION_BITS["None"], (False, False))

    def test_unknown_direction_is_rejected(self):
        with self.assertRaises(ValueError):
            topology.direction_bits("Sideways")

    def test_ship_both_direction_grants_both_ways(self):
        # The outside-v1 snapshot records a Ship lane as `Both` while its numeric
        # `flags` string is "1"; the model must use the recorded direction.
        item = topology._segment(
            {
                "id": 1,
                "start": 2,
                "end": 3,
                "a": (0, 0, 0),
                "b": (1, 0, 0),
                "lanes": [lane(0, "Both", vehicle="Ship")],
            },
            "Ship Path",
        )
        self.assertTrue(item["lanes"][0]["forward"])
        self.assertTrue(item["lanes"][0]["backward"])

    def test_mode_lanes_filter_by_vehicle_and_lane_type(self):
        item = {
            "lanes": [
                lane(0, "Forward", vehicle="Car"),
                lane(1, "Forward", vehicle="Ship"),
                {"index": 2, "type": "None", "vehicle": "None", "category": "All", "direction": "None"},
            ]
        }
        self.assertEqual([lane["index"] for lane in topology.mode_lanes(item, "road")], [0])
        self.assertEqual([lane["index"] for lane in topology.mode_lanes(item, "ship")], [1])
        self.assertEqual(topology.mode_lanes(item, "air"), [])


class TopologyTests(unittest.TestCase):
    def test_from_native_names_lanes_and_nodes(self):
        networks = {
            "segments": [
                {
                    "id": 7,
                    "start": 11,
                    "end": 12,
                    "a": (0, 0, 0),
                    "b": (10, 0, 0),
                    "prefab": "Highway",
                    "flags": "Created, Original",
                    "start_flags": "Created, Junction, Outside, OneWayOut",
                    "end_flags": "Created, Middle, Original",
                    "lanes": [lane(0, "Forward")],
                }
            ]
        }
        package = topology.from_native(networks, "sample")
        self.assertEqual(package["segments"][7]["prefab"], "Highway")
        self.assertEqual(package["nodes"][11]["flags"], {"Created", "Junction", "Outside", "OneWayOut"})
        self.assertEqual(package["node_flag_conflicts"], [])

    def test_conflicting_node_flags_are_reported_not_raised(self):
        networks = {
            "segments": [
                {
                    "id": 1,
                    "start": 5,
                    "end": 6,
                    "a": (0, 0, 0),
                    "b": (1, 0, 0),
                    "prefab": "Highway",
                    "flags": "Created",
                    "start_flags": "Created, OneWayIn",
                    "end_flags": "Created",
                    "lanes": [lane(0, "Forward")],
                },
                {
                    "id": 2,
                    "start": 5,
                    "end": 7,
                    "a": (0, 0, 0),
                    "b": (1, 0, 0),
                    "prefab": "Highway",
                    "flags": "Created",
                    "start_flags": "Created, OneWayOut",
                    "end_flags": "Created",
                    "lanes": [lane(0, "Forward")],
                },
            ]
        }
        package = topology.from_native(networks)
        self.assertEqual(len(package["node_flag_conflicts"]), 1)
        self.assertEqual(package["node_flag_conflicts"][0]["node"], 5)

    def test_endpoint_node_accepts_only_literal_offsets(self):
        item = segment(1, 2, 3, [lane(0, "Forward")])
        self.assertEqual(topology.endpoint_node(item, 0), 2)
        self.assertEqual(topology.endpoint_node(item, 255), 3)
        with self.assertRaises(ValueError):
            topology.endpoint_node(item, 128)

    def test_mode_index_skips_segments_without_the_vehicle(self):
        prepared = model.Prepared(
            package([segment(1, 1, 2, [lane(0, "Forward", vehicle="Ship")])]), "road"
        )
        self.assertEqual(prepared.segments, {})


class RuleTests(unittest.TestCase):
    def test_every_frozen_rule_parses(self):
        for rule in model.RULES:
            model.parse_rule(rule)

    def test_unknown_rule_raises(self):
        for bad in ("lane:any_lane:maybe", "junction:all:any_lane", "nonsense"):
            with self.assertRaises(ValueError):
                model.parse_rule(bad)

    def test_family_size_is_at_most_twelve_per_mode(self):
        self.assertLessEqual(len(model.RULES), 12)
        self.assertEqual(len(set(model.RULES)), len(model.RULES))

    def test_primary_rule_is_in_the_family(self):
        self.assertIn(model.PRIMARY_RULE, model.RULES)


class ModelTests(unittest.TestCase):
    def straight(self):
        # node 1 -- seg1 --> node 2 -- seg2 --> node 3
        return package(
            [
                segment(1, 1, 2, [lane(0, "Forward")]),
                segment(2, 2, 3, [lane(0, "Forward")]),
            ]
        )

    def test_one_way_chain_reaches_forward_only(self):
        prepared = model.Prepared(self.straight(), "road")
        forward = {"from": [1, 0, 0], "to": [2, 0, 255]}
        backward = {"from": [2, 0, 0], "to": [1, 0, 255]}
        self.assertEqual(
            model.predict(prepared, forward, "lane:any_lane:forbidden")["prediction"],
            model.SUCCESS,
        )
        self.assertEqual(
            model.predict(prepared, backward, "lane:any_lane:forbidden")["prediction"],
            model.NO_PATH,
        )

    def test_source_lane_direction_blocks_the_request(self):
        prepared = model.Prepared(self.straight(), "road")
        prediction = model.predict(
            prepared, {"from": [1, 0, 255], "to": [2, 0, 255]}, "lane:any_lane:forbidden"
        )
        self.assertEqual(prediction["prediction"], model.NO_PATH)
        self.assertEqual(prediction["detail"]["reason"], "source_lane_cannot_leave_node")

    def test_target_lane_direction_blocks_the_request(self):
        # seg2 is one-way 2->3, so a path may not arrive at node 2 on its lane.
        prepared = model.Prepared(self.straight(), "road")
        prediction = model.predict(
            prepared, {"from": [1, 0, 0], "to": [2, 0, 0]}, "lane:any_lane:forbidden"
        )
        self.assertEqual(prediction["prediction"], model.NO_PATH)
        self.assertEqual(prediction["detail"]["reason"], "target_lane_cannot_reach_node")

    def test_both_direction_lane_is_traversable_either_way(self):
        prepared = model.Prepared(
            package([segment(1, 1, 2, [lane(0, "Both", vehicle="Ship")])]), "ship"
        )
        for request in (
            {"from": [1, 0, 0], "to": [1, 0, 255]},
            {"from": [1, 0, 255], "to": [1, 0, 0]},
        ):
            self.assertEqual(
                model.predict(prepared, request, "lane:any_lane:forbidden")["prediction"],
                model.SUCCESS,
            )

    def test_any_lane_beats_index_same_on_a_lane_count_change(self):
        # A two-lane one-way joins a one-lane one-way: lane 1 cannot continue
        # under `index_same`, but it can under `any_lane`.
        package_ = package(
            [
                segment(1, 1, 2, [lane(0, "Forward"), lane(1, "Forward")]),
                segment(2, 2, 3, [lane(0, "Forward")]),
            ]
        )
        prepared = model.Prepared(package_, "road")
        request = {"from": [1, 1, 0], "to": [2, 0, 255]}
        self.assertEqual(
            model.predict(prepared, request, "lane:any_lane:forbidden")["prediction"],
            model.SUCCESS,
        )
        self.assertEqual(
            model.predict(prepared, request, "lane:index_same:forbidden")["prediction"],
            model.NO_PATH,
        )

    def test_reversal_hypothesis_is_inert_on_a_one_way_chain(self):
        # Re-entering a segment after a reversal still has to satisfy that
        # lane's direction grant, so `allowed` and `forbidden` predict alike.
        prepared = model.Prepared(self.straight(), "road")
        requests = [
            {"from": [1, 0, 0], "to": [2, 0, 255]},
            {"from": [2, 0, 0], "to": [1, 0, 255]},
            {"from": [2, 0, 255], "to": [1, 0, 0]},
        ]
        for request in requests:
            allowed = model.predict(prepared, request, "lane:any_lane:allowed")
            forbidden = model.predict(prepared, request, "lane:any_lane:forbidden")
            self.assertEqual(allowed["prediction"], forbidden["prediction"])

    def test_missing_lane_abstains(self):
        prepared = model.Prepared(self.straight(), "road")
        prediction = model.predict(
            prepared, {"from": [1, 9, 0], "to": [2, 0, 255]}, "lane:any_lane:forbidden"
        )
        self.assertEqual(prediction["prediction"], model.ABSTAIN)

    def test_missing_segment_abstains(self):
        prepared = model.Prepared(self.straight(), "road")
        prediction = model.predict(
            prepared, {"from": [99, 0, 0], "to": [2, 0, 255]}, "lane:any_lane:forbidden"
        )
        self.assertEqual(prediction["prediction"], model.ABSTAIN)

    def test_weak_component_ignores_direction(self):
        prepared = model.Prepared(self.straight(), "road")
        request = {"from": [2, 0, 0], "to": [1, 0, 255]}
        self.assertEqual(
            model.predict(prepared, request, "weak_component")["prediction"], model.SUCCESS
        )
        self.assertEqual(
            model.predict(prepared, request, "directed_segment")["prediction"], model.NO_PATH
        )

    def test_always_baselines(self):
        prepared = model.Prepared(self.straight(), "road")
        request = {"from": [1, 0, 0], "to": [2, 0, 255]}
        self.assertEqual(
            model.predict(prepared, request, "always_fail")["prediction"], model.NO_PATH
        )
        self.assertEqual(
            model.predict(prepared, request, "always_candidate")["prediction"], model.SUCCESS
        )

    def test_length_bound_rejects_a_path_over_the_cap(self):
        long = package(
            [
                segment(1, 1, 2, [lane(0, "Forward")], a=(0, 0, 0), b=(80000, 0, 0)),
                segment(2, 2, 3, [lane(0, "Forward")], a=(80000, 0, 0), b=(160000, 0, 0)),
            ]
        )
        prepared = model.Prepared(long, "road")
        prediction = model.predict(
            prepared, {"from": [1, 0, 0], "to": [2, 0, 255]}, "lane:any_lane:forbidden"
        )
        self.assertEqual(prediction["prediction"], model.NO_PATH)

    def test_predictions_are_deterministic_and_order_independent(self):
        package_ = package(
            [
                segment(1, 1, 2, [lane(0, "Forward"), lane(1, "Forward")]),
                segment(2, 2, 3, [lane(0, "Forward")]),
                segment(3, 3, 4, [lane(0, "Backward")]),
            ]
        )
        prepared = model.Prepared(package_, "road")
        request = {"from": [1, 0, 0], "to": [2, 0, 255]}
        for rule in model.RULES:
            first = model.predict(prepared, request, rule)
            second = model.predict(prepared, rule=rule, request=request)
            self.assertEqual(first, second)
            self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_model_module_performs_no_io(self):
        source = (HERE / "model.py").read_text()
        for forbidden in ("open(", "json.load", "gzip", "pathlib"):
            self.assertNotIn(forbidden, source)


class InventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (HERE / "inventory.json").exists():
            raise unittest.SkipTest("run inventory.py first")
        cls.inventory = load("inventory.json")
        cls.queries = {query["query_id"]: query for query in cls.inventory["queries"]}

    def test_source_evidence_hash_matches_the_file(self):
        actual = sha((SOURCE / "evidence.json").read_bytes())
        self.assertEqual(self.inventory["source"]["evidence_sha256"], actual)

    def test_every_recorded_raw_hash_matches_its_bytes(self):
        cache = {}
        for query in self.inventory["queries"]:
            raw = query["raw"]
            if not raw["observation_sha256"]:
                continue
            path = SOURCE / raw["observation"]
            if path not in cache:
                cache[path] = sha(gzip.decompress(path.read_bytes()))
            self.assertEqual(cache[path], raw["observation_sha256"], str(path))

    def test_every_network_hash_matches_its_bytes(self):
        cache = {}
        for query in self.inventory["queries"]:
            raw = query["raw"]
            if not raw["networks_sha256"]:
                continue
            path = SOURCE / raw["networks"]
            if path not in cache:
                cache[path] = sha(gzip.decompress(path.read_bytes()))
            self.assertEqual(cache[path], raw["networks_sha256"], str(path))

    def test_no_anomaly_except_the_three_attempts_without_networks(self):
        anomalies = self.inventory["anomalies"]
        self.assertEqual({item["kind"] for item in anomalies}, {"missing_networks"})
        self.assertEqual(len(anomalies), 3)

    def test_every_row_is_accounted_for_exactly_once(self):
        counts = self.inventory["counts"]
        self.assertEqual(counts["queries"], 876)
        classified = sum(counts["by_stratum"].values())
        self.assertEqual(classified, counts["queries"])

    def test_eligible_counts_by_mode(self):
        self.assertEqual(
            self.inventory["counts"]["eligible_by_mode"],
            {"air": 10, "road": 352, "ship": 16},
        )
        self.assertEqual(
            self.inventory["counts"]["eligible_by_stratum"],
            {"primary_distinct_edge": 342, "same_edge": 36},
        )

    def test_eligible_queries_have_a_boolean_label(self):
        for query in self.inventory["queries"]:
            if query["eligible"]:
                self.assertIn(query["observed"], (True, False), query["query_id"])
                self.assertIn(query["label"], ("success", "failure"))

    def test_exclusions_never_become_a_failure_label(self):
        for query in self.inventory["queries"]:
            if not query["eligible"]:
                self.assertIsNone(query["label"] if query["exclusion"] == "no_request_recorded" else None)
                if query["exclusion"] == "protocol_fields_absent":
                    self.assertEqual(query["label_status"], "excluded")

    def test_earliest_collector_requests_are_unknown_not_failed(self):
        unclassified = [
            query
            for query in self.inventory["queries"]
            if query["stratum"] == "unclassified_protocol"
        ]
        self.assertEqual(len(unclassified), 64)
        for query in unclassified:
            self.assertEqual(query["exclusion"], "protocol_fields_absent")
            self.assertEqual(query["label_status"], "excluded")
            self.assertFalse(query["eligible"])
        # Not scored: they stay outside every eligible count.
        self.assertFalse(
            any(query["eligible"] for query in unclassified)
        )

    def test_midpoints_are_correlated_repeats_of_their_boundary_request(self):
        self.assertEqual(
            self.inventory["counts"]["midpoint_pairs"], self.inventory["counts"]["midpoint_agree"]
        )
        self.assertEqual(self.inventory["counts"]["midpoint_pairs"], 378)
        for pair in self.inventory["midpoint_pairs"]:
            self.assertTrue(pair["agree"])

    def test_reversal_siblings_are_recorded(self):
        reversed_queries = [query for query in self.inventory["queries"] if query.get("reverse_of")]
        self.assertTrue(reversed_queries)
        for query in reversed_queries:
            other = self.queries[query["reverse_of"]]
            self.assertEqual(query["request"]["from"], other["request"]["to"])
            self.assertEqual(query["request"]["to"], other["request"]["from"])

    def test_requests_json_carries_no_label(self):
        requests = load("requests.json")
        self.assertEqual(len(requests["requests"]), 378)
        for entry in requests["requests"]:
            self.assertEqual(
                set(entry), {"query_id", "slug", "attempt_id", "mode", "stratum", "request"}
            )
        serialized = json.dumps(requests)
        for forbidden in ("observed", "path_result", "label"):
            self.assertNotIn(f'"{forbidden}"', serialized)


class FreezeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (HERE / "predictions.json").exists():
            raise unittest.SkipTest("run predict.py first")
        cls.protocol = load("protocol.json")
        cls.predictions = load("predictions.json")

    def test_protocol_binds_the_predictions_file(self):
        self.assertEqual(
            self.protocol["predictions_sha256"],
            sha((HERE / "predictions.json").read_bytes()),
        )

    def test_predictions_are_input_only(self):
        for record in self.predictions["predictions"]:
            self.assertEqual(set(record), {
                "query_id", "slug", "attempt_id", "mode", "stratum", "request", "rules"
            })
            self.assertEqual(set(record["rules"]), set(model.RULES))

    def test_protocol_records_the_same_rule_family(self):
        self.assertEqual(self.protocol["rules"], model.RULES)
        self.assertEqual(self.protocol["primary_rule"], model.PRIMARY_RULE)
        self.assertLessEqual(self.protocol["rules_per_mode"], 12)

    def test_predict_is_reproducible_for_a_sample(self):
        requests = load("requests.json")
        entry = requests["requests"][0]
        opening = next(
            item
            for item in requests["openings"]
            if item["key"] == f"{entry['slug']}/{entry['attempt_id']}"
        )
        raw = gzip.decompress((SOURCE / opening["networks"]["path"]).read_bytes())
        package = topology.from_native(json.loads(raw))
        prepared = model.Prepared(package, entry["mode"])
        record = next(
            item
            for item in self.predictions["predictions"]
            if item["query_id"] == entry["query_id"]
        )
        replayed = {
            rule: model.predict(prepared, entry["request"], rule) for rule in model.RULES
        }
        self.assertEqual(replayed, record["rules"])

    def test_no_prediction_reads_a_label(self):
        source = (HERE / "predict.py").read_text()
        for forbidden in ('"inventory.json"', '"evidence.json"', '"observed"', '"label"', '"path_result"'):
            self.assertNotIn(forbidden, source)


class MetricTests(unittest.TestCase):
    def test_precision_and_recall(self):
        metrics = evaluate.confusion(
            [
                (model.SUCCESS, True),
                (model.SUCCESS, False),
                (model.NO_PATH, False),
                (model.NO_PATH, True),
            ]
        )
        self.assertEqual((metrics["TP"], metrics["FP"], metrics["TN"], metrics["FN"]), (1, 1, 1, 1))
        self.assertEqual(metrics["precision"], 0.5)
        self.assertEqual(metrics["recall"], 0.5)
        self.assertEqual(metrics["precision"], metrics["recall"])

    def test_one_class_metrics_are_marked_not_estimable(self):
        metrics = evaluate.confusion([(model.SUCCESS, True), (model.NO_PATH, True)])
        self.assertEqual(metrics["precision"], 1.0)
        self.assertEqual(metrics["recall"], 0.5)
        self.assertFalse(metrics["classes"]["estimable"])
        self.assertEqual(metrics["classes"]["negatives"], 0)

    def test_empty_denominators_stay_null(self):
        metrics = evaluate.confusion([])
        self.assertIsNone(metrics["precision"])
        self.assertIsNone(metrics["recall"])
        self.assertIsNone(metrics["coverage"])

    def test_abstentions_are_counted_not_guessed(self):
        metrics = evaluate.confusion([(model.ABSTAIN, True), (model.SUCCESS, True)])
        self.assertEqual(metrics["abstain"], 1)
        self.assertEqual(metrics["TP"], 1)


@unittest.skipUnless((HERE / "bridge.json").exists(), "run bridge.py first")
class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = load("bridge.json")
        cls.catalogs = load("catalogs.json")

    def test_bridge_answered_yes(self):
        self.assertEqual(self.bridge["answer"], "yes")

    def test_every_package_reproduces_the_model_inputs(self):
        for slug, report in self.bridge["packages_report"].items():
            self.assertTrue(report["segment_ids_equal"], slug)
            self.assertEqual(report["start_end_equal"], report["segments_native"], slug)
            self.assertEqual(report["prefab_equal"], report["segments_native"], slug)
            self.assertEqual(report["lanes_equal"], report["segments_native"], slug)
            self.assertTrue(report["mode_inputs_equal"], slug)
            self.assertEqual(report["missing"], [], slug)

    def test_no_outside_flag_disagreement(self):
        for slug, report in self.bridge["packages_report"].items():
            self.assertEqual(report["node_flags_differ_outside_disagreements"], 0, slug)

    def test_prefab_lane_templates_are_unique(self):
        self.assertTrue(self.catalogs["prefab_lanes"])
        for prefab, variants in self.catalogs["prefab_variants"].items():
            self.assertEqual(variants, 1, prefab)
            self.assertIsNotNone(self.catalogs["prefab_lanes"][prefab])

    def test_every_fold_covers_the_fields_the_model_reads(self):
        # The two flag-name catalogs are reported, not required to be complete:
        # a flag value that appears in one package only cannot be named by a
        # catalog built from the other eight, and the model does not read flags.
        for slug, fold in self.bridge["fold_cross_validation"].items():
            self.assertEqual(fold["prefab_uncovered"], [], slug)
            self.assertIsInstance(fold["node_flag_values_uncovered"], list)
            self.assertIsInstance(fold["segment_flag_values_uncovered"], list)

    def test_catalogs_are_hash_bound(self):
        self.assertEqual(
            self.bridge["catalog"]["sha256_catalogs_json"],
            sha((HERE / "catalogs.json").read_bytes()),
        )


@unittest.skipUnless((HERE / "evaluation.json").exists(), "run evaluate.py first")
class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluation = load("evaluation.json")
        cls.integrity = load("integrity.json")

    def test_all_integrity_assertions_pass(self):
        self.assertTrue(self.integrity["all_ok"])
        failed = [item for item in self.integrity["assertions"] if not item["ok"]]
        self.assertEqual(failed, [])

    def test_evaluation_binds_the_frozen_predictions(self):
        self.assertEqual(
            self.evaluation["predictions_sha256"],
            sha((HERE / "predictions.json").read_bytes()),
        )

    def test_every_eligible_query_is_scored_once(self):
        primary = self.evaluation["by_rule"][model.PRIMARY_RULE]["primary_distinct_edge"]
        same_edge = self.evaluation["by_rule"][model.PRIMARY_RULE]["same_edge"]
        self.assertEqual(
            primary["n"] + same_edge["n"], self.evaluation["counts"]["eligible"]
        )

    def test_primary_stratum_has_both_classes(self):
        metrics = self.evaluation["by_rule"][model.PRIMARY_RULE]["primary_distinct_edge"]
        self.assertTrue(metrics["classes"]["estimable"])

    def test_ship_and_air_are_one_class(self):
        for mode in ("ship", "air"):
            self.assertFalse(self.evaluation["one_class"][mode]["discrimination_estimable"])
            metrics = self.evaluation["by_rule"][model.PRIMARY_RULE]["by_mode_primary"][mode]
            self.assertFalse(metrics["classes"]["estimable"])
            self.assertEqual(metrics["classes"]["negatives"], 0)
            self.assertIn("estimable", self.evaluation["one_class"][mode]["note"])

    def test_every_disagreement_is_a_native_length_denial(self):
        self.assertEqual(self.evaluation["unexplained_disagreements"], [])
        for rule, items in self.evaluation["disagreements"].items():
            for item in items:
                if item["relation"] == "false_positive":
                    self.assertEqual(item["native"]["flags"], 8, item["query_id"])
                    self.assertEqual(item["native"]["length"], model.MAX_LENGTH)
                elif item["relation"] == "false_negative":
                    self.fail(f"unexpected false negative: {item['query_id']}")

    def test_length_lower_bound_never_binds(self):
        self.assertFalse(self.evaluation["length_check"]["binds"])
        self.assertLess(self.evaluation["length_check"]["max_undirected_chord_over_cap"], 0.6)

    def test_leave_one_package_out_uses_the_frozen_criterion(self):
        folds = self.evaluation["leave_one_package_out"]
        self.assertTrue(folds)
        for fold in folds:
            if not fold["estimable"]:
                self.assertIsNone(fold["selected_rule"])
            else:
                self.assertIn(fold["selected_rule"], model.RULES)

    def test_correlated_repeats_agree(self):
        repeats = self.evaluation["repeats"]
        self.assertEqual(repeats["cross_opening_agree"], repeats["cross_opening_pairs"])
        self.assertEqual(repeats["midpoint"]["agree"], repeats["midpoint"]["pairs"])

    def test_no_always_fail_accuracy_headline(self):
        metrics = self.evaluation["by_rule"]["always_fail"]["primary_distinct_edge"]
        self.assertIsNone(metrics["precision"])
        serialized = json.dumps(self.evaluation)
        self.assertNotIn('"accuracy"', serialized)


if __name__ == "__main__":
    unittest.main()
