"""Portable, real wall-clock socket tests. No game imports, ports or licensed bytes."""

from pathlib import Path
import tempfile
import time
import unittest

from fixtures import server
from wire import Deadline, Wire, Unknown, decode


class WireTests(unittest.TestCase):
    def exercise(self, row, timeout=0.12, max_bytes=4096):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "server"
            with server([row], directory) as owned:
                trace = []
                start = time.monotonic()
                client = Wire(owned["port"], Deadline.after(timeout), trace, max_bytes)
                try:
                    result = client.call(row["op"])
                except Unknown as error:
                    result = str(error)
                elapsed = time.monotonic() - start
            calls = decode((directory / "calls.json").read_bytes())
            self.assertIsNone(owned["after"])
            self.assertEqual(owned["exit_code"], 0)
            self.assertEqual(len(calls), 1)
            self.assertLess(elapsed, 0.75)
            return result, trace, calls, elapsed

    def test_success_protocol(self):
        result, trace, calls, _ = self.exercise(
            dict(op="status", reply=dict(ok=True, loading=False))
        )
        self.assertEqual(result, dict(ok=True, loading=False))
        self.assertEqual(calls[0]["request"], dict(op="status"))
        self.assertGreater(trace[0]["sent_bytes"], 0)

    def test_blocked_read_has_actual_server_evidence(self):
        result, trace, calls, elapsed = self.exercise(
            dict(op="stats", reply=dict(ok=True), mode="blocked")
        )
        self.assertIn("deadline", result)
        self.assertGreater(elapsed, 0.09)
        self.assertGreater(calls[0]["blocked_until"], trace[0]["ended"])
        self.assertEqual(trace[0]["received_bytes"], 0)

    def test_no_newline_and_drip_share_absolute_deadline(self):
        for mode in ("no-newline", "drip"):
            with self.subTest(mode=mode):
                result, trace, _, elapsed = self.exercise(
                    dict(op="stats", reply=dict(ok=True, data="x" * 100), mode=mode)
                )
                self.assertIn("deadline", result)
                self.assertGreater(trace[0]["received_bytes"], 0)
                self.assertGreater(elapsed, 0.09)

    def test_envelopes_fail_closed(self):
        for raw in (
            '{"ok":false,"error":"no"}\n',
            '{"ok":"false"}\n',
            '{"ok":true,"ok":true}\n',
            '{"ok":true,"nested":{"x":1,"x":2}}\n',
            '{"ok":true,"x":NaN}\n',
            "{bad}\n",
            "[]\n",
            '{"ok":1}\n',
            "{}\n",
            '{"ok":true}\n{}\n',
        ):
            with self.subTest(raw=raw):
                result, trace, _, _ = self.exercise(dict(op="status", raw=raw))
                self.assertIsInstance(result, str)
                self.assertIn("error", trace[0])

    def test_oversize_and_eof(self):
        result, _, _, _ = self.exercise(
            dict(op="status", reply=dict(ok=True, data="x" * 1000)), max_bytes=100
        )
        self.assertIn("oversized", result)
        result, _, _, _ = self.exercise(dict(op="status", raw='{"ok":true}'))
        self.assertIn("missing newline", result)

    def test_expired_budget_makes_no_call(self):
        trace = []
        with self.assertRaises(Unknown):
            Wire(1, Deadline(time.monotonic() - 1), trace).call("path_start")
        self.assertEqual(trace, [])

    def test_minimum_deadline_not_renewed(self):
        parent = Deadline.after(0.04)
        child = Deadline.after(30, parent)
        self.assertEqual(child.end, parent.end)
        time.sleep(0.05)
        with self.assertRaises(Unknown):
            child.remaining()


if __name__ == "__main__":
    unittest.main()
