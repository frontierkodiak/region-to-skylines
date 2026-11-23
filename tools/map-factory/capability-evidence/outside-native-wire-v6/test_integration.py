"""Private byte checks are explicit; public socket checks live in test_wire.py."""

import copy
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import time
import unittest

import accepted_api as api
import candidate
from entry import enter
from exercise import ConstructedAuthority, Factory, run, script_for
from wire_check import request_for


@unittest.skipUnless(
    os.environ.get("PL1321_RUN"),
    "private build/store prerequisite; run test_wire.py portably",
)
class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(os.environ["PL1321_RUN"])
        cls.store = api.spec.ArtifactStore(cls.root / "evidence")
        cls.frozen = api.spec.read(
            cls.root / os.environ.get("PL1321_FREEZE", "candidate.json")
        )
        cls.native, _ = candidate.validate(cls.frozen, cls.store)
        cls.request = request_for(cls.frozen)
        cls.refusals = []

    def refused(self, frozen=None, request=None, authority=None):
        factory = Factory(self.root / "MUST-NOT-EXIST")
        with self.assertRaises((ValueError, TypeError, KeyError, OSError)) as failure:
            with enter(
                self.frozen if frozen is None else frozen,
                self.store,
                self.request if request is None else request,
                authority,
                factory,
            ):
                self.fail("refused entry executed its effect boundary")
        self.assertEqual(factory.effects, [])
        self.refusals.append(
            dict(reason=str(failure.exception), effects=factory.effects)
        )

    def test_pre_effect_authority_and_integrity(self):
        self.refused()
        self.refused(frozen={})
        self.refused(request={})

        class CallerAuthorizer:
            purpose = "CONSTRUCTED"

            def authorize(self, request, frozen):
                return True

        self.refused(authority=CallerAuthorizer())
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
            for mutation in ("delete", "null", "extra"):
                value = copy.deepcopy(self.frozen)
                if mutation == "delete":
                    del value[key]
                elif mutation == "null":
                    value[key] = None
                else:
                    value["extra"] = True
                self.refused(frozen=value, authority=grant)
        for key in self.frozen["source_map"]:
            value = copy.deepcopy(self.frozen)
            del value["source_map"][key]
            self.refused(frozen=value, authority=grant)
        for key in self.frozen["v5"]["inventory"]:
            value = copy.deepcopy(self.frozen)
            value["v5"]["inventory"][key] = {}
            self.refused(frozen=value, authority=grant)

    def exercise(self, script=None, limits=None, inventory_override=None):
        with tempfile.TemporaryDirectory(dir=self.root) as temp:
            factory = Factory(Path(temp), script, limits, inventory_override)
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
            limits = dict(
                self.native.descriptor["limits"],
                **{key: 6.0 if op == "new_game" else 2.0},
            )
            result = self.exercise(script, limits)
            self.assertIn("deadline", result["result"]["reason"])
            self.assertLess(
                max(r["ended"] - r["started"] for r in result["trace"]), 6.5
            )
            stalled = next(
                r for r in result["server_calls"] if r["request"]["op"] == op
            )
            failed_call = next(r for r in result["trace"] if r["op"] == op)
            self.assertGreater(stalled["blocked_until"], failed_call["ended"])
            if op == "path_result":
                self.assertIsNotNone(result["pending"])
                self.assertEqual(
                    sum(r["op"] == "path_start" for r in result["trace"]), 1
                )

    def test_opening_and_whole_study_interrupt_pending_query(self):
        for key in ("opening_seconds", "total_seconds"):
            script = script_for(self.native, self.store)
            next(r for r in script if r["op"] == "path_result")["mode"] = "blocked"
            limits = dict(self.native.descriptor["limits"], **{key: 6.0})
            start = time.monotonic()
            result = self.exercise(script, limits)
            elapsed = time.monotonic() - start
            self.assertLess(elapsed, 10)
            self.assertFalse(result["result"]["structural_pass"])
            self.assertIsNotNone(result["pending"])
            self.assertEqual(sum(r["op"] == "path_start" for r in result["trace"]), 1)
            stalled = next(
                r for r in result["server_calls"] if r["request"]["op"] == "path_result"
            )
            self.assertGreater(stalled["blocked_until"], start + 6)
            self.assertEqual(result["records"][0]["observed"]["completed"], False)
            self.assertIn("deadline", result["result"]["reason"])

    def test_runtime_inventory_omissions_are_retained_and_stop_before_query(self):
        for group in ("roots", "plugins", "assemblies"):
            value = copy.deepcopy(self.native.descriptor["inventory"])
            del value[group][next(iter(value[group]))]
            result = self.exercise(inventory_override=value)
            self.assertFalse(result["result"]["structural_pass"])
            self.assertFalse(any(r["op"] == "path_start" for r in result["trace"]))
            captured = self.store.json(
                result["inventory_captures"][0], "failed constructed inventory"
            )
            self.assertEqual(captured, value)

    def test_effective_and_context_drift_stop_at_first_request(self):
        for field, value in (
            ("seed", 858),
            ("vehicle", "Train"),
            ("max_length", 99999),
        ):
            script = script_for(self.native, self.store)
            next(r for r in script if r["op"] == "path_start")["reply"][field] = value
            result = self.exercise(script)
            self.assertFalse(result["result"]["structural_pass"])
            self.assertEqual(sum(r["op"] == "path_start" for r in result["trace"]), 1)
            self.assertIsNotNone(result["pending"])
        script = script_for(self.native, self.store)
        next(r for r in script if r["op"] == "stats")["reply"]["invert_traffic"] = True
        result = self.exercise(script)
        self.assertFalse(result["result"]["structural_pass"])
        self.assertFalse(any(r["op"] == "path_start" for r in result["trace"]))

    def test_all_mode_height_and_invert_graph_drift_stop_before_query(self):
        control = self.native.value["controls"][0]
        graph = self.store.json(control["exact_graph_sha256"], "frozen input graph")
        for mode in ("ship", "air"):
            for change in ("height", "invert"):
                script = script_for(self.native, self.store)
                networks = next(r for r in script if r["op"] == "networks")["reply"]
                segment = next(
                    s for s in networks["segments"] if s["id"] == graph[mode][0]["id"]
                )
                if change == "height":
                    segment["a"][1] += 1
                else:
                    flags = segment["flags"]
                    segment["flags"] = (
                        flags.replace("Invert", "")
                        if "Invert" in flags
                        else flags + ", Invert"
                    )
                result = self.exercise(script)
                self.assertFalse(result["result"]["structural_pass"])
                self.assertFalse(any(r["op"] == "path_start" for r in result["trace"]))

    def test_partial_submission_and_stalled_handle_remain_unresolved(self):
        for kind in ("partial-request", "stalled"):
            script = script_for(self.native, self.store)
            if kind == "partial-request":
                next(r for r in script if r["op"] == "path_start")["mode"] = kind
            else:
                index = next(
                    i for i, r in enumerate(script) if r["op"] == "path_result"
                )
                pending = copy.deepcopy(script[index])
                pending["reply"].update(
                    flags=1,
                    complete=False,
                    released=False,
                    success=False,
                    positions=[],
                    length=0,
                )
                script[index] = pending
                stalled = copy.deepcopy(pending)
                stalled["mode"] = "blocked"
                script.insert(index + 1, stalled)
            limits = dict(self.native.descriptor["limits"], query_seconds=2)
            result = self.exercise(script, limits)
            self.assertFalse(result["result"]["structural_pass"])
            self.assertIsNotNone(result["pending"])
            self.assertEqual(sum(r["op"] == "path_start" for r in result["trace"]), 1)
            if kind == "partial-request":
                self.assertTrue(
                    any(r.get("partial_request_hex") for r in result["server_calls"])
                )
            else:
                polls = [r for r in result["trace"] if r["op"] == "path_result"]
                self.assertEqual(len(polls), 2)
                self.assertEqual(polls[0]["args"], polls[1]["args"])

    def test_complete_constructed_study_keeps_admission_unknown(self):
        from exercise import study_run

        with tempfile.TemporaryDirectory(dir=self.root) as temp:
            result = study_run(self.frozen, self.store, Path(temp))
        self.assertEqual(result["control_admission"], "Unknown")
        self.assertEqual(result["native_requests"], 0)
        self.assertEqual(result["planned_unobserved"], [])
        self.assertGreaterEqual(len(result["cases"]), 3)
        self.assertTrue(all(r["result"]["structural_pass"] for r in result["cases"]))
        self.assertTrue(
            all(r["result"]["control_admission"] == "Unknown" for r in result["cases"])
        )

    @classmethod
    def tearDownClass(cls):
        (cls.root / "pre-effect-refusals.json").write_bytes(
            api.spec.canonical(cls.refusals)
        )


if __name__ == "__main__":
    unittest.main()
