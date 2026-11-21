"""Retained raw evidence tests; native inputs are opt-in, never recollected."""

import copy
import gzip
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from integrate_outside_v2 import (
    ORIGINAL,
    PREFIX,
    ROOT,
    SOURCE,
    STUDY,
    paired_controls,
    project,
    runtime_context,
    sha,
)

NATIVE = os.environ.get("OUTSIDE_V2_NATIVE_ROOT")


@unittest.skipUnless(
    NATIVE, "Set OUTSIDE_V2_NATIVE_ROOT to exact retained PR67 evidence"
)
class RetainedEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.native = Path(NATIVE).resolve()
        cls.repo = cls.native.parents[3]
        cls.rows, cls.study, cls.receipts = project(cls.native)
        evidence = json.loads((cls.native / "evidence.json").read_bytes())
        cls.observations = []
        for artifact in evidence["artifacts"]:
            for attempt in artifact["attempts"]:
                observation = json.loads(
                    gzip.decompress(
                        (
                            cls.native / attempt["observation_evidence"]["path"]
                        ).read_bytes()
                    )
                )
                if observation.get("schema") == 2 and observation.get("completed"):
                    networks = json.loads(
                        gzip.decompress(
                            (
                                cls.native
                                / attempt["native_evidence"]["networks.json"]["path"]
                            ).read_bytes()
                        )
                    )
                    cls.observations.append(
                        (observation, {s["id"]: s for s in networks["segments"]})
                    )

    def test_deterministic_import_and_original_history(self):
        self.assertEqual((self.rows, self.study, self.receipts), project(self.native))
        ledger = json.loads((ROOT / "capabilities.json").read_bytes())
        self.assertEqual(self.study, ledger["evidence_studies"][STUDY])
        self.assertEqual(
            (1269, 143, 17, 5, 619, 98),
            tuple(
                self.study[k] if isinstance(self.study[k], int) else len(self.study[k])
                for k in (
                    "native_rows_retained_upstream",
                    "projection_raw_files_checked",
                    "attempts",
                    "runtime_bound_observations",
                    "original_rows_fields_preserved",
                    "original_raw_files_preserved",
                )
            ),
        )
        base = json.loads(
            subprocess.check_output(
                ["git", "show", "d7716fb:capabilities.json"], cwd=ROOT
            )
        )
        self.assertEqual(
            base["evidence_studies"]["outside-v1"],
            ledger["evidence_studies"]["outside-v1"],
        )
        for cap in ledger["capabilities"]:
            before = next(c for c in base["capabilities"] if c["id"] == cap["id"])
            self.assertEqual(
                before["game_agreement"],
                [r for r in cap["game_agreement"] if r.get("study") != STUDY],
            )
        for file, raw in self.receipts.items():
            self.assertEqual((ROOT / file).read_bytes(), raw)
        self.assertEqual(ledger["native_path_certificates"], [])
        self.assertEqual(
            ledger["evidence_studies"]["outside-v1"]["source_commit"], ORIGINAL
        )

    def test_distinct_edges_and_unknown_failures(self):
        self.assertEqual(
            {k: sum(r["observed"] is True for r in v) for k, v in self.rows.items()},
            {"road": 2, "rail": 0, "ship": 4, "air": 0},
        )
        road = [
            len(r["successful_requests"])
            for r in self.rows["road"]
            if r["observed"] is True
        ]
        self.assertEqual(sorted(road), [7, 51])
        self.assertTrue(all(r["observed"] is None for r in self.rows["rail"]))
        self.assertEqual(len(self.study["qualification_candidates"]), 4)
        self.assertTrue(
            all(
                c["blocked_by"] == ["independent_review_pending"]
                for c in self.study["qualification_candidates"]
            )
        )

    def test_control_mutations_cannot_qualify(self):
        for observation, segments in self.observations:
            paths = [
                p for p in observation["paths"] if p["request"]["capability"] == "ship"
            ]
            if not paths:
                continue
            self.assertTrue(all(paired_controls(paths, segments)[0].values()))
            mutations = [
                lambda ps: ps.pop(),
                lambda ps: ps[0]["request"]["from"].__setitem__(2, 128),
                lambda ps: ps[0]["result"]["positions"][0].__setitem__(2, 128),
                lambda ps: ps[0]["result"].__setitem__("released", False),
                lambda ps: ps[0]["request"].__setitem__("direction", 1),
                lambda ps: ps[0]["request"].__setitem__("pair_index", 999),
                lambda ps: ps[0]["request"].__setitem__(
                    "to", ps[0]["request"]["from"][:]
                ),
            ]
            for mutate in mutations:
                changed = copy.deepcopy(paths)
                mutate(changed)
                self.assertFalse(all(paired_controls(changed, segments)[0].values()))

    def test_runtime_context_mutations_rejected(self):
        def source(name):
            return sha((self.repo / "tools/cs1-harness/mod" / name).read_bytes())

        for original, _ in self.observations:
            runtime_context(original, source)
            mutations = [
                lambda o: o["launch_runtime_identity"].__setitem__("namespace_pid", 1),
                lambda o: o["launch_runtime_identity"].__setitem__(
                    "process_start_ticks", "1"
                ),
                lambda o: o["runtime_identity"]["executable"].__setitem__(
                    "sha256", "0" * 64
                ),
                lambda o: o["runtime_identity"]["assemblies"][1].__setitem__(
                    "sha256", "0" * 64
                ),
                lambda o: o["runtime_identity"]["unresolved_loaded_assemblies"].append(
                    "unknown"
                ),
                lambda o: o["loaded"].__setitem__("invert_traffic", "True"),
                lambda o: o["new_game_protocol"].__setitem__("update_mode", "LoadGame"),
                lambda o: o["new_game_protocol"].__setitem__("loading", "/another.crp"),
                lambda o: o["session"]["cleanup"]["game"].append(1),
                lambda o: o["session"]["game_gpu"][0].__setitem__("pid", 1),
                lambda o: o["session"].__setitem__("mod_sha256", "0" * 64),
                lambda o: o["build_receipt"]["sources"].__setitem__(
                    "CoreOps.cs", "0" * 64
                ),
            ]
            for mutate in mutations:
                changed = copy.deepcopy(original)
                mutate(changed)
                with self.assertRaises(ValueError):
                    runtime_context(changed, source)

    def test_changed_source_selection_and_raw_bytes_rejected(self):
        # Mutate an owned worktree, never a producer's evidence.
        with tempfile.TemporaryDirectory() as directory:
            owned = Path(directory) / "native"
            subprocess.run(
                ["git", "worktree", "add", "--detach", str(owned), SOURCE],
                cwd=self.repo,
                check=True,
                capture_output=True,
            )
            try:
                root = owned / PREFIX
                targets = [
                    root / "selection.json",
                    root / "raw/boston/native-v2-4/observation.json.gz",
                    owned / "tools/cs1-harness/mod/CoreOps.cs",
                ]
                for target in targets:
                    before = target.read_bytes()
                    try:
                        target.write_bytes(before + b"changed")
                        with self.assertRaises(subprocess.CalledProcessError):
                            project(root)
                    finally:
                        target.write_bytes(before)
                subprocess.run(
                    ["git", "checkout", "--detach", ORIGINAL],
                    cwd=owned,
                    check=True,
                    capture_output=True,
                )
                with self.assertRaisesRegex(ValueError, "Wrong exact native source"):
                    project(root)
            finally:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(owned)],
                    cwd=self.repo,
                    check=True,
                    capture_output=True,
                )


if __name__ == "__main__":
    unittest.main()
