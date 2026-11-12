"""Synthetic offline inventory fixtures; not a native flight-path acceptance test."""

import copy
import hashlib
import pathlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cs1_harness.template_author import author, graph_evidence, poll, source_binding, validate_plan
from cs1_harness.client import HarnessError


class TemplateAuthorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = pathlib.Path(self.temp.name)
        self.plan = {"prefab": "explicit-native-fixture", "endpoints": [[-8639, -2000], [8639, -2000]]}
        self.air = {
            "native_plane": True,
            "ai": "FlightPathAI",
            "subservice": "PublicTransportPlane",
            "lanes": [{"vehicle_types": "Plane"}],
        }
        self.counts = {
            "road": {"incoming": 1, "outgoing": 1},
            "rail": {"incoming": 2, "outgoing": 2},
            "ship": {"incoming": 0, "outgoing": 0},
            "air": {"incoming": 0, "outgoing": 0},
        }
        self.before = {
            "graph": {
                "nodes": [{"id": 4, "prefab": {"ai": "RoadAI"}}],
                "segments": [{"id": 7, "lane_ids": [55]}],
                "outside_counts": self.counts,
            }
        }
        self.after = copy.deepcopy(self.before)
        self.after["graph"]["nodes"] += [
            {"id": 101, "prefab": self.air, "outside": True, "outside_building_id": 50},
            {"id": 102, "prefab": self.air, "outside": False, "outside_building_id": 0},
            {"id": 103, "prefab": self.air, "outside": True, "outside_building_id": 51},
        ]
        self.after["graph"]["segments"] += [
            {"id": 600, "from": 101, "to": 102, "prefab": self.air, "lane_ids": [900]},
            {"id": 601, "from": 102, "to": 103, "prefab": self.air, "lane_ids": [901]},
        ]
        self.after["graph"]["outside_counts"]["air"] = {"incoming": 2, "outgoing": 2}

    @staticmethod
    def binding(source, digest):
        return {
            "source_path": str(source.resolve()),
            "source_sha256": digest,
            "source_binding": "exact_path",
            "source_matches": 1,
        }

    def test_alias_receipt_accepts_only_same_basename_and_exact_hash(self):
        source = self.out / "source.crp"
        source.write_bytes(b"fixture")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        receipt = {
            **self.binding(source, digest),
            "source_path": "/flatpak/alias/source.crp",
            "source_binding": "basename_sha256",
        }
        self.assertEqual(source_binding(receipt, source, digest)["source_path"], receipt["source_path"])
        for changes in [
            {"source_sha256": "0" * 64},
            {"source_matches": 2},
            {"source_matches": True},
            {"source_path": "/flatpak/alias/nearby.crp"},
            {"source_binding": "exact_path"},
        ]:
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "binding"):
                source_binding({**receipt, **changes}, source, digest)

    def test_ambiguous_binding_stops_before_wait_or_authoring(self):
        source = self.out / "source.crp"
        source.write_bytes(b"fixture")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        client = SimpleNamespace(
            call=Mock(return_value={**self.binding(source, digest), "source_matches": 2}), wait=Mock()
        )
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            author(client, source, self.out / "result", self.plan)
        self.assertEqual(client.call.call_count, 1)
        client.wait.assert_not_called()

    def test_explicit_plan_accepts_edges_not_inland_or_nonfinite(self):
        self.assertEqual(validate_plan(self.plan), self.plan)
        for points in (
            [[0, 0], [8639, 0]],
            [[8639, 0], [8639, 100]],
            [[-8639, float("nan")], [8639, 0]],
            [[-9000, 0], [8639, 0]],
        ):
            with self.assertRaises(ValueError):
                validate_plan({**self.plan, "endpoints": points})

    def test_native_inventory_uses_observed_ids_and_preserves_originals(self):
        evidence = graph_evidence(self.before, self.after)
        self.assertEqual([s["id"] for s in evidence["new_segments"]], [600, 601])
        self.assertEqual([n["outside_building_id"] for n in evidence["new_nodes"]], [50, 0, 51])
        self.assertTrue(evidence["original_inventory_preserved"])

    def test_both_outside_is_not_enough_to_classify_a_plane(self):
        after = copy.deepcopy(self.after)
        after["graph"]["segments"][1]["prefab"].update(ai="TrainTrackAI", native_plane=False)
        with self.assertRaisesRegex(ValueError, "non-native-plane"):
            graph_evidence(self.before, after)

    def test_original_lane_ids_cannot_change(self):
        after = copy.deepcopy(self.after)
        after["graph"]["segments"][0]["lane_ids"] = [999]
        with self.assertRaisesRegex(ValueError, "original segment"):
            graph_evidence(self.before, after)

    def test_air_requires_real_lanes_outside_buildings_and_counts(self):
        for change in ["lane", "building", "count"]:
            after = copy.deepcopy(self.after)
            if change == "lane":
                after["graph"]["segments"][1]["lane_ids"] = []
            if change == "building":
                after["graph"]["nodes"][1]["outside_building_id"] = 0
            if change == "count":
                after["graph"]["outside_counts"]["air"]["incoming"] = 0
            with self.assertRaises(ValueError):
                graph_evidence(self.before, after)

    def test_air_cannot_join_original_graph_or_leave_disconnected_piece(self):
        after = copy.deepcopy(self.after)
        after["graph"]["segments"][1]["from"] = 4
        with self.assertRaisesRegex(ValueError, "touches the original"):
            graph_evidence(self.before, after)
        after = copy.deepcopy(self.after)
        after["graph"]["nodes"].append({"id": 199, "prefab": self.air, "outside": False, "outside_building_id": 0})
        with self.assertRaisesRegex(ValueError, "disconnected"):
            graph_evidence(self.before, after)

    def test_dry_run_never_applies_or_exports(self):
        source = self.out / "source.crp"
        source.write_bytes(b"offline fixture only")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        binding = self.binding(source, hashlib.sha256(source.read_bytes()).hexdigest())
        before = {**self.before, **binding, "state": "ready", "plane_prefabs": [{"prefab": self.plan["prefab"]}]}

        def call(op, **kw):
            if op == "template_open":
                self.assertEqual(kw["source_sha256"], digest)
                return binding
            if op == "template_status":
                return before
            return {}

        client = SimpleNamespace(call=Mock(side_effect=call), wait=Mock())
        with patch("cs1_harness.template_author.poll", return_value={**before, "state": "checked"}):
            author(client, source, self.out / "receipt", self.plan)
        operations = client.call.call_args_list
        self.assertNotIn("template_export", [c.args[0] for c in operations])
        self.assertEqual([c.kwargs["apply"] for c in operations if c.args[0] == "template_air"], [False])

    def test_failure_is_terminal_not_a_silent_retry(self):
        client = SimpleNamespace(call=Mock(return_value={"state": "failed_discard_editor", "error": "collision"}))
        with self.assertRaisesRegex(HarnessError, "discard editor"):
            poll(client, lambda st: False, 1)
        self.assertEqual(client.call.call_count, 1)

    def test_apply_requires_explicit_plan_and_new_output_name(self):
        with self.assertRaisesRegex(ValueError, "apply requires"):
            author(None, None, self.out, self.plan, apply=True)

    def test_invalid_export_name_fails_before_any_native_call(self):
        with self.assertRaisesRegex(ValueError, "safe new"):
            author(None, None, self.out, self.plan, apply=True, export_name="../overwrite", map_name="fixture")

    def test_export_receipt_binds_actual_file_and_native_inventory(self):
        source = self.out / "source.crp"
        source.write_bytes(b"source fixture")
        exported = self.out / "air-template-fixture.crp"
        exported.write_bytes(b"export fixture only, not native CRP")
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        export_hash = hashlib.sha256(exported.read_bytes()).hexdigest()
        binding = self.binding(source, hashlib.sha256(source.read_bytes()).hexdigest())
        before = {**self.before, **binding, "state": "ready", "plane_prefabs": [{"prefab": self.plan["prefab"]}]}
        saved = {**self.after, **binding, "state": "export_requested", "saving": False, "export_sha256": export_hash}

        def call(op, **kw):
            if op == "template_open":
                self.assertEqual(kw["source_sha256"], source_hash)
                return binding
            if op == "template_status":
                return before
            if op == "template_export":
                return {"path": str(exported)}
            return {}

        client = SimpleNamespace(call=Mock(side_effect=call), wait=Mock())
        with patch("cs1_harness.template_author.poll", side_effect=[before, self.after, self.after, saved]):
            receipt = author(
                client,
                source,
                self.out / "result",
                self.plan,
                apply=True,
                export_name="air-template-fixture",
                map_name="offline fixture",
            )
        self.assertEqual(receipt["export_sha256"], export_hash)
        self.assertEqual(receipt["native_graph"]["new_segments"][0]["id"], 600)
        self.assertFalse(receipt["writer_adopted"])
        self.assertEqual(
            [c.kwargs["apply"] for c in client.call.call_args_list if c.args[0] == "template_air"], [False, True]
        )


if __name__ == "__main__":
    unittest.main()
