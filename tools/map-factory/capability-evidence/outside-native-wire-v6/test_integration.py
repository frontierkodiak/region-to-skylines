"""Private byte checks are explicit; public socket checks live in test_wire.py."""

import copy
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest

import accepted_api as api
import candidate
from entry import preflight
from exercise import ConstructedAuthority, Factory, run, script_for
from verify import request_for


@unittest.skipUnless(
    os.environ.get("PL1321_RUN"),
    "private build/store prerequisite; run test_wire.py portably",
)
class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(os.environ["PL1321_RUN"])
        cls.store = api.spec.ArtifactStore(cls.root / "evidence")
        cls.frozen = api.spec.read(cls.root / "candidate.json")
        cls.native, _ = candidate.validate(cls.frozen, cls.store)
        cls.request = request_for(cls.frozen)
        cls.refusals = []

    def refused(self, frozen=None, request=None, authority=None):
        factory = Factory(self.root / "MUST-NOT-EXIST")
        with self.assertRaises((ValueError, TypeError, KeyError, OSError)) as failure:
            preflight(
                frozen or self.frozen,
                self.store,
                request or self.request,
                authority,
                factory,
            )
        self.assertEqual(factory.effects, [])
        self.refusals.append(
            dict(reason=str(failure.exception), effects=factory.effects)
        )

    def test_pre_effect_authority_and_integrity(self):
        self.refused()
        self.refused(authority={"kind": "OFFLINE_CONSTRUCTED_ONLY"})
        grant = ConstructedAuthority(self.request)
        self.refused(request=replace(self.request, purpose="NATIVE"), authority=grant)
        for field in ("binding", "limits", "freeze_sha256", "session"):
            self.refused(
                request=replace(
                    self.request,
                    **{field: b"wrong" if field in ("binding", "limits") else ""},
                ),
                authority=grant,
            )
        for key in self.frozen:
            value = copy.deepcopy(self.frozen)
            value[key] = None
            self.refused(frozen=value, authority=grant)
        for key in self.frozen["source_map"]:
            value = copy.deepcopy(self.frozen)
            del value["source_map"][key]
            self.refused(frozen=value, authority=grant)
        for key in self.frozen["v5"]["inventory"]:
            value = copy.deepcopy(self.frozen)
            value["v5"]["inventory"][key] = {}
            self.refused(frozen=value, authority=grant)

    def exercise(self, script=None, limits=None):
        with tempfile.TemporaryDirectory(dir=self.root) as temp:
            factory = Factory(Path(temp), script, limits)
            result = run(
                self.frozen,
                self.store,
                self.request,
                ConstructedAuthority(self.request),
                factory,
            )
            self.assertEqual(set(result["lifecycle"]["births"]), api.lifecycle.ROLES)
            self.assertEqual(
                len({b["pid"] for b in result["lifecycle"]["births"].values()}), 5
            )
            self.assertTrue(
                all(
                    b is None
                    for b in result["lifecycle"]["after_exit_identities"].values()
                )
            )
            self.assertTrue(
                all(code == 0 for code in result["lifecycle"]["exit_codes"].values())
            )
            return result

    def test_real_socket_collector_retention_bundle_gate(self):
        result = self.exercise()
        self.assertTrue(result["result"]["structural_pass"])
        self.assertEqual(result["result"]["control_admission"], "Unknown")
        self.assertIsNone(result["pending"])
        trace = result["trace"]
        self.assertEqual(sum(r["op"] == "path_start" for r in trace), 12)
        for i, row in enumerate(trace):
            if row["op"] == "path_start":
                self.assertEqual(trace[i - 1]["op"], "study_build_index")
                self.assertEqual(trace[i + 1]["op"], "path_result")

    def test_first_bad_handle_or_release_stops_and_retains(self):
        for field, value in (("id", 1000), ("released", False), ("complete", "false")):
            script = script_for(self.native, self.store)
            next(r for r in script if r["op"] == "path_result")["reply"][field] = value
            result = self.exercise(script)
            self.assertFalse(result["result"]["structural_pass"])
            self.assertIsNotNone(result["pending"])
            self.assertEqual(sum(r["op"] == "path_start" for r in result["trace"]), 1)
            self.assertTrue(result["records"][0]["observed"]["paths"][0]["error"])

    def test_blocking_load_and_query_absolute_wall_deadlines(self):
        for op, key in (("new_game", "load_seconds"), ("path_result", "query_seconds")):
            script = script_for(self.native, self.store)
            next(r for r in script if r["op"] == op)["mode"] = "blocked"
            limits = dict(self.native.descriptor["limits"], **{key: 0.08})
            result = self.exercise(script, limits)
            self.assertIn("deadline", result["result"]["reason"])
            self.assertLess(
                max(r["ended"] - r["started"] for r in result["trace"]), 0.5
            )
            if op == "path_result":
                self.assertIsNotNone(result["pending"])
                self.assertEqual(
                    sum(r["op"] == "path_start" for r in result["trace"]), 1
                )

    @classmethod
    def tearDownClass(cls):
        (cls.root / "pre-effect-refusals.json").write_bytes(
            api.spec.canonical(cls.refusals)
        )


if __name__ == "__main__":
    unittest.main()
