"""CONSTRUCTED readiness inputs; never a native qualification example."""

import copy
import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory
from pathlib import Path

from evidence import ArtifactStore
from test_support import constructed

import bridge_contract as b
import fixtures
import readiness as r


class Readiness(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.store = ArtifactStore(Path(temporary.name))

    def check(self, f, o, p):
        return r.check([f], {f["case_id"]: o}, p, set(), self.store)

    def test_constructed_ready_is_not_qualified(self):
        result = self.check(*constructed(self.store))
        self.assertTrue(result.ready_for_measurement, result.reasons)
        self.assertEqual(result.pre_export_qualification, "unknown")

    def test_missing_control_inventory_source_and_process_facts(self):
        f, original, policy = constructed(self.store)
        for key in original:
            bad = copy.deepcopy(original)
            del bad[key]
            # These are only the new checker's consumed opening inputs.
            if key not in {
                "completed",
                "session_id",
                "native_context",
                "artifact_sha256",
                "source_sha256",
                "request_sha256",
                "prediction_sha256",
                "protocol_sha256",
                "consumed_fields",
                "opening_graph",
                "post_graph",
                "runtime",
                "owned_processes",
                "cleanup",
                "paths",
            }:
                continue
            with self.subTest(key=key):
                self.assertFalse(self.check(f, bad, policy).ready_for_measurement)
        for phase in original["runtime"]:
            for key in original["runtime"][phase]:
                bad = copy.deepcopy(original)
                del bad["runtime"][phase][key]
                with self.subTest(phase=phase, key=key):
                    self.assertFalse(self.check(f, bad, policy).ready_for_measurement)
            for key in ("files", "roots", "plugins", "assemblies"):
                bad = copy.deepcopy(original)
                bad["runtime"][phase][key] = {}
                self.assertFalse(self.check(f, bad, policy).ready_for_measurement)
        for role in policy["process_roles"]:
            bad = copy.deepcopy(original)
            del bad["cleanup"][role]
            self.assertFalse(self.check(f, bad, policy).ready_for_measurement)
        bad = copy.deepcopy(original)
        bad["cleanup"]["game"]["gone"] = 1
        self.assertFalse(self.check(f, bad, policy).ready_for_measurement)
        self.assertFalse(r.check([f], {}, policy, set()).ready_for_measurement)
        self.assertFalse(r.check([], {}, policy, set()).ready_for_measurement)
        self.assertFalse(
            r.check(
                [f], {f["case_id"]: original}, policy, {"CONSTRUCTED"}, self.store
            ).ready_for_measurement
        )

    def test_no_replacement_drift_or_incomplete_control(self):
        f, o, policy = constructed(self.store)
        mutations = [
            lambda v: v.update(completed=1),
            lambda v: v.update(completed=False),
            lambda v: v.update(error="first guard failed"),
            lambda v: v["paths"].pop(),
            lambda v: v["paths"].append(copy.deepcopy(v["paths"][0])),
            lambda v: v["paths"][0].update(pre_graph="drift"),
            lambda v: v["paths"][0].update(post_graph="drift"),
            lambda v: v["paths"][0]["plan"].update(query_id="replacement"),
            lambda v: v["paths"][0]["result"].update(complete=False),
            lambda v: v["paths"][0]["result"].update(success=False),
            lambda v: v["paths"][0].pop("pre_build_index"),
            lambda v: v["paths"][0]["pre_context"].update(frame=0),
            lambda v: v["runtime"]["pre"].update(pid=101),
        ]
        for mutate in mutations:
            bad = copy.deepcopy(o)
            mutate(bad)
            self.assertFalse(self.check(f, bad, policy).ready_for_measurement)

    def test_completion_mutant_is_killed(self):
        f, o, policy = constructed(self.store)
        o["completed"] = 1
        self.assertFalse(self.check(f, o, policy).ready_for_measurement)
        # Original generic truthiness accepts numeric lookalike completion.
        with patch("readiness.strict_bool", bool), patch("schema.strict_bool", bool):
            self.assertTrue(self.check(f, o, policy).ready_for_measurement)


class Dependency(unittest.TestCase):
    def package(self):
        lane = {
            "index": 0,
            "lane_type": "Vehicle",
            "vehicle": ["Car"],
            "category": "PassengerCar",
            "forward": True,
            "backward": True,
        }
        return {
            "segments": {
                1: {
                    "id": 1,
                    "start": 1,
                    "end": 2,
                    "a": (0, 0, 0),
                    "b": (10, 0, 0),
                    "flags": set(),
                    "prefab": "A",
                    "lanes": [lane],
                }
            }
        }

    def test_prefab_only_equality_is_not_raw_identity(self):
        a = self.package()
        z = copy.deepcopy(a)
        z["segments"][1]["prefab"] = "B"
        result = b.compare(a, z)
        self.assertFalse(result["normalized_object_identity"])
        self.assertTrue(result["model_consumed_equality"])
        self.assertEqual(result["native_qualification"], "unknown")
        z["segments"][1]["lanes"][0]["forward"] = False
        self.assertFalse(b.compare(a, z)["model_consumed_equality"])

    def test_raw_identity_never_normalizes(self):
        self.assertTrue(b.exact_raw_identity(b'{"a":1}', b'{"a":1}'))
        self.assertFalse(b.exact_raw_identity(b'{"a":1}', b'{ "a":1}'))
        with self.assertRaises(ValueError):
            b.exact_raw_identity({"a": 1}, {"a": 1})

    def test_all_consumed_fields_required(self):
        original = self.package()
        for key in b.SEGMENT_FIELDS:
            bad = copy.deepcopy(original)
            del bad["segments"][1][key]
            self.assertIsNone(b.compare(original, bad)["model_consumed_equality"])
        for key in b.LANE_FIELDS:
            bad = copy.deepcopy(original)
            del bad["segments"][1]["lanes"][0][key]
            self.assertIsNone(b.compare(original, bad)["model_consumed_equality"])

    def test_height_can_change_pinned_predicate(self):
        # Synthetic only; execute unchanged accepted model, not historical labels.
        import sys

        sys.path.insert(0, str(fixtures.HERE.parent / "outside-query-model-v1"))
        import model

        a = self.package()
        a["segments"][2] = dict(
            copy.deepcopy(a["segments"][1]),
            id=2,
            start=2,
            end=3,
            a=(10, 0, 0),
            b=(20, 0, 0),
        )
        request = {"from": [1, 0, 0], "to": [2, 0, 255]}

        def predict(package):
            return model.predict(
                model.Prepared(package, "road"), request, "lane:any_lane:forbidden"
            )["prediction"]

        self.assertEqual(predict(a), "success")
        renamed = copy.deepcopy(a)
        renamed["segments"][1]["prefab"] = "anything"
        self.assertEqual(predict(renamed), "success")
        high = copy.deepcopy(a)
        high["segments"][1]["b"] = (10, 200000, 0)
        self.assertEqual(predict(high), "no_path")
        self.assertFalse(b.compare(a, high)["model_consumed_equality"])
        for key, value in [("flags", {"Invert"}), ("start", 9), ("a", (0, 200000, 0))]:
            bad = copy.deepcopy(a)
            bad["segments"][1][key] = value
            self.assertFalse(b.compare(a, bad)["model_consumed_equality"])


if __name__ == "__main__":
    unittest.main()
