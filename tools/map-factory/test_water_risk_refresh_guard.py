"""A preparation refresh must not mutate history after another contract lands."""

import json
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import refresh_water_risk
from verify_regions import ROOT, screen_refresh_predecessor


class RefreshBoundary(unittest.TestCase):
    def test_coherent_label_flip_cannot_rewrite_original_corpus(self):
        fixtures = ROOT / "fixtures"
        active = json.loads((fixtures / "active.json").read_text())
        current = json.loads((fixtures / active["current"]).read_text())
        refresh = current["screen_refresh"]
        predecessor = json.loads(
            (fixtures / refresh["predecessor"]["file"]).read_text()
        )
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            names = {
                entry["file"] for entry in refresh.values() if isinstance(entry, dict)
            }
            names.update((current["corpus_file"], predecessor["corpus_file"]))
            for name in names:
                target = folder / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(fixtures / name, target)
            for name in (predecessor["corpus_file"], current["corpus_file"]):
                path = folder / name
                rows = json.loads(path.read_text())
                rows[0]["labels"]["flood"] = not rows[0]["labels"]["flood"]
                path.write_text(json.dumps(rows))
            corrected_digest = hashlib.sha256(
                (folder / current["corpus_file"]).read_bytes()
            ).hexdigest()
            current["corpus_sha256"] = corrected_digest
            prepared_path = folder / refresh["prepared"]["file"]
            prepared = json.loads(prepared_path.read_text())
            prepared["corpus_sha256"] = corrected_digest
            prepared_path.write_text(json.dumps(prepared))
            refresh["prepared"]["sha256"] = hashlib.sha256(
                prepared_path.read_bytes()
            ).hexdigest()
            with self.assertRaisesRegex(AssertionError, "original corpus"):
                screen_refresh_predecessor(folder, current)

    def test_superseded_contract_stops_before_any_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixtures = root / "fixtures"
            fixtures.mkdir()
            active = fixtures / "active.json"
            raw = json.dumps({"current": "contracts/new-version/current.json"})
            active.write_text(raw)
            with patch.object(refresh_water_risk, "ROOT", root):
                with self.assertRaisesRegex(ValueError, "superseded contract"):
                    refresh_water_risk.refresh(root / "native", root / "output")
            self.assertEqual(active.read_text(), raw)
            self.assertFalse((root / "output").exists())
            self.assertEqual(list(fixtures.iterdir()), [active])

    def test_changed_writer_stops_before_corpus_or_model_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            root = repo / "tools/map-factory"
            fixtures = root / "fixtures"
            contract = fixtures / "contracts/pl912-water-risk-v1/current.json"
            contract.parent.mkdir(parents=True)
            (fixtures / "active.json").write_text(
                json.dumps({"current": "contracts/pl912-water-risk-v1/current.json"})
            )
            raw = json.dumps({"source_files_sha256": {"writer.py": "0" * 64}})
            contract.write_text(raw)
            (repo / "writer.py").write_text("unchanged physical writer")
            with patch.object(refresh_water_risk, "ROOT", root):
                with self.assertRaisesRegex(
                    ValueError, "Physical writer/source changed"
                ):
                    refresh_water_risk.refresh(repo / "native", repo / "output")
            self.assertEqual(contract.read_text(), raw)
            self.assertFalse((repo / "output").exists())
            self.assertFalse((root / "water-risk-model.json").exists())


if __name__ == "__main__":
    unittest.main()
