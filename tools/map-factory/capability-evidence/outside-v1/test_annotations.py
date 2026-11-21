"""Retained failures must not become capability negatives or rewritten successes."""

import copy
import json
import unittest
from unittest.mock import patch

from annotate import HERE, annotations, summary
from verify import verify


class AnnotationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = json.loads((HERE / "evidence.json").read_text())

    def test_no_capability_negative_and_same_role_failures_retained(self):
        evidence = annotations(copy.deepcopy(self.evidence))
        same = [
            r
            for r in evidence["rows"]
            if r.get("pair_status") == "same_role_probe_limited"
        ]
        self.assertEqual(len(same), 138)
        self.assertTrue(
            all(
                r["observed"] is False and r["capability_observed"] is None
                for r in same
            )
        )
        self.assertTrue(
            all(c["observed"] in [True, None] for c in summary(evidence)[1])
        )

    def test_verifier_rejects_rewritten_raw_result(self):
        changed = copy.deepcopy(self.evidence)
        row = next(
            r for r in changed["rows"] if r.get("request") and r["observed"] is False
        )
        row["path_result"]["positions"] = [[999, 0, 0]]
        original = __import__("pathlib").Path.read_text

        def read(path, *args, **kwargs):
            if path == HERE / "evidence.json":
                return json.dumps(changed)
            return original(path, *args, **kwargs)

        with (
            patch("pathlib.Path.read_text", read),
            self.assertRaisesRegex(ValueError, "differs from raw"),
        ):
            verify()
