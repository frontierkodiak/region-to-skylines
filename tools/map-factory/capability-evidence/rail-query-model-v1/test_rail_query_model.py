"""Tests for the query-scoped rail reachability model, evaluator and bridge.

The invariance tests are the point of this study's guard rails: a prediction
must not depend on how the export happens to number segments or nodes, on which
end of a segment the game calls "start", or on any observation. The bridge tests
read one frozen package read-only and never write to it.
"""

import copy
import hashlib
import json
import unittest
from pathlib import Path

import bridge
import evaluate
import model
import predict
import topology

HERE = Path(__file__).resolve().parent
TRAIN = ("Vehicle", "Train", "All")


def segment(
    identity,
    start,
    end,
    a,
    b,
    lanes=None,
    flags=("Created", "Original"),
    prefab="Train Track",
):
    lanes = lanes or [0, 1]
    return {
        "id": identity,
        "start": start,
        "end": end,
        "a": tuple(a),
        "b": tuple(b),
        "flags": set(flags),
        "prefab": prefab,
        "lanes": [
            {
                "index": index,
                "forward": index == 1,
                "backward": index == 0,
                "lane_type": TRAIN[0],
                "vehicle": [TRAIN[1]],
                "category": TRAIN[2],
            }
            for index in lanes
        ],
    }


def package(segments, outside=()):
    nodes = {}
    for item in segments:
        nodes.setdefault(item["start"], {"flags": set(), "position": item["a"]})
        nodes.setdefault(item["end"], {"flags": set(), "position": item["b"]})
    for node in outside:
        nodes[node]["flags"].add("Outside")
    return {
        "name": "fixture",
        "segments": {item["id"]: item for item in segments},
        "nodes": nodes,
    }


def chain():
    """Two segments in a straight line, Outside at both far nodes."""
    return package(
        [
            segment(10, 1, 2, (0.0, 0.0, 0.0), (0.0, 0.0, 100.0)),
            segment(11, 2, 3, (0.0, 0.0, 100.0), (0.0, 0.0, 200.0)),
        ],
        outside=(1, 3),
    )


def tee():
    """A straight A-B continuation through node 2, and a 90 degree branch C into 2."""
    return package(
        [
            segment(10, 1, 2, (0.0, 0.0, 0.0), (0.0, 0.0, 100.0)),
            segment(11, 2, 3, (0.0, 0.0, 100.0), (0.0, 0.0, 200.0)),
            segment(12, 4, 2, (100.0, 0.0, 100.0), (0.0, 0.0, 100.0)),
        ],
        outside=(1, 3, 4),
    )


def request(source, source_lane, source_offset, target, target_lane, target_offset):
    return {
        "from": [source, source_lane, source_offset],
        "to": [target, target_lane, target_offset],
        "name": "directed-outside-to-outside",
        "position_kind": "boundary",
        "diagnostic": False,
        "endpoint_edges": ["north", "south"],
    }


def rename(pkg, segment_ids, node_ids):
    renamed = copy.deepcopy(pkg)
    renamed["segments"] = {
        segment_ids[key]: {
            **value,
            "id": segment_ids[key],
            "start": node_ids[value["start"]],
            "end": node_ids[value["end"]],
        }
        for key, value in pkg["segments"].items()
    }
    renamed["nodes"] = {node_ids[key]: value for key, value in pkg["nodes"].items()}
    return (
        renamed,
        {value: key for key, value in segment_ids.items()},
        {value: key for key, value in node_ids.items()},
    )


def reverse_orientation(pkg):
    """Keep the physical track, flip which node the export calls the start."""
    flipped = copy.deepcopy(pkg)
    flipped["segments"] = {}
    for segment_id, value in pkg["segments"].items():
        flipped["segments"][segment_id] = {
            **value,
            "start": value["end"],
            "end": value["start"],
            "a": value["b"],
            "b": value["a"],
            "lanes": [
                {**lane, "forward": lane["backward"], "backward": lane["forward"]}
                for lane in value["lanes"]
            ],
        }
    return flipped


def flip_request(req):
    """Re-express the same physical request after `reverse_orientation`.

    Reversing a segment keeps the lane index and swaps its travel bits, and it
    moves the node that offset 0 names to the other end, so both offsets flip.
    """
    source = req["from"]
    target = req["to"]
    return request(
        source[0],
        source[1],
        0 if source[2] == 255 else 255,
        target[0],
        target[1],
        0 if target[2] == 255 else 255,
    )


class ModelTest(unittest.TestCase):
    def test_chain_is_reachable_both_directions(self):
        pkg = chain()
        forward = request(10, 1, 0, 11, 1, 255)
        backward = request(11, 0, 255, 10, 0, 0)
        for rule in ("junction:continuation:any_lane", "lane:any_lane:forbidden"):
            self.assertEqual(
                model.predict(pkg, forward, rule)["prediction"], model.SUCCESS
            )
            self.assertEqual(
                model.predict(pkg, backward, rule)["prediction"], model.SUCCESS
            )

    def test_wrong_source_direction_is_not_reachable(self):
        pkg = chain()
        # Offset 255 needs the backward lane, so the forward-only lane cannot leave.
        bad = request(10, 1, 255, 11, 1, 255)
        self.assertEqual(
            model.predict(pkg, bad, model.FITTED_RULE),
            {
                "prediction": model.NO_PATH,
                "detail": {"reason": "source_lane_cannot_leave_node"},
            },
        )

    def test_wrong_target_direction_is_not_reachable(self):
        pkg = chain()
        # Arriving at offset 0 means travelling backward, so the forward-only
        # lane cannot be the target lane.
        bad = request(10, 1, 0, 11, 1, 0)
        self.assertEqual(
            model.predict(pkg, bad, model.FITTED_RULE)["prediction"], model.NO_PATH
        )
        self.assertEqual(
            model.predict(pkg, bad, model.FITTED_RULE)["detail"]["reason"],
            "target_lane_cannot_reach_node",
        )
        # A target at the near offset is a reversal for this geometry, and the
        # continuation rule forbids reversing inside a node.
        self.assertEqual(
            model.predict(pkg, request(10, 1, 0, 11, 0, 0), model.FITTED_RULE)[
                "prediction"
            ],
            model.NO_PATH,
        )

    def test_junction_continuation_keeps_the_straight_pair(self):
        pkg = tee()
        straight = request(10, 1, 0, 11, 1, 255)
        branch_to_branch = request(12, 1, 0, 11, 1, 255)
        self.assertEqual(
            model.predict(pkg, straight, model.FITTED_RULE)["prediction"], model.SUCCESS
        )
        # The branch is not the straightest continuation of segment 10, so the
        # continuation junction rule does not connect it.
        self.assertEqual(
            model.predict(pkg, branch_to_branch, model.FITTED_RULE)["prediction"],
            model.NO_PATH,
        )
        # The unconstrained junction family connects it, which is what the
        # junction hypothesis is meant to remove.
        self.assertEqual(
            model.predict(pkg, branch_to_branch, "lane:any_lane:forbidden")[
                "prediction"
            ],
            model.SUCCESS,
        )

    def test_absent_inputs_abstain(self):
        pkg = chain()
        missing_segment = request(99, 0, 0, 11, 1, 255)
        missing_lane = request(10, 7, 0, 11, 1, 255)
        for req in (missing_segment, missing_lane):
            self.assertEqual(
                model.predict(pkg, req, model.FITTED_RULE)["prediction"], model.ABSTAIN
            )
        empty = {"name": "empty", "segments": {}, "nodes": {}}
        self.assertEqual(
            model.predict(empty, missing_segment, model.FITTED_RULE)["prediction"],
            model.ABSTAIN,
        )

    def test_baselines(self):
        pkg = chain()
        req = request(10, 1, 0, 11, 1, 255)
        self.assertEqual(
            model.predict(pkg, req, "always_fail")["prediction"], model.NO_PATH
        )
        self.assertEqual(
            model.predict(pkg, req, "always_candidate")["prediction"], model.SUCCESS
        )
        self.assertEqual(
            model.predict(pkg, req, "weak_component")["prediction"], model.SUCCESS
        )

    def test_weak_component_separates_disjoint_tracks(self):
        pkg = package(
            [
                segment(10, 1, 2, (0.0, 0.0, 0.0), (0.0, 0.0, 100.0)),
                segment(11, 3, 4, (500.0, 0.0, 0.0), (500.0, 0.0, 100.0)),
            ],
            outside=(1, 4),
        )
        req = request(10, 1, 0, 11, 1, 255)
        self.assertEqual(
            model.predict(pkg, req, "weak_component")["prediction"], model.NO_PATH
        )
        self.assertEqual(
            model.predict(pkg, req, "lane:any_lane:forbidden")["prediction"],
            model.NO_PATH,
        )

    def test_unknown_rule_is_rejected(self):
        with self.assertRaises(ValueError):
            model.parse_rule("lane:nope:forbidden")
        with self.assertRaises(ValueError):
            model.parse_rule("junction:continuation:nope")

    def test_segment_and_node_renaming_is_invariant(self):
        pkg = tee()
        req = request(10, 1, 0, 11, 1, 255)
        segment_ids = {10: 501, 11: 900002, 12: 7}
        node_ids = {1: 400001, 2: 3, 3: 88, 4: 120000}
        renamed, back_segments, back_nodes = rename(pkg, segment_ids, node_ids)
        renamed_request = request(segment_ids[10], 1, 0, segment_ids[11], 1, 255)
        for rule in model.RULES:
            self.assertEqual(
                model.predict(pkg, req, rule)["prediction"],
                model.predict(renamed, renamed_request, rule)["prediction"],
                rule,
            )
        # And the renaming round-trips, so a query id is a graph reference only.
        self.assertEqual(back_segments[501], 10)
        self.assertEqual(back_nodes[3], 2)

    def test_segment_order_does_not_matter(self):
        pkg = tee()
        req = request(12, 1, 0, 11, 1, 255)
        shuffled = copy.deepcopy(pkg)
        shuffled["segments"] = dict(reversed(list(pkg["segments"].items())))
        for rule in model.RULES:
            self.assertEqual(
                model.predict(pkg, req, rule)["prediction"],
                model.predict(shuffled, req, rule)["prediction"],
                rule,
            )

    def test_orientation_reversal_is_invariant(self):
        pkg = chain()
        req = request(10, 1, 0, 11, 1, 255)
        flipped = reverse_orientation(pkg)
        flipped_request = flip_request(req)
        for rule in ("lane:any_lane:forbidden", model.FITTED_RULE):
            self.assertEqual(
                model.predict(pkg, req, rule)["prediction"],
                model.predict(flipped, flipped_request, rule)["prediction"],
                rule,
            )

    def test_model_has_no_outcome_or_observation_access(self):
        for name in (
            "observation.json",
            "observation.json.gz",
            "evaluation.json",
            "verification.json",
            "scorer",
        ):
            source = (HERE / "model.py").read_text()
            self.assertNotIn(name, source)


class RealPackageInvarianceTest(unittest.TestCase):
    """The invariance tests again on a frozen real package, not a fixture."""

    @classmethod
    def setUpClass(cls):
        openings = json.loads((HERE / "openings.json").read_text())
        entry = next(item for item in openings["openings"] if item["opening"] == "rio")
        raw = bridge.CAPABILITY / entry["raw"]
        cls.package = topology.load_native(raw / "networks.json.gz", "rio")
        plan = bridge.load_json(raw / "query-freeze.json.gz")
        cls.requests = [
            request
            for request in plan["plan"]["requests"]
            if not request["diagnostic"] and request["position_kind"] == "boundary"
        ]
        segment_ids = sorted(cls.package["segments"])
        node_ids = sorted(cls.package["nodes"])
        cls.segment_ids = {key: (key * 7919) % 100003 + 1 for key in segment_ids}
        cls.node_ids = {key: (key * 104729) % 200003 + 1 for key in node_ids}
        assert len(set(cls.segment_ids.values())) == len(segment_ids)
        assert len(set(cls.node_ids.values())) == len(node_ids)
        cls.renamed, _, _ = rename(cls.package, cls.segment_ids, cls.node_ids)

    def test_it_has_requests(self):
        self.assertEqual(len(self.requests), 6)

    def test_id_renaming_does_not_change_a_prediction(self):
        for req in self.requests:
            mapped = request(
                self.segment_ids[req["from"][0]],
                req["from"][1],
                req["from"][2],
                self.segment_ids[req["to"][0]],
                req["to"][1],
                req["to"][2],
            )
            for rule in (model.PRIMARY_RULE, model.FITTED_RULE, "weak_component"):
                self.assertEqual(
                    model.predict(self.package, req, rule)["prediction"],
                    model.predict(self.renamed, mapped, rule)["prediction"],
                    rule,
                )

    def test_orientation_reversal_does_not_change_a_prediction(self):
        flipped = reverse_orientation(self.package)
        for req in self.requests:
            for rule in (model.PRIMARY_RULE, model.FITTED_RULE):
                self.assertEqual(
                    model.predict(self.package, req, rule)["prediction"],
                    model.predict(flipped, flip_request(req), rule)["prediction"],
                    rule,
                )


class FrozenResultTest(unittest.TestCase):
    """Guard the corrected measured result; these are the study's recorded output."""

    def setUp(self):
        self.evaluation = json.loads(
            (HERE / "corrected" / "evaluation.json").read_text()
        )

    def test_recorded_confusions(self):
        rules = self.evaluation["result"]["rules"]
        primary = rules["lane:orientation_index:forbidden"]
        fitted = rules["junction:continuation:any_lane"]
        self.assertEqual(
            (
                primary["tp"],
                primary["fp"],
                primary["tn"],
                primary["fn"],
                primary["abstain"],
            ),
            (11, 198, 51, 16, 0),
        )
        self.assertEqual(
            (fitted["tp"], fitted["fp"], fitted["tn"], fitted["fn"], fitted["abstain"]),
            (26, 4, 245, 1, 0),
        )
        self.assertAlmostEqual(fitted["precision"], 26 / 30)
        self.assertAlmostEqual(fitted["recall"], 26 / 27)

    def test_controls_and_cohort_groups(self):
        """The stock controls are the study's own check: they must be exact."""
        stock = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
        cohort = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
        for entry in self.evaluation["result"]["packages"].values():
            target = stock if entry["split"] == "stock_controls" else cohort
            for key in target:
                target[key] += entry["rules"][model.FITTED_RULE][key]
        self.assertEqual(stock, {"tp": 16, "fp": 0, "tn": 16, "fn": 0})
        self.assertEqual(cohort, {"tp": 10, "fp": 4, "tn": 229, "fn": 1})

    def test_zero_query_packages_are_unscored(self):
        packages = self.evaluation["result"]["packages"]
        for opening in ("charleston", "grand-canyon", "yosemite"):
            scored = sum(packages[opening]["labels"].values())
            self.assertEqual(scored, 0, opening)
            for rule in self.evaluation["result"]["rules"]:
                self.assertIsNone(packages[opening]["rules"][rule]["precision"], rule)
                self.assertIsNone(packages[opening]["rules"][rule]["recall"], rule)

    def test_bridge_status_and_model_domain(self):
        bridge_report = json.loads((HERE / "corrected" / "bridge.json").read_text())
        self.assertEqual(bridge_report["status"], "bridge_established")
        self.assertTrue(bridge_report["model_input_domain"]["digests_identical"])
        for field in bridge.MODEL_FIELDS:
            self.assertEqual(bridge_report["fields"][field]["rate"], 1.0, field)
        self.assertEqual(
            bridge_report["prediction_agreement"]["queries"],
            bridge_report["prediction_agreement"]["identical"],
        )
        # Cross-component requests are the one denial this retrospective set supports.
        component = self.evaluation["result"]["rules"]["weak_component"]
        self.assertEqual(
            (component["tp"], component["tn"], component["fn"]), (27, 51, 0)
        )

    def test_fitted_errors_are_all_pittsburgh(self):
        errors = [
            item
            for item in self.evaluation["result"]["counterexamples"]
            if item["rule"] == model.FITTED_RULE
        ]
        self.assertEqual(len(errors), 5)
        self.assertEqual({item["opening"] for item in errors}, {"pittsburgh"})
        for item in errors:
            self.assertIn(item["kind"], ("false_positive", "false_negative"))
            self.assertEqual(len(item["observation_sha256"]), 64)
            self.assertEqual(len(item["query_freeze_sha256"]), 64)

    def test_binding_counts(self):
        self.assertEqual(
            self.evaluation["bindings"],
            {"opening_bindings": 11, "query_bindings": 276, "rows_checked": 568},
        )


class EvaluatingTest(unittest.TestCase):
    def row(
        self, success, complete=True, released=True, positions=None, endpoints=None
    ):
        endpoints = endpoints or {"from": [1, 0, 0], "to": [2, 0, 0]}
        return {
            "request": {"from": endpoints["from"], "to": endpoints["to"]},
            "result": {
                "success": success,
                "complete": complete,
                "released": released,
                "positions": [[1, 0, 0], [2, 0, 0]] if positions is None else positions,
                "flags": 4 if success else 8,
                "length": 100.0 if success else 100000.0,
            },
        }

    def test_exact_success_requires_exact_endpoints(self):
        row = self.row(True)
        self.assertEqual(evaluate.classify(row)[0], evaluate.EXACT)
        mismatched = self.row(True, positions=[[1, 0, 0], [3, 0, 0]])
        self.assertEqual(evaluate.classify(mismatched)[0], evaluate.UNKNOWN)
        self.assertEqual(evaluate.classify(None)[0], evaluate.UNKNOWN)
        self.assertEqual(
            evaluate.classify(self.row(True, complete=False))[0], evaluate.UNKNOWN
        )
        self.assertEqual(
            evaluate.classify(self.row(True, released=False))[0], evaluate.UNKNOWN
        )
        self.assertEqual(evaluate.classify(self.row(False))[0], evaluate.FAILURE)

    def test_confusion_arithmetic_and_null_denominators(self):
        confusion = evaluate.empty_confusion()
        evaluate.add(confusion, "success", evaluate.EXACT)
        evaluate.add(confusion, "success", evaluate.FAILURE)
        evaluate.add(confusion, "no_path", evaluate.FAILURE)
        self.assertEqual(
            (confusion["tp"], confusion["fp"], confusion["tn"], confusion["fn"]),
            (1, 1, 1, 0),
        )
        ratios = evaluate.ratios(confusion)
        self.assertAlmostEqual(ratios["precision"], 0.5)
        self.assertAlmostEqual(ratios["recall"], 1.0)
        empty = evaluate.empty_confusion()
        self.assertIsNone(evaluate.ratios(empty)["precision"])
        self.assertIsNone(evaluate.ratios(empty)["recall"])
        only_failure = evaluate.empty_confusion()
        evaluate.add(only_failure, "no_path", evaluate.FAILURE)
        self.assertIsNone(evaluate.ratios(only_failure)["precision"])
        self.assertIsNone(evaluate.ratios(only_failure)["recall"])

    def test_abstention_is_not_a_negative(self):
        confusion = evaluate.empty_confusion()
        evaluate.add(confusion, "abstain", evaluate.FAILURE)
        evaluate.add(confusion, "abstain", evaluate.EXACT)
        self.assertEqual(evaluate.scored(confusion), 0)
        self.assertEqual(confusion["abstain"], 2)


class FreezeTest(unittest.TestCase):
    def test_reviewed_v1_artifacts_are_preserved_byte_for_byte(self):
        for name, expected in predict.REVIEWED_ARTIFACTS.items():
            self.assertEqual(
                hashlib.sha256((HERE / name).read_bytes()).hexdigest(), expected, name
            )

    def test_corrected_predictions_match_their_protocol_and_sources(self):
        predictions = json.loads((HERE / "corrected" / "predictions.json").read_text())
        self.assertEqual(predictions["freeze"], predict.CORRECTED_FREEZE)
        self.assertEqual(predictions["model_version"], model.MODEL_VERSION)
        protocol = (HERE / "corrected" / "protocol.json").read_bytes()
        self.assertEqual(
            predictions["protocol_sha256"], hashlib.sha256(protocol).hexdigest()
        )
        self.assertEqual(
            predictions["supersedes"]["head"],
            "97e00389f4ad0eb30aa1ff1d775876c87f4ab27c",
        )
        for name, expected in predictions["sources"].items():
            self.assertEqual(
                hashlib.sha256((HERE.parents[2] / name).read_bytes()).hexdigest(),
                expected,
                name,
            )
        self.assertEqual(len(predictions["queries"]), 276)
        for rule in (predictions["primary_rule"], predictions["fitted_rule"]):
            self.assertIn(rule, predictions["rules"])
        for query in predictions["queries"]:
            self.assertEqual(set(query["predictions"]), set(predictions["rules"]))

    def test_corrected_evaluation_matches_its_predictions(self):
        evaluation = json.loads((HERE / "corrected" / "evaluation.json").read_text())
        self.assertEqual(
            evaluation["predictions_sha256"],
            hashlib.sha256(
                (HERE / "corrected" / "predictions.json").read_bytes()
            ).hexdigest(),
        )
        self.assertEqual(
            evaluation["result"]["labels"],
            {"exact_path_success": 27, "selected_query_failure": 249},
        )
        self.assertEqual(
            evaluation["result"]["exact_same_edge"]
            + evaluation["result"]["exact_distinct_edge"],
            27,
        )

    def test_selected_requests_are_the_primary_set(self):
        plan = {
            "plan": {
                "requests": [
                    {"diagnostic": False, "position_kind": "boundary"},
                    {"diagnostic": True, "position_kind": "boundary"},
                    {"diagnostic": True, "position_kind": "midpoint"},
                ]
            }
        }
        self.assertEqual([index for index, _ in predict.selected_requests(plan)], [0])


class DomainContractTest(unittest.TestCase):
    """Constructed cases that fail on the reviewed head and pass the correction."""

    def test_car_only_middle_segment_blocks_a_train_path(self):
        pkg = package(
            [
                segment(10, 1, 2, (0.0, 0.0, 0.0), (100.0, 0.0, 0.0)),
                segment(11, 2, 3, (100.0, 0.0, 0.0), (200.0, 0.0, 0.0)),
                segment(12, 3, 4, (200.0, 0.0, 0.0), (300.0, 0.0, 0.0)),
            ]
        )
        for lane in pkg["segments"][11]["lanes"]:
            lane["vehicle"] = ["Car"]
        pkg["segments"][11]["prefab"] = "Car-only road"
        self.assertEqual(
            model.predict(pkg, request(10, 1, 0, 12, 1, 255), model.FITTED_RULE)[
                "prediction"
            ],
            model.NO_PATH,
        )
        # A Car lane is not a Train lane of the request either.
        self.assertEqual(
            model.predict(pkg, request(11, 0, 0, 12, 1, 255), model.FITTED_RULE)[
                "prediction"
            ],
            model.ABSTAIN,
        )

    def test_invert_swaps_the_required_travel_bit(self):
        pkg = chain()
        for item in pkg["segments"].values():
            item["flags"].add("Invert")
        self.assertTrue(
            model.effective_forward(pkg["segments"][10], pkg["segments"][10]["start"])
            is False
        )
        self.assertEqual(
            model.predict(pkg, request(10, 1, 0, 11, 1, 255), model.FITTED_RULE)[
                "prediction"
            ],
            model.NO_PATH,
        )
        self.assertEqual(
            model.predict(pkg, request(10, 0, 0, 11, 0, 255), model.FITTED_RULE)[
                "prediction"
            ],
            model.SUCCESS,
        )

    def test_equal_angle_junction_does_not_depend_on_ids(self):
        pkg = package(
            [
                segment(10, 1, 2, (-1.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
                segment(11, 2, 3, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
                segment(12, 2, 4, (0.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
            ]
        )
        query = request(10, 1, 0, 11, 1, 255)
        renamed, _, _ = rename(
            pkg, {10: 10, 11: 30, 12: 11}, {key: key for key in pkg["nodes"]}
        )
        renamed_query = request(10, 1, 0, 30, 1, 255)
        original = model.predict(pkg, query, model.FITTED_RULE)
        renamed_result = model.predict(renamed, renamed_query, model.FITTED_RULE)
        self.assertEqual(original, renamed_result)
        # The resolution is genuinely symmetric, so the honest answer is to abstain.
        self.assertEqual(original["prediction"], model.ABSTAIN)
        self.assertEqual(original["detail"]["reason"], "ambiguous_junction_pairing")

    def test_reversal_hypothesis_is_expressible(self):
        pkg = package([segment(10, 1, 2, (0.0, 0.0, 0.0), (100.0, 0.0, 0.0))])
        out_and_back = request(10, 1, 0, 10, 0, 0)
        outcomes = {
            uturn: model.predict(pkg, out_and_back, f"lane:any_lane:{uturn}")[
                "prediction"
            ]
            for uturn in model.UTURNS
        }
        self.assertEqual(outcomes["forbidden"], model.NO_PATH)
        self.assertEqual(outcomes["deadend"], model.SUCCESS)
        self.assertEqual(outcomes["allowed"], model.SUCCESS)

    def test_length_bound_rejects_an_oversized_path(self):
        pkg = package([segment(10, 1, 2, (0.0, 0.0, 0.0), (100001.0, 0.0, 0.0))])
        result = model.predict(pkg, request(10, 1, 0, 10, 1, 255), model.FITTED_RULE)
        self.assertEqual(result["prediction"], model.NO_PATH)
        self.assertEqual(
            result["detail"]["reason"], "path_lower_bound_exceeds_max_length"
        )
        # The same segment just inside the bound is reachable.
        short = package([segment(10, 1, 2, (0.0, 0.0, 0.0), (99999.0, 0.0, 0.0))])
        self.assertEqual(
            model.predict(short, request(10, 1, 0, 10, 1, 255), model.FITTED_RULE)[
                "prediction"
            ],
            model.SUCCESS,
        )

    def test_length_bound_relaxes_to_a_shorter_alternative(self):
        # The long parallel branch reaches the transfer state first by insertion
        # order with a distance over the bound; only a relaxed search finds the
        # short branch under it.
        pkg = package(
            [
                segment(10, 1, 2, (0.0, 0.0, 0.0), (10.0, 0.0, 0.0)),
                segment(20, 2, 3, (10.0, 0.0, 0.0), (99010.0, 0.0, 0.0)),
                segment(21, 2, 3, (10.0, 0.0, 0.0), (1010.0, 0.0, 0.0)),
                segment(30, 3, 4, (1010.0, 0.0, 0.0), (51010.0, 0.0, 0.0)),
            ]
        )
        result = model.predict(
            pkg, request(10, 1, 0, 30, 1, 255), "lane:any_lane:forbidden"
        )
        self.assertEqual(result["prediction"], model.SUCCESS)
        self.assertLessEqual(
            result["detail"]["path_lower_bound_length"], model.MAX_LENGTH
        )
        shuffled = copy.deepcopy(pkg)
        shuffled["segments"] = dict(reversed(list(pkg["segments"].items())))
        self.assertEqual(
            model.predict(
                shuffled, request(10, 1, 0, 30, 1, 255), "lane:any_lane:forbidden"
            ),
            result,
        )


class BindingContractTest(unittest.TestCase):
    """A prediction is only scored against the exact record it is bound to."""

    @classmethod
    def setUpClass(cls):
        cls.openings = json.loads((HERE / "openings.json").read_text())
        cls.predictions = json.loads(
            (HERE / "corrected" / "predictions.json").read_text()
        )
        cls.observations = evaluate.collect(cls.openings)

    def test_mutated_request_fails_binding(self):
        altered = copy.deepcopy(self.predictions)
        altered["queries"][0]["request"]["from"][0] = -123456789
        with self.assertRaises(evaluate.BindingError):
            evaluate.bind(altered, self.observations, self.openings)

    def test_mutated_row_request_fails_binding(self):
        altered = copy.deepcopy(self.observations)
        opening = altered["asheville"]
        opening["rows"][0]["request"] = {"from": [1, 0, 0], "to": [2, 0, 0]}
        with self.assertRaises(evaluate.BindingError):
            evaluate.bind(self.predictions, altered, self.openings)

    def test_changed_source_fails_binding(self):
        altered = copy.deepcopy(self.predictions)
        name = next(iter(altered["sources"]))
        altered["sources"][name] = "0" * 64
        with self.assertRaises(evaluate.BindingError):
            evaluate.bind(altered, self.observations, self.openings)

    def test_missing_success_fails_closed(self):
        row = {
            "request": {"from": [1, 0, 0], "to": [2, 0, 0]},
            "result": {"complete": True, "released": True, "positions": []},
        }
        with self.assertRaises(evaluate.BindingError):
            evaluate.classify(row)

    def test_missing_row_is_unknown_not_a_failure(self):
        self.assertEqual(evaluate.classify(None)[0], evaluate.UNKNOWN)

    def test_real_binding_covers_every_query(self):
        self.assertEqual(
            evaluate.bind(self.predictions, self.observations, self.openings),
            {"opening_bindings": 11, "query_bindings": 276, "rows_checked": 568},
        )


class BridgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.openings = json.loads((HERE / "openings.json").read_text())
        cls.packages = json.loads((HERE / "packages.json").read_text())["packages"]

    def test_catalog_is_stable_across_packages(self):
        entries = [
            entry
            for entry in self.openings["openings"]
            if entry["package"] in self.openings["bridge"]["packages"]
        ]
        catalogs = bridge.catalogs_for(entries, {"packages": self.packages})
        for prefab, templates in catalogs["prefab_lanes"].items():
            self.assertEqual(len(templates), 1, prefab)

    def test_one_package_derives_every_model_field_from_export_bytes(self):
        entries = [
            entry
            for entry in self.openings["openings"]
            if entry["package"] in self.openings["bridge"]["packages"]
        ]
        held_out = entries[0]
        held = bridge.catalogs_for(entries, {"packages": self.packages})
        _, net = bridge.crp_networks(self.packages[held_out["package"]]["locator"])
        built = bridge.bridge_package(net, held)
        self.assertEqual(built["missing"], [])
        raw_dir = bridge.CAPABILITY / held_out["raw"]
        native = topology.from_native(
            bridge.load_json(raw_dir / "networks.json.gz"), held_out["opening"]
        )
        counts, failures = bridge.compare(built, native, train_only=True)
        self.assertEqual(failures, {})
        for field in bridge.MODEL_FIELDS:
            self.assertEqual(
                counts[field + ":agree"], counts[field + ":checked"], field
            )
        requests = bridge.selected_requests(
            bridge.load_json(raw_dir / "query-freeze.json.gz")
        )
        for req in requests:
            self.assertEqual(
                model.predict(native, req, model.FITTED_RULE),
                model.predict(built, req, model.FITTED_RULE),
            )

    def test_bridge_never_writes_to_a_package(self):
        package = self.packages["yosemite"]
        before = hashlib.sha256(Path(package["locator"]).read_bytes()).hexdigest()
        bridge.crp_networks(package["locator"])
        after = hashlib.sha256(Path(package["locator"]).read_bytes()).hexdigest()
        self.assertEqual(before, package["sha256"])
        self.assertEqual(after, package["sha256"])


if __name__ == "__main__":
    unittest.main()
