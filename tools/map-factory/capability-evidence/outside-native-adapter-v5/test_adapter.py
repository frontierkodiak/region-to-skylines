"""Real adapter refusal, byte mutation, consumer and five-process integration tests."""

import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from api import ROOT, spec, pipeline, lifecycle
import adapter_spec
import adapter
import fresh_build
import verify_adapter


class AdapterBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.run_root = Path(os.environ["PL1318_RUN"])
        cls.store = spec.ArtifactStore(cls.run_root / "evidence")
        cls.native = adapter_spec.validate(
            spec.read(cls.run_root / "adapter-freeze.json"), cls.store
        )
        cls.refusal_log = []
        cls.freeze = cls.native.descriptor
        cls.authority = dict(
            kind="OFFLINE_CONSTRUCTED_ONLY",
            spec_sha256=cls.native.sha256,
            binding=cls.native.bindings(),
        )
        cls.bundle = spec.read(cls.run_root / "exercise-final/bundle.json")

    def refused(self, frozen=None, authority=None, transport=None, source_root=ROOT):
        transport = transport or adapter.RecordingTransport()
        with self.assertRaises(
            (ValueError, TypeError, KeyError, OSError, spec.ProtocolError)
        ) as failure:
            adapter.preflight(
                self.freeze if frozen is None else frozen,
                self.store,
                self.authority if authority is None else authority,
                transport,
                source_root,
            )
        self.assertEqual(transport.calls, [])
        self.refusal_log.append(
            dict(reason=str(failure.exception), calls=copy.deepcopy(transport.calls))
        )

    def reject_bundle(self, value):
        with self.assertRaises(
            (ValueError, TypeError, KeyError, OSError, spec.ProtocolError)
        ):
            adapter.gate(value, self.freeze, self.store)

    def test_shared_api_builder_collector_bundle(self):
        self.assertEqual(
            adapter.gate(self.bundle, self.freeze, self.store)["native_requests"], 0
        )
        self.assertEqual(self.bundle["spec_bytes"].encode(), self.native.encoded)
        self.assertEqual(
            self.bundle["binding"], pipeline.collector_binding(self.native)
        )
        self.assertNotEqual(
            self.native.bindings()["fresh_build_sha256"],
            self.freeze["v4"]["build_receipt"],
        )
        self.assertEqual(
            len(self.freeze["v4"]["sources"]["measurement_build"]["files"]), 87
        )
        self.assertEqual(
            len(self.freeze["v4"]["sources"]["readiness_helpers"]["files"]), 35
        )
        self.assertEqual(len(self.freeze["adapter_sources"]["files"]), 7)

    def test_default_and_wrong_authority_zero_effect(self):
        self.refused(authority={})
        self.refused(authority=dict(self.authority, kind="NATIVE"))
        for key in ("binding", "spec_sha256"):
            self.refused(authority=dict(self.authority, **{key: None}))

        class Foreign(adapter.RecordingTransport):
            pass

        self.refused(transport=Foreign())

    def test_exact_descriptor_shape_zero_effect(self):
        for key in self.freeze:
            for mutation in ("delete", "null", "extra"):
                value = copy.deepcopy(self.freeze)
                if mutation == "delete":
                    del value[key]
                elif mutation == "null":
                    value[key] = None
                else:
                    value["extra"] = True
                self.refused(frozen=value)

    def test_all_source_roles_and_actual_executable_bytes(self):
        with tempfile.TemporaryDirectory(dir=self.run_root) as temp:
            source_root = Path(temp)
            paths = set(self.freeze["adapter_sources"]["files"])
            for role in self.freeze["v4"]["sources"].values():
                paths.update(role["files"])
            for path in paths:
                target = source_root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / path).read_bytes())
            for path in paths:
                target = source_root / path
                original = target.read_bytes()
                try:
                    target.write_bytes(original + b"\n# MUTATION\n")
                    self.refused(source_root=source_root)
                finally:
                    target.write_bytes(original)
        for key in self.freeze["adapter_sources"]["files"]:
            value = copy.deepcopy(self.freeze)
            del value["adapter_sources"]["files"][key]
            value["adapter_sources"]["sha256"] = spec.digest(
                value["adapter_sources"]["files"]
            )
            self.refused(frozen=value)

    def test_retained_byte_mutations(self):
        keys = set(self.freeze["adapter_sources"]["files"].values())
        receipt = self.freeze["fresh_build"]
        keys |= {receipt["dll"], receipt["compiler_log"], spec.digest(receipt)}
        keys |= set(receipt["references"].values()) | set(
            receipt["staged_sources"].values()
        )
        keys |= {
            receipt["tool_files"]["dotnet"],
            receipt["tool_files"]["sdk/8.0.427/Roslyn/bincore/csc.dll"],
        }
        keys |= set(self.freeze["v4"]["inputs"].values())
        for key in keys:
            target = self.store.root / key
            original = target.read_bytes()
            try:
                target.write_bytes(b"CORRUPT")
                self.refused()
                target.unlink()
                self.refused()
            finally:
                target.write_bytes(original)

    def test_fresh_build_receipt_and_arguments(self):
        for key in self.freeze["fresh_build"]:
            value = copy.deepcopy(self.freeze)
            value["fresh_build"][key] = None
            self.refused(frozen=value)
        value = copy.deepcopy(self.freeze)
        value["fresh_build"]["argv"].append("-unsafe-")
        self.refused(frozen=value)
        # Offline replay does not claim a newly invoked build merely from a DLL.
        with self.assertRaises(FileExistsError):
            fresh_build.build(
                self.store, self.run_root / "fresh-build", Path("/ABSENT")
            )

    def test_full_inventory_shared_omission_and_extra_zero_effect(self):
        for group in ("files", "roots", "plugins", "assemblies"):
            for key in self.freeze["inventory"][group]:
                value = copy.deepcopy(self.freeze)
                del value["inventory"][group][key]
                self.refused(frozen=value)
                b = copy.deepcopy(self.bundle)
                del b["inner"]["policy"][group][key]
                # Both pre/post are changed too: equality between two omissions is insufficient.
                for observed in b["inner"]["observations"].values():
                    for phase in observed["runtime"].values():
                        del phase[group][key]
                self.reject_bundle(b)
            value = copy.deepcopy(self.freeze)
            value["inventory"][group]["EXTRA"] = None
            self.refused(frozen=value)
        for group in ("adapter_sources", "api"):
            value = copy.deepcopy(self.freeze)
            value[group] = {}
            self.refused(frozen=value)

    def test_capture_retains_actual_bytes_and_rejects_bad_reader(self):
        inv = self.freeze["inventory"]
        with self.assertRaisesRegex(ValueError, "file bytes differ"):
            adapter.retain_inventory(self.native, inv, lambda p: b"wrong", self.store)
        seen = []

        def reader(path):
            seen.append(path)
            return self.store.read(inv["files"][path], "test inventory")

        adapter.retain_inventory(self.native, inv, reader, self.store)
        self.assertEqual(set(seen), set(inv["files"]))
        self.assertGreaterEqual(len(seen), len(inv["files"]) + len(inv["assemblies"]))

    def test_bundle_bindings_dll_mvid_arguments_and_raw_facts(self):
        for key in self.bundle["binding"]:
            b = copy.deepcopy(self.bundle)
            b["binding"][key] = "0" * 64
            self.reject_bundle(b)
        for kind in ("dll", "mvid", "effective", "graph", "raw"):
            b = copy.deepcopy(self.bundle)
            observed = next(iter(b["inner"]["observations"].values()))
            if kind == "dll":
                b["inner"]["policy"]["dll_sha256"] = "0" * 64
            elif kind == "mvid":
                b["inner"]["policy"]["assemblies"]["Cs1Harness"]["mvid"] = "0" * 36
            elif kind == "effective":
                observed["paths"][0]["effective"]["seed"] = 858
            elif kind == "graph":
                observed["paths"][0]["post_graph"] = "0" * 64
            else:
                observed["consumed_fields"] = {}
            self.reject_bundle(b)

    def test_actual_external_driver_process_boundary(self):
        with tempfile.TemporaryDirectory(dir=self.run_root) as temp:
            receipt = adapter.supervise(
                self.native, self.store, Path(temp) / "children"
            )
        adapter.validate_cleanup(receipt, self.store)
        self.assertEqual(set(receipt["births"]), lifecycle.ROLES)
        self.assertTrue(all(code == 0 for code in receipt["exit_codes"].values()))
        self.assertTrue(
            all(lifecycle.identity(v["pid"]) != v for v in receipt["births"].values())
        )
        for mutation in ("missing", "duplicate", "reuse", "self"):
            bad = copy.deepcopy(receipt)
            if mutation == "missing":
                del bad["births"]["driver"]
            elif mutation == "duplicate":
                bad["births"]["driver"] = bad["births"]["game"]
            elif mutation == "reuse":
                bad["births"]["driver"]["start_ticks"] += 1
            else:
                bad["supervisor"] = bad["births"]["driver"]
            with self.assertRaises((ValueError, spec.ProtocolError)):
                adapter.validate_cleanup(bad, self.store)
        with lifecycle.finite_fixture() as (children, births):
            with self.assertRaisesRegex(ValueError, "post-exit"):
                lifecycle.finalize(children, births)

    def test_runtime_preflight_refusal_precedes_effect(self):
        transport = adapter.RecordingTransport()
        with mock.patch.object(
            pipeline, "validate_policy", side_effect=ValueError("policy refusal")
        ):
            self.refused(transport=transport)

    def test_first_protocol_failure_stops_without_next_request(self):
        births = self.bundle["lifecycle"]["births"]
        transport = adapter.RecordingTransport()
        original = transport.call

        def drift(operation, case, index=None, arguments=None):
            value = original(operation, case, index, arguments)
            return value + 1 if operation == "study_build_index" else value

        with mock.patch.object(transport, "call", side_effect=drift):
            with self.assertRaisesRegex(ValueError, "STOP Unknown"):
                adapter.collect(self.native, self.store, births, transport)
        self.assertEqual(
            sum(c.get("operation") == "create_path" for c in transport.calls), 1
        )
        self.assertEqual(
            sum(c.get("operation") == "opening" for c in transport.calls), 1
        )

    def test_deadline_stops_before_first_opening(self):
        transport = adapter.RecordingTransport()
        ticks = iter([0, 4501, 4501, 4501])
        with self.assertRaisesRegex(ValueError, "STOP Unknown: deadline"):
            adapter.collect(
                self.native,
                self.store,
                self.bundle["lifecycle"]["births"],
                transport,
                clock=lambda: next(ticks),
            )
        self.assertEqual(transport.calls, [])

    @classmethod
    def tearDownClass(cls):
        (cls.run_root / "refusal-effects.json").write_bytes(
            spec.canonical(cls.refusal_log)
        )

    def test_historical_preservation(self):
        self.assertTrue(
            all(
                g["unchanged"] for g in verify_adapter.preservation()["groups"].values()
            )
        )


if __name__ == "__main__":
    unittest.main()
