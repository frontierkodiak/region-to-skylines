import pathlib
import tempfile
import unittest

from cs1_harness.client import HarnessError
from cs1_harness.waterstudy import WaterStudy


class Client:
    def __init__(self):
        self.calls = []
        self.omit = False

    def call(self, operation, **kwargs):
        self.calls.append((operation, kwargs))
        return {
            "schema": "polli.water-study-snapshot/1",
            "prefix": kwargs["prefix"],
            "before": {"simulation_frame": 10},
            "after": {"simulation_frame": 12},
            "samples": [] if self.omit else [{"x": x, "z": z} for x, z in kwargs["points"]],
        }


class WaterStudyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.client = Client()
        self.rows = []
        self.points = [{"name": "frozen-branch", "x": 16, "z": 32}]
        self.study = WaterStudy(
            self.client, pathlib.Path(self.temp.name), self.points, 0.25, lambda k, v: self.rows.append((k, v))
        )

    def test_subminute_captures_are_unique_and_retain_brackets_and_names(self):
        for minute in [0, 0.25, 0.5, 0.75, 1]:
            self.study.capture(minute)
        self.assertEqual([r[1]["prefix"] for r in self.rows], [f"ws{i:06d}" for i in range(5)])
        self.assertEqual([r[1]["scheduled_minute"] for r in self.rows], [0, 0.25, 0.5, 0.75, 1])
        self.assertTrue(all(r[1]["samples"][0]["name"] == "frozen-branch" for r in self.rows))
        self.assertNotEqual(self.rows[0][1]["before"], self.rows[0][1]["after"])

    def test_missed_slots_are_not_filled_by_duplicate_late_observations(self):
        self.study.capture(0)
        self.assertIsNone(self.study.capture(0.1))
        result = self.study.capture(0.8)
        self.assertEqual(result["missed_slots"], [1, 2])
        self.assertEqual(result["scheduled_slot"], 3)
        self.assertEqual(len(self.client.calls), 2)
        final = self.study.capture(0.8, final=True)
        self.assertTrue(final["final"])
        self.assertNotEqual(final["prefix"], result["prefix"])

    def test_missing_authored_probe_and_invalid_cadence_fail_closed(self):
        self.client.omit = True
        with self.assertRaisesRegex(HarnessError, "omitted"):
            self.study.capture(0)
        self.assertFalse(self.rows)
        for every in [0, -1, float("nan"), float("inf"), 6]:
            with self.assertRaises(ValueError):
                WaterStudy(self.client, pathlib.Path(self.temp.name), self.points, every, lambda *_: None)
