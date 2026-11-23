"""Corrected-head adaptations of the five rejected-d39 acceptance regressions."""

import copy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from evidence import ArtifactStore
import readiness
import schema
from test_support import constructed, put_json


class Acceptance(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.store = ArtifactStore(Path(temporary.name))
        self.frozen, self.observed, self.policy = constructed(self.store)
        baseline = self.result(self.frozen, self.observed, self.policy)
        self.assertTrue(baseline.ready_for_measurement, baseline.reasons)
        self.assertEqual(baseline.pre_export_qualification, "unknown")

    def result(self, f, o, p):
        return readiness.check([f], {"CONSTRUCTED": o}, p, set(), self.store)

    def reject(self, f, o, p, reason=None):
        result = self.result(f, o, p)
        self.assertFalse(result.ready_for_measurement)
        self.assertEqual(result.pre_export_qualification, "unknown")
        self.assertTrue(result.reasons)
        if reason is not None:
            self.assertTrue(
                any(reason in value for value in result.reasons), result.reasons
            )

    def fresh(self):
        return copy.deepcopy((self.frozen, self.observed, self.policy))

    def test_parent_five_regressions(self):
        for fact in (
            "artifact_sha256",
            "protocol_sha256",
            "dll_sha256",
            "mods_inventory_root",
            "consumed_field_hashes",
        ):
            with self.subTest(fact=fact):
                f, o, p = self.fresh()
                if fact == "artifact_sha256":
                    f[fact] = o[fact] = None
                elif fact == "protocol_sha256":
                    f[fact] = o[fact] = p[fact] = None
                    for phase in o["runtime"].values():
                        phase[fact] = None
                elif fact == "dll_sha256":
                    p[fact] = None
                    for phase in o["runtime"].values():
                        phase[fact] = None
                elif fact == "mods_inventory_root":
                    del p["roots"]["user_mods"]
                    for phase in o["runtime"].values():
                        del phase["roots"]["user_mods"]
                else:
                    f["consumed_fields"] = {
                        key: None for key in readiness.CONSUMED_COVERAGE
                    }
                    o["consumed_fields"] = copy.deepcopy(f["consumed_fields"])
                self.reject(f, o, p)

    def test_missing_observed_artifact_with_null_frozen_is_not_equal_evidence(self):
        f, o, p = self.fresh()
        f["artifact_sha256"] = None
        del o["artifact_sha256"]
        self.reject(f, o, p, "observed control")

    def test_shared_nulls_omissions_and_bad_hash_types(self):
        for key in schema.HASHES:
            for value in (
                None,
                "",
                True,
                1,
                [],
                {},
                "a" * 63,
                "A" * 64,
                "g" * 64,
                " a" * 32,
            ):
                with self.subTest(key=key, value=value):
                    f, o, p = self.fresh()
                    f[key] = o[key] = value
                    self.reject(f, o, p, "SHA-256")
            f, o, p = self.fresh()
            del f[key]
            del o[key]
            self.reject(f, o, p, "frozen control")
        for value in (None, "", False, "not-a-hash"):
            f, o, p = self.fresh()
            f["exact_graph_sha256"] = o["opening_graph"] = o["post_graph"] = value
            self.reject(f, o, p)

    def test_every_schema_field_is_required_on_both_sides(self):
        for subject, keys in (
            ("frozen", schema.FROZEN),
            ("observed", schema.OBSERVED),
            ("policy", schema.POLICY),
            ("phase", schema.PHASE),
        ):
            for key in keys:
                f, o, p = self.fresh()
                target = {
                    "frozen": f,
                    "observed": o,
                    "policy": p,
                    "phase": o["runtime"]["pre"],
                }[subject]
                del target[key]
                with self.subTest(subject=subject, key=key):
                    self.reject(f, o, p)

    def test_missing_root_roles_and_unknown_roots_in_both_maps(self):
        for key in schema.ROOTS | {"plugin:Cs1Harness"}:
            f, o, p = self.fresh()
            del p["roots"][key]
            for phase in o["runtime"].values():
                del phase["roots"][key]
            with self.subTest(root=key):
                self.reject(f, o, p, "roots")
        f, o, p = self.fresh()
        p["roots"]["unknown"] = copy.deepcopy(p["roots"]["managed"])
        for phase in o["runtime"].values():
            phase["roots"]["unknown"] = copy.deepcopy(p["roots"]["unknown"])
        self.reject(f, o, p, "roots")

    def test_root_labels_cannot_hide_wrong_runtime_paths(self):
        for role in schema.ROOTS:
            f, o, p = self.fresh()
            p["roots"][role] = copy.deepcopy(p["roots"]["plugin:Cs1Harness"])
            for phase in o["runtime"].values():
                phase["roots"][role] = copy.deepcopy(p["roots"][role])
            self.reject(f, o, p, "root")

    def test_shared_inventory_omissions_and_malformed_values(self):
        for key in ("files", "roots", "plugins", "assemblies"):
            for value in (None, [], {}, {"unknown": None}):
                f, o, p = self.fresh()
                p[key] = copy.deepcopy(value)
                for phase in o["runtime"].values():
                    phase[key] = copy.deepcopy(value)
                with self.subTest(key=key, value=value):
                    self.reject(f, o, p)
        f, o, p = self.fresh()
        del p["files"][p["dll_path"]]
        for phase in o["runtime"].values():
            del phase["files"][phase["dll_path"]]
        self.reject(f, o, p, "dll_path")
        f, o, p = self.fresh()
        p["dll_sha256"] = p["files"][p["executable_path"]]
        for phase in o["runtime"].values():
            phase["dll_sha256"] = p["dll_sha256"]
        self.reject(f, o, p, "DLL hash")
        for key, value in (("sha256", None), ("mvid", ""), ("path", "/absent.dll")):
            f, o, p = self.fresh()
            p["assemblies"]["Cs1Harness"][key] = value
            for phase in o["runtime"].values():
                phase["assemblies"]["Cs1Harness"][key] = value
            self.reject(f, o, p)

    def test_unknown_extra_facts_fail_instead_of_being_ignored(self):
        for subject in (
            "frozen",
            "observed",
            "policy",
            "phase",
            "query",
            "plugin",
            "assembly",
            "root",
            "process",
        ):
            f, o, p = self.fresh()
            target = {
                "frozen": f,
                "observed": o,
                "policy": p,
                "phase": o["runtime"]["pre"],
                "query": o["paths"][0],
                "plugin": p["plugins"]["Cs1Harness"],
                "assembly": p["assemblies"]["Cs1Harness"],
                "root": p["roots"]["managed"],
                "process": o["cleanup"]["game"],
            }[subject]
            target["unknown_extra"] = True
            with self.subTest(subject=subject):
                self.reject(f, o, p, "expected exactly")

    def test_consumed_evidence_cannot_just_point_to_unrelated_bytes(self):
        for value in (None, "", False, {}, [], "a" * 64):
            f, o, p = self.fresh()
            f["consumed_fields"] = o["consumed_fields"] = {
                k: value for k in schema.CONSUMED_COVERAGE
            }
            self.reject(f, o, p)
        f, o, p = self.fresh()
        key = "segment_ids"
        record = self.store.json(f["consumed_fields"][key], "fixture")
        record["values"] = {"road": [9999]}
        f["consumed_fields"][key] = o["consumed_fields"][key] = put_json(
            self.store, record
        )
        self.reject(f, o, p, "values differ")

    def test_actual_bytes_are_required_and_rehashed(self):
        f, o, p = self.fresh()
        absent = "f" * 64
        f["artifact_sha256"] = o["artifact_sha256"] = absent
        self.reject(f, o, p, "missing retained artifact")
        f, o, p = self.fresh()
        (self.store.root / f["artifact_sha256"]).write_bytes(b"corrupt bytes")
        self.reject(f, o, p, "corrupt retained artifact")

    def test_source_request_prediction_are_bound_to_retained_content(self):
        for key, value in [
            ("source_files", {"new.py": "f" * 64}),
            ("requests", self.frozen["requests"][:-1]),
            ("predictions", {k: "no_path" for k in self.frozen["predictions"]}),
        ]:
            f, o, p = self.fresh()
            f[key] = value
            with self.subTest(key=key):
                self.reject(f, o, p)

    def test_malformed_boundary_arguments_return_reasons_not_crashes(self):
        for controls in (
            None,
            {},
            True,
            [None],
            [{"case_id": None}],
            [self.frozen, self.frozen],
        ):
            result = readiness.check(controls, {}, self.policy, set(), self.store)
            self.assertFalse(result.ready_for_measurement)
            self.assertTrue(result.reasons)
        for observations in (None, [], False):
            result = readiness.check(
                [self.frozen], observations, self.policy, set(), self.store
            )
            self.assertFalse(result.ready_for_measurement)
        result = readiness.check(
            [self.frozen], {"CONSTRUCTED": self.observed}, self.policy, set()
        )
        self.assertFalse(result.ready_for_measurement)
        self.assertIn("declarations are not evidence", result.reasons[0])


if __name__ == "__main__":
    unittest.main()
