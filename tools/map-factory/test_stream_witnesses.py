import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from natural_storage_candidate import write
from stream_construction import assess, greatest_profile, sha
from stream_witnesses import (
    bound_witnesses,
    contact_relation,
    foreign_contacts,
    infrastructure_contacts,
    infrastructure_sources,
    members_for,
    preflight,
    raw_distance,
    stage,
    trace_bounds,
)
from test_maintained_water_inventory import coord, line
import test_stream_construction as stream_fixture
from test_stream_construction import fixture
from waterway_pieces import catalog


class BoundWitnessTests(unittest.TestCase):
    def test_paths_certify_frozen_solver_and_distinguish_propagation(self):
        lower, upper, edges = [0, 7, 6], [3, 10, 4], [(0, 1), (1, 2)]
        result = trace_bounds(lower, upper, edges)
        self.assertEqual([w["path"] for w in result], [[0, 1], [0, 1, 2]])
        self.assertEqual(
            [w["local_bounds_already_conflict"] for w in result], [False, True]
        )
        rng = np.random.default_rng(8)
        for _ in range(40):
            lo, hi = rng.integers(0, 20, (2, 8))
            es = [
                (a, b) for a in range(8) for b in range(a + 1, 8) if rng.random() < 0.3
            ]
            expected = greatest_profile(lo, hi, es)
            traced = trace_bounds(lo, hi, es)
            self.assertEqual(
                [
                    {k: w[k] for k in ("node", "lower_q", "greatest_possible_q")}
                    for w in traced
                ],
                expected.get("witnesses", []),
            )
            for witness in traced:
                path = witness["path"]
                self.assertTrue(all((a, b) in es for a, b in zip(path, path[1:])))
                self.assertEqual(hi[path[0]], witness["greatest_possible_q"])
                self.assertLess(witness["greatest_possible_q"], lo[path[-1]])

    def test_cycles_have_no_bound_certificate(self):
        with self.assertRaisesRegex(ValueError, "cycle"):
            trace_bounds([0, 0], [3, 3], [(0, 1), (1, 0)])

    def test_real_bank_and_branch_membership_are_checkable(self):
        g, h, f, w, layout = fixture()
        f[540, 542] = 7000
        pieces, plan = assess(g, h, f, w, layout)
        clips = {c["id"]: c for row in pieces["rows"] for c in row["clips"]}
        component = plan["components"][0]
        members = members_for(component, clips)
        result = bound_witnesses(component, members, clips, f, w)
        self.assertGreater(result["summary"]["violating_nodes"], 0)
        own = set(members)
        for witness in result["witnesses"]:
            ancestor = tuple(witness["ancestor_evidence"]["node_rc"])
            for bank in witness["limiting_untouched_banks"]:
                node = tuple(bank["node_rc"])
                self.assertNotIn(node, own)
                self.assertEqual(max(abs(node[i] - ancestor[i]) for i in (0, 1)), 1)
                self.assertEqual(f[node] - 32, witness["greatest_possible_q"])
            self.assertTrue(all(witness["path_source_clips"]))


class ContactWitnessTests(unittest.TestCase):
    def test_foreign_underground_clip_at_exact_fixed_buffer(self):
        g, h, f, w, layout = fixture()
        g["streams"].append(line((0, -144), (64, -144), brunnel="tunnel"))
        pieces, plan = assess(g, h, f, w, layout)
        rows = {row["id"]: row for row in pieces["rows"]}
        clips = {c["id"]: c for row in rows.values() for c in row["clips"]}
        component = plan["components"][0]
        result = foreign_contacts(component, members_for(component, clips), rows, clips)
        contact = result["contacts"][0]
        self.assertEqual(contact["clip_id"], "streams:2:clip:0")
        self.assertEqual(contact["relation"]["scope_reason"], "explicit underground")
        self.assertEqual(contact["buffer_m"], 128)
        self.assertTrue(
            all(w["native_distance_m"] == 128 for w in contact["witnesses"])
        )
        self.assertTrue(
            all(w["role"] == "untouched_bank" for w in contact["witnesses"])
        )
        self.assertEqual(component["status"], "refused_or_unresolved")

    def test_own_fragment_is_not_declared_different_hydraulic_waterway(self):
        g, *_ = fixture()
        g["streams"] = [
            {
                "pts": [
                    coord(*p)
                    for p in [
                        (-9000, 0),
                        (0, 0),
                        (9000, 0),
                        (9000, 400),
                        (0, 400),
                        (-9000, 400),
                    ]
                ]
            }
        ]
        rows = {r["id"]: r for r in catalog(g)["rows"]}
        clips = {c["id"]: c for r in rows.values() for c in r["clips"]}
        relation = contact_relation(
            ["streams:0:clip:0"], clips["streams:0:clip:1"], rows, clips
        )
        self.assertEqual(
            relation["source_row_relation"], "same_captured_row_other_clipped_part"
        )
        self.assertEqual(
            relation["junction"], "buffer_proximity_only_hydraulic_relation_unknown"
        )

    def test_raster_landing_control_corridor_sources_match_frozen_union(self):
        g, h, f, w, layout = fixture()
        g["rivers"].append(line((0, 100), (64, 100)))
        h["start_area"]["landing"] = [0, 0]
        h["sources"] = [
            {"position": [0, 0, 0], "capacity": 0.01, "output_capacity": 0.02}
        ]
        h["node_positions"] = {"1": [0, 0, 0], "2": [64, 0, 0]}
        layout = {"routes": [{"nodes": [1, 2]}]}
        pieces, plan = assess(g, h, f, w, layout)
        clips = {c["id"]: c for row in pieces["rows"] for c in row["clips"]}
        component = plan["components"][0]
        result = infrastructure_contacts(
            component,
            members_for(component, clips),
            infrastructure_sources(g, h, layout),
        )
        self.assertEqual(
            {c["id"] for c in result["contacts"]},
            {
                "rivers:0",
                "start_area:landing",
                "hydrology:sources:0",
                "layout:routes:0",
            },
        )
        broken = copy.deepcopy(component)
        broken["guards"]["infrastructure_or_other_water_hits"] -= 1
        with self.assertRaisesRegex(ValueError, "union"):
            infrastructure_contacts(
                broken,
                members_for(component, clips),
                infrastructure_sources(g, h, layout),
            )

    def test_raw_distance_is_not_reinterpreted_as_native_mask(self):
        self.assertEqual(raw_distance(np.array([1, 3]), [[0, 0], [4, 0]]), 3)
        self.assertEqual(raw_distance(np.array([1, 3]), [[1, 0], [1, 0]]), 3)


class WitnessProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stream_fixture.StreamProtocolTests.setUpClass()
        cls.addClassCleanup(stream_fixture.StreamProtocolTests.temp.cleanup)
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.output = Path(cls.temp.name) / "witness"
        stage(stream_fixture.StreamProtocolTests.output, cls.output)

    def test_complete_frozen_protocol_is_retained_without_native_plan(self):
        preflight(self.output)
        result = json.loads((self.output / "witnesses.json").read_text())
        self.assertIsNone(result["physical_package"])
        self.assertEqual(result["stable_water_promise"], "unknown")
        self.assertFalse((self.output / "native-plan.json").exists())
        self.assertEqual(
            sha(self.output / "source/probes.json"),
            sha(stream_fixture.StreamProtocolTests.output / "probes.json"),
        )

    def test_coherent_contact_omission_and_dependency_omission_rejected(self):
        path, fp = self.output / "witnesses.json", self.output / "freeze.json"
        saved, frozen = path.read_bytes(), fp.read_bytes()
        try:
            result = json.loads(saved)
            result["components"].pop()
            write(path, result)
            freeze = json.loads(frozen)
            freeze["files_sha256"]["witnesses.json"] = sha(path)
            write(fp, freeze)
            with self.assertRaisesRegex(ValueError, "does not replay"):
                preflight(self.output)
            path.write_bytes(saved)
            freeze = json.loads(frozen)
            del freeze["source_files_sha256"]["stream_witnesses.py"]
            write(fp, freeze)
            with self.assertRaisesRegex(ValueError, "closure"):
                preflight(self.output)
        finally:
            path.write_bytes(saved)
            fp.write_bytes(frozen)
