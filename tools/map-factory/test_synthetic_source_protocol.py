import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from closed_storage_candidate import sha
from synthetic_source_protocol import FILES, review_gate, study_rows


class ProspectiveProtocolTests(unittest.TestCase):
    def test_review_is_for_exact_protocol_and_both_source_builds(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "protocol.json").write_text("prospective immutable bytes")
            plan = {
                "recipe_commit": "recipe",
                "harness_source": "runtime",
                "mod_sha256": "build",
            }
            receipt = {
                **plan,
                "status": "pass",
                "review_issue": "independent-review",
                "protocol_sha256": sha(root / "protocol.json"),
            }
            path = root / "review.json"
            path.write_text(json.dumps(receipt))
            review_gate(root, plan, path)
            receipt["mod_sha256"] = "different-build"
            path.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, "different bytes"):
                review_gate(root, plan, path)

    def test_raw_snapshot_rejects_missing_points_controls_and_grid_corruption(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "grids").mkdir()
            points = [{"name": "branch", "x": 16, "z": 0}]
            source = {
                "type": 1,
                "target_fixed": 6400,
                "intake_rate": 128,
                "output_rate": 32,
                "position": [16, 98, 0],
            }
            row = {
                "kind": "water_study_snapshot",
                "schema": "polli.water-study-snapshot/1",
                "sequence": 0,
                "prefix": "ws000000",
                "samples": points,
                "cells": 1081**2,
                "depth_sum_q": 0,
                "wet_nodes": 0,
                "sources": [
                    {
                        "id": 1,
                        "type": 1,
                        "target_fixed": 6400,
                        "input_rate": 128,
                        "output_rate": 32,
                        "input_position": [16, 98, 0],
                        "output_position": [16, 98, 0],
                    }
                ],
                "files": {},
            }
            for file in FILES:
                path = root / "grids" / f"ws000000-{file}.u16"
                path.write_bytes(np.zeros(1081**2, "<u2").tobytes())
                row["files"][file] = {
                    "path": str(path),
                    "bytes": path.stat().st_size,
                    "sha256": sha(path),
                }

            def save(record):
                (root / "timeline.jsonl").write_text(json.dumps(record) + "\n")

            save(row)
            study_rows(root, points, [source])
            bad = copy.deepcopy(row)
            bad["samples"] = []
            save(bad)
            with self.assertRaisesRegex(ValueError, "omitted"):
                study_rows(root, points, [source])
            bad = copy.deepcopy(row)
            bad["sources"][0]["input_rate"] = 0
            save(bad)
            with self.assertRaisesRegex(ValueError, "control table"):
                study_rows(root, points, [source])
            save(row)
            (root / "grids/ws000000-water-ground.u16").write_bytes(b"incomplete")
            with self.assertRaisesRegex(ValueError, "grid size"):
                study_rows(root, points, [source])
