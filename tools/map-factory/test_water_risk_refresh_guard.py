"""A preparation refresh must not mutate history after another contract lands."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import refresh_water_risk


class RefreshBoundary(unittest.TestCase):
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
