"""Opt-in public-generator/staging integration using a frozen real region."""

import gzip
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from generate import generate
from soak import stage_prepared


@unittest.skipUnless(
    os.environ.get("MAP_FACTORY_DIRECT_GENERATION"),
    "set MAP_FACTORY_DIRECT_GENERATION to a resource-bearing fixture directory",
)
class DirectGenerationTests(unittest.TestCase):
    def test_resource_export_stages_and_rejects_changed_acceptance_geometry(self):
        fixtures = Path(os.environ["MAP_FACTORY_DIRECT_GENERATION"])
        case = next(
            c
            for c in json.loads((fixtures / "manifest.json").read_text())["cases"]
            if c["slug"] == "rio"
        )
        fixture = fixtures / "rio"
        raw = gzip.decompress((fixture / "geometry.json.gz").read_bytes())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            geometry = root / "caller-geometry.json"
            geometry.write_bytes(raw)
            banks = root / "banks.f32"
            banks.write_bytes(gzip.decompress((fixture / "banks.f32.gz").read_bytes()))
            exported = root / "inputs/rio"
            evidence = fixture / "evidence.json"
            result = generate(
                fixture / "input.png",
                geometry,
                exported,
                banks,
                landcover=fixture / "landcover.u8.gz",
                evidence=evidence if evidence.exists() else None,
            )
            self.assertEqual(result["package"]["sha256"], case["expected_crp_sha256"])
            self.assertEqual((exported / "geometry.json").read_bytes(), raw)
            self.assertEqual(
                result["resources"]["prepared_geometry_sha256"],
                hashlib.sha256(raw).hexdigest(),
            )
            geometry.write_text("{}")
            staged = stage_prepared(root / "inputs", root / "valid-stage", ["rio"])
            self.assertEqual(
                hashlib.sha256(staged[0][1].read_bytes()).hexdigest(),
                case["expected_crp_sha256"],
            )
            self.assertEqual(
                (root / "valid-stage/maps/rio/geometry.json").read_bytes(), raw
            )
            changed = json.loads(raw)
            changed.setdefault("lakes", []).append(
                {"rings": [[[-180, -85], [180, -85], [180, 85], [-180, -85]]]}
            )
            (exported / "geometry.json").write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "geometry changed"):
                stage_prepared(root / "inputs", root / "must-not-stage", ["rio"])
            self.assertFalse((root / "must-not-stage").exists())


if __name__ == "__main__":
    unittest.main()
