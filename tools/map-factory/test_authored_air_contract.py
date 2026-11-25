"""A new Air byte reference cannot silently reuse old qualification."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
from authored_air_contract import ROOT, PREFIX, PREDECESSOR, load, sha
from crp import read_package, write_package
from freeze_authored_air import compare
from plane_entries import ensure_plane_entries
from network_writer import section_start

FIXTURES = ROOT / "tools/map-factory/fixtures"


class AuthoredAirContract(unittest.TestCase):
    def test_live_writer_and_archived_reader_have_distinct_bound_identities(self):
        previous, reader = load(FIXTURES)
        self.assertEqual(previous["version"], "pl1072-sea-neighbours-v1")
        self.assertNotEqual(reader("mapgen.js"), (ROOT / "mapgen.js").read_bytes())
        self.assertEqual(
            sha(reader("mapgen.js")), previous["source_files_sha256"]["mapgen.js"]
        )

    def test_old_writer_cannot_satisfy_current_source_identity(self):
        with self.assertRaisesRegex(AssertionError, "current contract source changed"):
            load(
                FIXTURES,
                lambda name: b"old source"
                if name == "mapgen.js"
                else (ROOT / name).read_bytes(),
            )

    def test_package_proof_cannot_grant_native_qualification_or_erase_cases(self):
        for mutation in ("native", "missing_case", "changed_water"):
            with (
                self.subTest(mutation=mutation),
                tempfile.TemporaryDirectory() as temporary,
            ):
                folder = Path(temporary)
                for prefix in (
                    PREFIX,
                    "contracts/pl1072-sea-neighbours-v1",
                    "contracts/pl1119-capability-ui-v1/baseline",
                ):
                    shutil.copytree(FIXTURES / prefix, folder / prefix)
                current = json.loads((folder / PREFIX / "current.json").read_bytes())
                proof = json.loads((folder / PREFIX / "proof.json").read_bytes())
                if mutation == "native":
                    proof["native_tested"] = True
                if mutation == "missing_case":
                    current["cases"].pop()
                    proof["cases"] = proof["cases"][:-2]
                if mutation == "changed_water":
                    proof["cases"][0]["prepared_sha256"]["water.u16"] = "0" * 64
                raw = json.dumps(proof).encode()
                (folder / PREFIX / "proof.json").write_bytes(raw)
                current["proof"]["sha256"] = sha(raw)
                (folder / PREFIX / "current.json").write_text(json.dumps(current))
                with self.assertRaises(AssertionError):
                    load(folder)

    def test_predecessor_is_not_relabelled_as_new_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            shutil.copytree(FIXTURES / PREFIX, folder / PREFIX)
            path = folder / PREDECESSOR
            path.parent.mkdir(parents=True)
            path.write_bytes((FIXTURES / PREDECESSOR).read_bytes() + b" ")
            with self.assertRaisesRegex(
                AssertionError, "Air predecessor contract changed"
            ):
                load(folder)

    def test_actual_plane_delta_preserves_other_managers_and_rejects_a_water_edit(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            path = folder / "map.crp"
            original = (
                ROOT / "tools/map-factory/templates/native-corridors.crp"
            ).read_bytes()
            path.write_bytes(original)
            np.zeros((1081, 1081), dtype="<u2").tofile(folder / "terrain.u16")
            ensure_plane_entries(
                path, {"sq": {"lon": 0, "lat": 0, "scale": 1, "rotation": 0}}, folder
            )
            self.assertEqual(compare(original, path.read_bytes())["plane_entries"], 2)
            package, assets = read_package(path.read_bytes())
            simulation = next(a for a in assets if a["kind"] == 52)
            data = bytearray(simulation["payload"])
            data[section_start(data, "WaterSimulation") + 20] ^= 1
            simulation["payload"] = bytes(data)
            with self.assertRaises(AssertionError):
                compare(original, write_package(package, assets))


if __name__ == "__main__":
    unittest.main()
