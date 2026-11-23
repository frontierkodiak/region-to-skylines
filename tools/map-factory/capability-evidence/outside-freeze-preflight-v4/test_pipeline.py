"""Real builder/consumer, source-role mutations and owned-process regressions.

PL1315_EVIDENCE names a private seed holding; tests copy it before writing.
No retained observation is scored, no game or shared service is contacted.
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import spec
from spec import ArtifactStore, ProtocolError
import lifecycle
import pipeline
import schema_v3
import verify
import consumer
from unittest import mock


class RealPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed = os.environ.get("PL1315_EVIDENCE")
        if not seed:
            raise RuntimeError(
                "PL1315_EVIDENCE required: private bytes cannot be empty proof"
            )
        cls.temp = tempfile.TemporaryDirectory(prefix="pl1315-", dir=Path(seed).parent)
        cls.addClassCleanup(cls.temp.cleanup)
        cls.work = Path(cls.temp.name)
        shutil.copytree(seed, cls.work / "evidence")
        cls.store = ArtifactStore(cls.work / "evidence")
        cls.valid = spec.build(cls.store)
        cls.freeze = cls.valid.value
        cls.receipt = lifecycle.fixture_receipt()
        cls.records, cls.policy = pipeline.constructed(
            cls.valid, cls.store, cls.receipt
        )
        cls.b = pipeline.bundle(cls.valid, cls.records, cls.policy, cls.store)
        cls.source_root = cls.work / "tree"
        for name in spec.provenance_keys():
            target = cls.source_root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((spec.ROOT / name).read_bytes())

    def rejects(self, value):
        with self.assertRaises(
            (ProtocolError, ValueError, KeyError, TypeError, OSError)
        ):
            spec.validate(value, self.store)

    def gate_rejects(self, value):
        with self.assertRaises(
            (ProtocolError, ValueError, KeyError, TypeError, OSError)
        ):
            pipeline.gate(value, self.freeze, self.store)

    def test_real_builder_same_consumer_and_no_admission(self):
        result = spec.ready(self.freeze, self.store)
        self.assertTrue(result["offline_compatible"])
        self.assertFalse(result["launch_authorized"])
        self.assertEqual(result["control_admission"], "unknown")
        out = pipeline.gate(self.b, self.freeze, self.store)
        self.assertTrue(out["structural_consumer_pass"])
        self.assertFalse(out["real_certificate"])
        self.assertEqual(out["control_admission"], "unknown")
        self.assertEqual(out["native_observations"], 0)
        self.assertNotEqual(
            self.valid.bindings()["source_sha256"],
            self.valid.bindings()["measurement_provenance_sha256"],
        )

    def test_preflight_consumer_is_before_and_distinct_from_driver_cleanup(self):
        with lifecycle.finite_fixture() as (children, births):
            self.assertTrue(spec.ready(self.freeze, self.store)["offline_compatible"])
            self.assertEqual(
                lifecycle.identity(children["driver"].pid), births["driver"]
            )
            with self.assertRaisesRegex(ValueError, "post-exit"):
                lifecycle.finalize(children, births)
            with mock.patch.object(
                consumer,
                "validate_frozen",
                side_effect=ProtocolError("consumer input refusal"),
            ):
                with self.assertRaisesRegex(ProtocolError, "consumer input refusal"):
                    spec.ready(self.freeze, self.store)
        self.assertEqual(
            lifecycle.finalize(children, births)["stage"], "AfterDriverExit"
        )

    def test_actual_old_freeze_fails_before_missing_build_or_store(self):
        old = spec.read(spec.OLD / "freeze.json")
        self.assertEqual(spec.source_map(old["source_files"]), old["source_files"])
        self.assertEqual(spec.digest(old["source_files"]), old["source_sha256"])
        self.assertEqual(
            set(schema_v3.SOURCE_KEYS_V3) - set(old["source_files"]), set()
        )
        self.assertFalse(
            (spec.ROOT / "tools/cs1-harness/.build/Cs1Harness.dll").exists()
        )
        with self.assertRaisesRegex(ProtocolError, "legacy freeze consumer closure"):
            spec.validate(old, ArtifactStore(self.work / "ABSENT"))
        import stock_v2

        # The old self-map check reaches its irrelevant local build locator;
        # our new pre-control boundary rejects the actual 82/30 mismatch first.
        with self.assertRaises(FileNotFoundError):
            stock_v2.preflight()

    def test_actual_wiring_not_only_relabelled_dictionary(self):
        c = self.freeze["controls"][0]
        o = self.records[0]["observed"]
        with self.assertRaisesRegex(ProtocolError, "required source closure"):
            schema_v3.validate_opening(c, o, self.policy, self.store)
        # The new schema extends the exact closure before freeze creation.
        self.assertTrue(
            pipeline.gate(self.b, self.freeze, self.store)["structural_consumer_pass"]
        )

    def test_strict_top_level_shapes(self):
        for key in self.freeze:
            for replacement in (None, [], "wrong", True):
                with self.subTest(key=key, replacement=replacement):
                    value = copy.deepcopy(self.freeze)
                    value[key] = replacement
                    self.rejects(value)
            value = copy.deepcopy(self.freeze)
            del value[key]
            self.rejects(value)
        self.rejects(dict(self.freeze, extra=True))
        value = copy.deepcopy(self.freeze)
        value["stop_policy"]["no_retry"] = 1
        self.rejects(value)

    def test_role_keysets_and_digests(self):
        for name in self.freeze["sources"]:
            for operation in (
                "missing",
                "extra",
                "null",
                "type",
                "digest",
                "superset_digest",
            ):
                with self.subTest(role=name, operation=operation):
                    value = copy.deepcopy(self.freeze)
                    row = value["sources"][name]
                    if operation == "missing":
                        row["files"].pop(next(iter(row["files"])))
                    elif operation == "extra":
                        row["files"]["extra.py"] = "0" * 64
                    elif operation == "null":
                        row["files"] = None
                    elif operation == "type":
                        row["files"] = []
                    elif operation == "digest":
                        row["sha256"] = "0" * 64
                    else:
                        row["sha256"] = value["sources"]["measurement_build"]["sha256"]
                        if name == "measurement_build":
                            row["sha256"] = value["sources"]["readiness_helpers"][
                                "sha256"
                            ]
                    self.rejects(value)
        value = copy.deepcopy(self.freeze)
        value["sources"]["readiness_helpers"] = value["sources"]["measurement_build"]
        self.rejects(value)

    def test_each_source_hash_and_actual_source_content(self):
        for role, row in self.freeze["sources"].items():
            for name in row["files"]:
                with self.subTest(role=role, source=name):
                    value = copy.deepcopy(self.freeze)
                    value["sources"][role]["files"][name] = "0" * 64
                    value["sources"][role]["sha256"] = spec.digest(
                        value["sources"][role]["files"]
                    )
                    self.rejects(value)
        for name in spec.provenance_keys():
            with self.subTest(source_bytes=name):
                path = self.source_root / name
                original = path.read_bytes()
                path.write_bytes(original + b"\nTAMPER")
                try:
                    with self.assertRaises(ProtocolError):
                        spec.validate(self.freeze, self.store, self.source_root)
                finally:
                    path.write_bytes(original)

    def test_each_private_build_and_input_role(self):
        for role in ("build_artifacts", "inputs"):
            for key in self.freeze[role]:
                with self.subTest(role=role, key=key):
                    value = copy.deepcopy(self.freeze)
                    value[role][key] = "0" * 64
                    self.rejects(value)
            for operation in ("extra", "missing", "null"):
                value = copy.deepcopy(self.freeze)
                if operation == "extra":
                    value[role]["extra"] = "0" * 64
                elif operation == "missing":
                    value[role].pop(next(iter(value[role])))
                else:
                    value[role] = None
                self.rejects(value)

    def test_actual_retained_bytes_corruption_and_missing(self):
        hashes = set(self.freeze["inputs"].values()) | set(
            self.freeze["build_artifacts"].values()
        )
        hashes |= {
            key for r in self.freeze["sources"].values() for key in r["files"].values()
        }
        for key in hashes:
            with self.subTest(artifact=key):
                path = self.store.root / key
                original = path.read_bytes()
                path.write_bytes(b"TAMPER")
                try:
                    self.rejects(self.freeze)
                    path.unlink()
                    self.rejects(self.freeze)
                finally:
                    path.write_bytes(original)

    def test_collector_and_bundle_edges_each_binding(self):
        for key in self.valid.bindings():
            records = copy.deepcopy(self.records)
            records[0]["binding"][key] = "0" * 64
            with self.subTest(collector=key), self.assertRaises(ProtocolError):
                pipeline.bundle(self.valid, records, self.policy, self.store)
            value = copy.deepcopy(self.b)
            value["binding"][key] = "0" * 64
            self.gate_rejects(value)
        for field in ("binding", "kind", "observed"):
            records = copy.deepcopy(self.records)
            records[0][field] = None
            with self.assertRaises((ProtocolError, TypeError)):
                pipeline.bundle(self.valid, records, self.policy, self.store)
        records = copy.deepcopy(self.records)
        records[0]["kind"] = "REAL"
        with self.assertRaises(ProtocolError):
            pipeline.bundle(self.valid, records, self.policy, self.store)

    def test_policy_runtime_and_bundle_gate_edges(self):
        for key in ("source_sha256", "dll_sha256", "protocol_sha256"):
            value = copy.deepcopy(self.b)
            value["policy"][key] = "0" * 64
            self.gate_rejects(value)
            for phase in ("launch", "pre", "post"):
                value = copy.deepcopy(self.b)
                value["observations"]["stock-1"]["runtime"][phase][key] = "0" * 64
                self.gate_rejects(value)
        for field in self.freeze["controls"][0]:
            value = copy.deepcopy(self.b)
            value["controls"][0][field] = None
            self.gate_rejects(value)
        for field in self.records[0]["observed"]:
            value = copy.deepcopy(self.b)
            value["observations"]["stock-1"][field] = (
                "CONSTRUCTED error" if field == "error" else None
            )
            with self.subTest(observed=field):
                self.assertNotEqual(value, self.b)
                self.gate_rejects(value)
        value = copy.deepcopy(self.b)
        value["observations"]["stock-1"]["cleanup"]["driver"]["gone"] = "True"
        self.gate_rejects(value)

    def test_mvid_is_retained_byte_fact_not_a_uuid_claim(self):
        for name in self.policy["assemblies"]:
            value = copy.deepcopy(self.b)
            value["policy"]["assemblies"][name]["mvid"] = (
                "00000000-0000-0000-0000-000000000000"
            )
            with self.subTest(assembly=name):
                self.gate_rejects(value)

    def test_future_types_do_not_forge_admission(self):
        value = copy.deepcopy(self.b)
        value["kind"] = "REAL"
        self.gate_rejects(value)
        value = copy.deepcopy(self.b)
        value["observations"]["stock-1"]["session_id"] = self.freeze["prior_sessions"][
            -1
        ]
        self.gate_rejects(value)
        with self.assertRaises(ProtocolError):
            pipeline.runtime_policy(
                self.valid, self.policy
            )  # Pre-bound inventory refused.
        value = copy.deepcopy(self.b)
        value["policy"]["process_roles"].append("driver")
        self.gate_rejects(value)

    def test_duplicate_json_fields_fail_at_file_boundary(self):
        path = self.work / "duplicate.json"
        path.write_bytes(b'{"version":4,"version":4}')
        with self.assertRaisesRegex(ProtocolError, "duplicate field"):
            spec.read(path)

    def test_portable_build_modes_and_recipe(self):
        self.assertEqual(
            verify.local_build_context(None)["local_fresh_build"], "unverified"
        )
        self.assertEqual(
            verify.local_build_context(self.work / "absent")["local_fresh_build"],
            "unverified",
        )
        # Retained bytes pass despite no original absolute stage or local .build.
        self.assertTrue(spec.ready(self.freeze, self.store)["offline_compatible"])
        receipt = spec.read(spec.OLD / "freeze.json")["build"]
        self.assertEqual(
            {n: spec.hashed(v) for n, v in spec.staged_sources(receipt).items()},
            receipt["staged_sources"],
        )

    def test_original_tree_unchanged(self):
        diff = subprocess.check_output(
            [
                "git",
                "diff",
                spec.PIN,
                "--name-only",
                "--",
                ".",
                ":(exclude)" + spec.PREFIX,
            ],
            cwd=spec.ROOT,
            text=True,
        )
        self.assertEqual(diff, "")


class ProcessOwnership(unittest.TestCase):
    def test_live_driver_cannot_be_ready_cleanup(self):
        with lifecycle.finite_fixture() as (children, births):
            self.assertTrue(
                all(lifecycle.identity(c.pid) == births[r] for r, c in children.items())
            )
            with self.assertRaisesRegex(ValueError, "post-exit"):
                lifecycle.finalize(children, births)
        self.assertTrue(all(c.process.returncode == 0 for c in children.values()))
        receipt = lifecycle.finalize(children, births)
        self.assertEqual(receipt["stage"], "AfterDriverExit")
        self.assertTrue(all(r["gone"] for r in receipt["cleanup"].values()))

    def test_coverage_start_identity_and_self_attestation(self):
        with lifecycle.finite_fixture() as (children, births):
            pass
        wrong = copy.deepcopy(births)
        wrong["driver"]["start_ticks"] += 1
        with self.assertRaisesRegex(ValueError, "birth identity"):
            lifecycle.finalize(children, wrong)
        with self.assertRaisesRegex(ValueError, "coverage"):
            lifecycle.finalize(
                children, {k: v for k, v in births.items() if k != "driver"}
            )
        wrong = copy.deepcopy(births)
        wrong["driver"] = lifecycle.identity(os.getpid())
        with self.assertRaisesRegex(ValueError, "own absence"):
            lifecycle.finalize(children, wrong)
        self.assertTrue(
            all(lifecycle.identity(c.pid) != births[r] for r, c in children.items())
        )


if __name__ == "__main__":
    unittest.main()
