"""Real-byte regressions plus adversarial boundary mutations; no old scoring."""

import copy
import io
import unittest
from unittest.mock import patch
import zipfile

import fixtures
import protocol as p
import readiness as r


def real_query():
    row = fixtures.observation("hanami")["paths"][0]
    plan = row["plan"]
    request = p.Request(
        plan["mode"],
        p.position(plan["request"]["from"]),
        p.position(plan["request"]["to"]),
        plan["max_length"],
        row["effective"]["build_index"],
    )
    # This build index is fixture-only, not independent observation evidence.
    return row, request


class Wire(unittest.TestCase):
    def test_retained_metabool(self):
        context = fixtures.observation("asanu")["native_context"]
        self.assertEqual(context["invert_traffic"], "False")
        p.entry(context)
        self.assertFalse(p.meta_bool(context["invert_traffic"]))
        with zipfile.ZipFile(io.BytesIO(fixtures.load("original_guard"))) as archive:
            source = archive.read("collect.py").decode()
        self.assertIn(
            'observation["native_context"]["invert_traffic"]\n                    or',
            source,
        )
        self.assertTrue(bool(context["invert_traffic"]))  # actual original bug
        for value in (True, "True"):
            self.assertTrue(p.meta_bool(value))
        for value in (0, 1, None, "", "false", "FALSE", " False ", "0", [], {}):
            with self.subTest(value=value), self.assertRaises(p.ProtocolError):
                p.meta_bool(value)
        for key in context:
            bad = dict(context)
            del bad[key]
            with self.subTest(key=key), self.assertRaises(p.ProtocolError):
                p.entry(bad)
        with self.assertRaises(p.ProtocolError):
            p.entry(dict(context, extra=True))

    def test_retained_envelope(self):
        row, request = real_query()
        self.assertIs(row["result"]["ok"], True)
        self.assertEqual(
            p.decide(row["effective"], row["result"], request).literal_label,
            p.Label.SUCCESS,
        )
        self.assertEqual(
            p.decide(row["effective"], row["result"], request).qualification, "unknown"
        )
        freeze = fixtures.observation("freeze")
        self.assertNotEqual(
            set(row["result"]), set(freeze["protocol"]["result_schema"])
        )
        self.assertIn(
            "native result schema differs", fixtures.load("schema_failure").decode()
        )
        correction = fixtures.observation("schema_correction")
        self.assertEqual(
            correction["timing"],
            "analysis correction after stock-2 control outcomes; no model refit",
        )
        # Every retained Hanami control traverses the new typed path, no old scorer.
        for observed in fixtures.observation("hanami")["paths"]:
            plan = observed["plan"]
            req = p.Request(
                plan["mode"],
                p.position(plan["request"]["from"]),
                p.position(plan["request"]["to"]),
                plan["max_length"],
                observed["effective"]["build_index"],
            )
            expected = (
                p.Label.SUCCESS if plan["kind"] == "positive" else p.Label.NO_PATH
            )
            self.assertEqual(
                p.decide(observed["effective"], observed["result"], req).literal_label,
                expected,
            )

    def test_every_missing_extra_and_boolean_field(self):
        row, request = real_query()
        for which in ("effective", "result"):
            for key in row[which]:
                bad = copy.deepcopy(row)
                del bad[which][key]
                with self.subTest(which=which, missing=key):
                    self.assertEqual(
                        p.decide(
                            bad["effective"], bad["result"], request
                        ).literal_label,
                        p.Label.UNKNOWN,
                    )
            bad = copy.deepcopy(row)
            bad[which]["extra"] = 1
            self.assertEqual(
                p.decide(bad["effective"], bad["result"], request).literal_label,
                p.Label.UNKNOWN,
            )
        for key in ("ok", "complete", "success", "released"):
            for value in (0, 1, "True", "False", None, []):
                bad = copy.deepcopy(row)
                bad["result"][key] = value
                with self.subTest(key=key, value=value):
                    self.assertEqual(
                        p.decide(
                            bad["effective"], bad["result"], request
                        ).literal_label,
                        p.Label.UNKNOWN,
                    )

    def test_request_handle_and_result_mutations(self):
        row, request = real_query()
        changes = {
            "id": True,
            "from": [1, 0, 0],
            "to": [1, 0, 0],
            "mode": "ship",
            "vehicle": "Ship",
            "category": "All",
            "lane_types": "Vehicle, CargoVehicle",
            "seed": 858,
            "max_length": 200000,
            "build_index": True,
        }
        for key, value in changes.items():
            bad = dict(row["effective"], **{key: value})
            with self.subTest(key=key):
                self.assertEqual(
                    p.decide(bad, row["result"], request).literal_label, p.Label.UNKNOWN
                )
        for key, value in {
            "id": row["result"]["id"] + 1,
            "flags": 12,
            "length": float("nan"),
            "positions": [[1, 0, 0]],
            "released": False,
            "complete": False,
            "success": False,
        }.items():
            with self.subTest(key=key):
                result = dict(row["result"], **{key: value})
                self.assertEqual(
                    p.decide(row["effective"], result, request).literal_label,
                    p.Label.UNKNOWN,
                )
        pending = dict(
            row["result"],
            flags=2,
            complete=False,
            success=False,
            released=False,
            positions=[],
        )
        d = p.decide(row["effective"], pending, request)
        self.assertTrue(d.transport_success)
        self.assertFalse(d.native.complete)
        self.assertEqual(d.literal_label, p.Label.UNKNOWN)
        failed = {"ok": False, "error": "refused", "exception": "Exception"}
        self.assertFalse(p.decide(failed, failed, request).transport_success)
        for data in (b'{"ok":true,"ok":false}', b'{"v":NaN}', b"[]", b"{"):
            with self.assertRaises(p.ProtocolError):
                p.decode(data)

    def test_original_mutants_are_detected(self):
        # Run the same behavior assertions with historical mistakes reintroduced.
        # Assert actual failing tests, not merely different implementation output.
        for test, target, mutant in (
            ("test_retained_metabool", "protocol.meta_bool", bool),
            (
                "test_retained_envelope",
                "protocol.envelope",
                lambda value, keys: p.exact(value, keys, "original body-only schema"),
            ),
        ):
            result = unittest.TestResult()
            with patch(target, mutant):
                Wire(test).run(result)
            self.assertEqual(result.testsRun, 1)
            self.assertFalse(result.wasSuccessful(), target)


class Controls(unittest.TestCase):
    def test_first_failure_is_not_erased_by_parser_repair(self):
        freeze = fixtures.observation("freeze")
        observations = {
            c["case_id"]: fixtures.observation(name)
            for c, name in zip(freeze["controls"], ("asanu", "hanami"))
        }
        result = r.check(freeze["controls"], observations, {}, set())
        self.assertFalse(result.ready_for_measurement)
        self.assertEqual(result.pre_export_qualification, "unknown")
        self.assertTrue(any("failed/incomplete" in x for x in result.reasons))
        self.assertIn("native-cost", result.missing_native_fact)
        self.assertEqual(observations["stock-1"]["paths"], [])


if __name__ == "__main__":
    unittest.main()
