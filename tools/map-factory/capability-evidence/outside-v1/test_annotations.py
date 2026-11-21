"""Retained failures must not become capability negatives or rewritten successes."""

import copy
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from annotate import HERE, annotations, summary, path_endpoints
from verify import verify
from assemble import write_new_raw


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

    def test_retained_raw_cannot_be_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "raw.gz"
            write_new_raw(path, b"original observation")
            original = path.read_bytes()
            write_new_raw(path, b"original observation")
            self.assertEqual(path.read_bytes(), original)
            with self.assertRaisesRegex(ValueError, "refusing to replace"):
                write_new_raw(path, b"rewritten observation")
            self.assertEqual(path.read_bytes(), original)

    def test_historical_literal_boundary_and_midpoint_cells_are_separate(self):
        historical = copy.deepcopy(self.evidence)
        historical["rows"] = historical["rows"][:619]
        cells = summary(annotations(historical))[1]
        self.assertEqual(sum(c["observed"] is True for c in cells), 11)
        self.assertEqual(sum(c["observed"] is None for c in cells), 25)
        self.assertEqual(
            sum(c["observed"] is None and c["midpoint_positives"] > 0 for c in cells), 8
        )

    def test_returned_positions_not_segment_flags_define_witness(self):
        segments = {
            1: {"start": 10, "end": 11, "start_flags": "Outside"},
            2: {"start": 20, "end": 21, "end_flags": "Outside"},
        }
        request = {"from": [1, 0, 0], "to": [2, 0, 255]}
        self.assertEqual(
            path_endpoints(request, {"positions": [[1, 0, 0], [2, 0, 255]]}, segments),
            (True, True),
        )
        self.assertEqual(
            path_endpoints(
                request, {"positions": [[1, 0, 128], [2, 0, 128]]}, segments
            ),
            (True, False),
        )
        midpoint = {"from": [1, 0, 128], "to": [2, 0, 128]}
        self.assertEqual(
            path_endpoints(
                midpoint, {"positions": [[1, 0, 128], [2, 0, 128]]}, segments
            ),
            (False, True),
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
