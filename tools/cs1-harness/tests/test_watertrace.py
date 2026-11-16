"""Native replay and corruption detection, not a second map qualification."""

import gzip
import json
from pathlib import Path
import tempfile
import unittest

from cs1_harness.watertrace import audit

FIXTURES = Path(__file__).parent / "fixtures"
TRACE = FIXTURES / "watertrace-c7-rio.jsonl.gz"
RECEIPT = FIXTURES / "watertrace-c7-rio-session.json"


class WaterTraceTests(unittest.TestCase):
    def changed(self, transform, receipt=RECEIPT):
        rows = [json.loads(line) for line in gzip.decompress(TRACE.read_bytes()).decode().splitlines()]
        transform(rows)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.jsonl"
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            return audit(path, receipt)

    def test_actual_completed_native_updates_and_endpoint_replay(self):
        result = audit(TRACE, RECEIPT)
        self.assertTrue(result["passes"], result["errors"])
        self.assertEqual(result["transactions"], 286)
        self.assertEqual(result["comparisons"]["intake_cells"], 74074)
        self.assertEqual(result["unfinished_unpublished_tail_records"], 1)

    def test_corrupted_native_input_cell_is_detected(self):
        def corrupt(rows):
            source = next(s for s in rows[-1]["sources"] if s["id"] == 92)
            offset = next(
                i for i in range(0, len(source["pre_cells"]), 4) if source["pre_cells"][i] > source["input_cells"][i]
            )
            source["input_cells"][offset] += 1

        result = self.changed(corrupt)
        self.assertFalse(result["passes"])
        self.assertTrue(any("per-cell removal" in error for error in result["errors"]))

    def test_missing_completed_phase_is_not_excused_by_tail_policy(self):
        result = self.changed(lambda rows: rows[1].update(complete=False))
        self.assertFalse(result["passes"])
        self.assertIn("0: incomplete transaction", result["errors"])

    def test_changed_published_checkpoint_is_detected(self):
        def corrupt(rows):
            rows[0]["checkpoint"]["cells"][0] += 1

        result = self.changed(corrupt)
        self.assertFalse(result["passes"])
        self.assertTrue(any("paused published grid" in error for error in result["errors"]))

    def test_dirty_cleanup_is_not_a_removed_observer(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = json.loads(RECEIPT.read_text())
            receipt["cleanup"]["game"] = [123456]
            path = Path(directory) / "receipt.json"
            path.write_text(json.dumps(receipt))
            result = audit(TRACE, path)
        self.assertFalse(result["passes"])
        self.assertIn("disposable process was not cleaned up", result["errors"])

    def test_receipt_for_another_map_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = json.loads(RECEIPT.read_text())
            receipt["map"]["sha256"] = "0" * 64
            path = Path(directory) / "receipt.json"
            path.write_text(json.dumps(receipt))
            result = audit(TRACE, path)
        self.assertFalse(result["passes"])
        self.assertIn("session map differs from trace package binding", result["errors"])


if __name__ == "__main__":
    unittest.main()
