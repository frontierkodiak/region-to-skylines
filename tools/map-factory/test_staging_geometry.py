"""Acceptance reference bytes must remain bound to the selected generation."""

import hashlib
import json
import os
import shutil
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from soak import prepared_geometry, stage_prepared


class StagingGeometryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "inputs" / "fixture"
        self.source.mkdir(parents=True)
        self.raw = b'{"sq": {}, "rivers": [], "streams": []}\n'
        (self.source / "geometry.json").write_bytes(self.raw)
        self.sha = hashlib.sha256(self.raw).hexdigest()

    def test_valid_resource_binding_returns_exact_bytes(self):
        raw, binding = prepared_geometry(
            self.source, {"resources": {"prepared_geometry_sha256": self.sha}}
        )
        self.assertEqual(raw, self.raw)
        self.assertEqual(binding["sha256"], self.sha)
        self.assertEqual(
            binding["generation_fields"], ["resources.prepared_geometry_sha256"]
        )

    def test_corrupt_geometry_fails_before_package_reference_or_native_calls(self):
        generation = {"resources": {"prepared_geometry_sha256": self.sha}}
        (self.source / "generation.json").write_text(json.dumps(generation))
        (self.source / "geometry.json").write_text(
            '{"lakes": [{"rings": [[[-180,-85],[180,-85],[180,85],[-180,85]]]}]}'
        )
        with (
            patch("soak.write_map") as writer,
            patch("soak.mapped_water_reference") as mask,
            patch("soak.subprocess.run") as native,
        ):
            with self.assertRaisesRegex(ValueError, "geometry changed"):
                stage_prepared(self.root / "inputs", self.root / "stage", ["fixture"])
            writer.assert_not_called()
            mask.assert_not_called()
            native.assert_not_called()
        self.assertFalse((self.root / "stage").exists())

    def test_missing_binding_cannot_be_bypassed_by_removing_resource_metadata(self):
        for generation in [
            {"resources": {}},
            {"resource_plan": {"file": "plan.npz"}},
            {"resources": {"prepared_geometry_sha256": "bad"}},
        ]:
            with (
                self.subTest(generation=generation),
                self.assertRaisesRegex(ValueError, "geometry binding"),
            ):
                prepared_geometry(self.source, generation)
        (self.source / "plan.npz").write_bytes(b"plan marker")
        with self.assertRaisesRegex(ValueError, "geometry binding"):
            prepared_geometry(self.source, {})

    def test_missing_bound_geometry_fails(self):
        (self.source / "geometry.json").unlink()
        with self.assertRaises(FileNotFoundError):
            prepared_geometry(
                self.source, {"resources": {"prepared_geometry_sha256": self.sha}}
            )

    @unittest.skipUnless(
        os.environ.get("MAP_FACTORY_PREPARED_CASE"),
        "set an exact resource candidate for integration proof",
    )
    def test_exact_candidate_corruption_changes_no_other_bytes_and_fails_before_staging(
        self,
    ):
        actual = Path(os.environ["MAP_FACTORY_PREPARED_CASE"])
        copied = self.root / "actual-inputs" / "case"
        shutil.copytree(actual, copied)
        before = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in copied.iterdir()
            if p.is_file()
        }
        geometry = json.loads((copied / "geometry.json").read_text())
        geometry.setdefault("lakes", []).append(
            {
                "name": "corrupt reference",
                "rings": [
                    [[-180, -85], [180, -85], [180, 85], [-180, 85], [-180, -85]]
                ],
            }
        )
        (copied / "geometry.json").write_text(json.dumps(geometry))
        changed = [
            p.name
            for p in copied.iterdir()
            if p.is_file()
            and hashlib.sha256(p.read_bytes()).hexdigest() != before[p.name]
        ]
        self.assertEqual(changed, ["geometry.json"])
        with patch("soak.write_map") as writer, patch("soak.subprocess.run") as native:
            with self.assertRaisesRegex(ValueError, "geometry changed"):
                stage_prepared(copied.parent, self.root / "actual-stage", ["case"])
            writer.assert_not_called()
            native.assert_not_called()
        self.assertFalse((self.root / "actual-stage").exists())

    def test_legacy_unpainted_optional_geometry_preserved_and_declared_hash_enforced(
        self,
    ):
        raw, binding = prepared_geometry(self.source, {"resources": None})
        self.assertEqual(raw, self.raw)
        self.assertEqual(binding["generation_fields"], [])
        declared = {"source": {"inputs_sha256": {"geometry.json": self.sha}}}
        self.assertEqual(prepared_geometry(self.source, declared)[0], self.raw)
        (self.source / "geometry.json").write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError, "geometry changed"):
            prepared_geometry(self.source, declared)
        (self.source / "geometry.json").unlink()
        self.assertEqual(prepared_geometry(self.source, {}), (None, None))


if __name__ == "__main__":
    unittest.main()
