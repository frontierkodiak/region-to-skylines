"""The rail adapter must reject changed bytes, sources, freezes, context or coverage."""

import gzip
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import integrate_rail_evidence as rail

EVIDENCE = "tools/map-factory/capability-evidence"
FROZEN = f"{EVIDENCE}/rail-native-sources"


def copy_file(source, target):
    (target).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def copy_evidence(target):
    for name in (
        "rail-v1",
        "rail-v2",
        "rail-v3",
        "rail-v3-followup-1",
        "rail-native-sources",
    ):
        shutil.copytree(rail.ROOT / EVIDENCE / name, target / EVIDENCE / name)
    copy_file(rail.ROOT / rail.PREDICTIONS, target / rail.PREDICTIONS)
    copy_file(rail.ROOT / rail.PROJECTION_TOOL, target / rail.PROJECTION_TOOL)
    copy_file(rail.ROOT / rail.BASEMAPS, target / rail.BASEMAPS)
    copy_file(rail.ROOT / "capabilities.json", target / "capabilities.json")


class RailImportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pristine = Path(tempfile.mkdtemp(prefix="rail-pristine-"))
        copy_evidence(cls.pristine)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.pristine, ignore_errors=True)

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="rail-mutation-"))
        shutil.copytree(self.pristine, self.root, dirs_exist_ok=True)
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.original_root = rail.ROOT
        rail.ROOT = self.root
        self.addCleanup(setattr, rail, "ROOT", self.original_root)

    # -- helpers -----------------------------------------------------------------

    def evidence(self, *parts):
        return self.root / EVIDENCE / Path(*parts)

    def restore(self, relative):
        shutil.copy2(self.pristine / relative, self.root / relative)

    def plain(self, section, relative):
        return json.loads(
            gzip.decompress((self.evidence(section, relative + ".gz")).read_bytes())
        )

    def put(self, section, relative, value):
        """Rewrite one archived receipt and its own manifest record consistently."""
        path = self.evidence(section, relative + ".gz")
        payload = rail.encoded(value)
        path.write_bytes(gzip.compress(payload, mtime=0))
        manifest_path = self.evidence(section, "integrity.json")
        manifest = json.loads(manifest_path.read_text())
        for record in manifest["files"]:
            if record["path"] == relative:
                record["bytes"] = len(payload)
                record["sha256"] = rail.sha(payload)
                record["gzip_sha256"] = rail.sha(path.read_bytes())
                break
        else:
            raise AssertionError(f"missing manifest record {section}/{relative}")
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        audit_path = self.evidence("rail-v3-followup-1", "cleanup-audit.json")
        if audit_path.exists():
            audit = json.loads(audit_path.read_text())
            audit["initial_integrity_sha256"] = rail.digest(
                self.evidence("rail-v3", "integrity.json")
            )
            audit["followup_integrity_sha256"] = rail.digest(
                self.evidence("rail-v3-followup-1", "integrity.json")
            )
            self.put_audit(audit)
        return rail.sha(payload)

    def rebind_freeze(self, section, relative, digest_value):
        observation = self.plain(section, relative + "/observation.json")
        observation["query_freeze_sha256"] = digest_value
        self.put(section, relative + "/observation.json", observation)

    def audit(self):
        return json.loads(
            (self.evidence("rail-v3-followup-1", "cleanup-audit.json")).read_text()
        )

    def put_audit(self, value):
        (self.evidence("rail-v3-followup-1", "cleanup-audit.json")).write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n"
        )

    # -- the accepted artifact ---------------------------------------------------

    def test_import_is_deterministic_and_matches_the_ledger(self):
        first = rail.build_study()
        second = rail.build_study()
        self.assertEqual(first, second)
        self.assertEqual(first["totals"]["selected_boundary"], 244)
        self.assertEqual(first["totals"]["distinct_edge_successes"], 9)
        self.assertEqual(first["totals"]["same_edge_successes"], 2)
        self.assertEqual(first["totals"]["selected_failures"], 233)
        self.assertEqual(first["totals"]["unqueried_boundary_candidates"], 112)
        self.assertEqual(first["raw_file_counts"]["runtime_openings"], 11)
        ledger = json.loads((self.root / "capabilities.json").read_text())
        rail.write(first)
        once = (self.root / "capabilities.json").read_bytes()
        rail.write(first)
        self.assertEqual(
            once,
            (self.root / "capabilities.json").read_bytes(),
            "write is not idempotent",
        )
        projection_sha = rail.verify_current(first)
        self.assertEqual(
            ledger["rail_studies"][rail.STUDY], rail.summary_of(first, projection_sha)
        )
        self.assertFalse(
            [c for c in ledger["native_path_certificates"] if c["capability"] == "rail"]
        )
        self.assertEqual(
            [c["capability"] for c in ledger["native_path_certificates"]], ["ship"] * 4
        )
        self.assertEqual(first["cleanup"]["degraded"], True)
        self.assertEqual(
            first["cleanup"]["findings"][0]["raw_cleanup"]["steam_instances"],
            ["3933505219"],
        )

    def test_source_closure_and_stock_rule_are_strict(self):
        frozen = self.root / FROZEN
        source = frozen / "cs1_harness/rail_study.py"
        source.write_bytes(source.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "archived native source differs"):
            rail.build_study()
        source.write_bytes(
            (self.pristine / FROZEN / "cs1_harness/rail_study.py").read_bytes()
        )
        mod = frozen / "mod/NetworkOps.cs"
        mod.write_bytes(mod.read_bytes() + b"\n")
        with self.assertRaisesRegex(
            ValueError, "archived (native|build) source differs"
        ):
            rail.build_study()
        selection = json.loads(self.evidence("rail-v3/selection.json").read_text())
        selection["controls"][0]["file"] = "AP Noyou Port.crp"
        self.evidence("rail-v3/selection.json").write_text(
            json.dumps(selection, indent=2, sort_keys=True) + "\n"
        )
        with self.assertRaisesRegex(
            ValueError, "stock corpus selection is not reproducible"
        ):
            rail.build_study()

    def test_raw_bytes_and_manifest_are_hashed(self):
        path = self.evidence("rail-v3", "raw/stock-1/observation.json.gz")
        path.write_bytes(path.read_bytes() + b"\0")
        with self.assertRaisesRegex(ValueError, "compressed bytes changed"):
            rail.build_study()
        shutil.copy2(
            self.pristine / EVIDENCE / "rail-v3/raw/stock-1/observation.json.gz", path
        )
        manifest_path = self.evidence("rail-v3", "integrity.json")
        manifest = json.loads(manifest_path.read_text())
        for record in manifest["files"]:
            if record["path"] == "raw/stock-1/observation.json":
                record["bytes"] += 1
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        with self.assertRaisesRegex(ValueError, "decompressed length changed"):
            rail.build_study()

    def test_frozen_enumeration_and_query_order_are_bound(self):
        frozen = self.plain("rail-v3", "raw/stock-1/query-freeze.json")
        frozen["plan"]["requests"][0]["to"] = [1, 0, 0]
        digest_value = self.put("rail-v3", "raw/stock-1/query-freeze.json", frozen)
        self.rebind_freeze("rail-v3", "raw/stock-1", digest_value)
        with self.assertRaisesRegex(
            ValueError, "frozen directed enumeration is not reproducible"
        ):
            rail.build_study()

    def test_returned_endpoints_must_match_the_request(self):
        observation = self.plain("rail-v3", "raw/asheville/observation.json")
        successes = [row for row in observation["paths"] if row["result"]["success"]]
        successes[0]["result"]["positions"][-1] = [1, 0, 255]
        self.put("rail-v3", "raw/asheville/observation.json", observation)
        audit = self.audit()
        audit["observation_sha256"]["raw/asheville/observation.json"] = rail.sha(
            rail.encoded(observation)
        )
        self.put_audit(audit)
        with self.assertRaisesRegex(
            ValueError, "last returned position is not the requested destination"
        ):
            rail.build_study()

    def test_context_and_process_identity_are_bound(self):
        observation = self.plain("rail-v3", "raw/stock-2/observation.json")
        observation["runtime_identity"]["host_pid"] += 1
        self.put("rail-v3", "raw/stock-2/observation.json", observation)
        with self.assertRaises(ValueError):
            rail.build_study()

    def test_cleanup_audit_must_cover_every_game_process(self):
        audit = self.audit()
        audit["games"] = audit["games"][:-1]
        self.put_audit(audit)
        with self.assertRaisesRegex(
            ValueError, "does not cover exactly the recorded game processes"
        ):
            rail.build_study()

    def test_cleanup_audit_must_cover_every_telemetry_owner(self):
        audit = self.audit()
        audit["collector_pids"] = audit["collector_pids"][:-1]
        self.put_audit(audit)
        with self.assertRaisesRegex(ValueError, "does not cover every telemetry owner"):
            rail.build_study()

    def test_cleanup_audit_rejects_a_live_remainder(self):
        audit = self.audit()
        audit["reported_steam_remainders_still_present"] = ["3933505219"]
        self.put_audit(audit)
        with self.assertRaisesRegex(
            ValueError, "listed Steam remainder is still present"
        ):
            rail.build_study()

    def test_cleanup_audit_rejects_an_unbound_remainder(self):
        audit = self.audit()
        audit["reported_steam_remainders"] = []
        self.put_audit(audit)
        with self.assertRaisesRegex(
            ValueError, "does not name every teardown remainder"
        ):
            rail.build_study()

    def test_cleanup_audit_must_name_every_observation(self):
        audit = self.audit()
        audit["observation_sha256"].pop("raw/yosemite-attempt-1/observation.json")
        self.put_audit(audit)
        with self.assertRaisesRegex(ValueError, "omits or invents an observation"):
            rail.build_study()

    def test_cleanup_audit_must_postdate_every_exit(self):
        audit = self.audit()
        audit["observed_at"] = "2026-11-21T00:00:00+00:00"
        self.put_audit(audit)
        with self.assertRaisesRegex(ValueError, "predates an observation exit"):
            rail.build_study()

    def test_cleanup_finding_cannot_be_emptied_or_reclassified(self):
        observation = self.plain(
            "rail-v3-followup-1", "raw/pittsburgh-attempt-1/observation.json"
        )
        observation["session"]["cleanup"]["steam_instances"] = []
        self.put(
            "rail-v3-followup-1",
            "raw/pittsburgh-attempt-1/observation.json",
            observation,
        )
        audit = self.audit()
        audit["observation_sha256"]["raw/pittsburgh-attempt-1/observation.json"] = (
            rail.sha(rail.encoded(observation))
        )
        self.put_audit(audit)
        with self.assertRaisesRegex(
            ValueError, "does not name every teardown remainder"
        ):
            rail.build_study()

    def test_projection_and_ledger_must_agree(self):
        study = rail.build_study()
        rail.write(study)
        ledger = json.loads((self.root / "capabilities.json").read_text())
        ledger["rail_studies"][rail.STUDY]["totals"]["distinct_edge_successes"] = 10
        (self.root / "capabilities.json").write_text(
            json.dumps(ledger, indent=2) + "\n"
        )
        with self.assertRaisesRegex(ValueError, "stale or unbound"):
            rail.verify_current(study)
        ledger = json.loads((self.root / "capabilities.json").read_text())
        ledger["rail_studies"][rail.STUDY]["totals"]["distinct_edge_successes"] = 9
        rail_capability = next(c for c in ledger["capabilities"] if c["id"] == "rail")
        rail_capability.pop("rail_study")
        (self.root / "capabilities.json").write_text(
            json.dumps(ledger, indent=2) + "\n"
        )
        with self.assertRaisesRegex(ValueError, "does not reference"):
            rail.verify_current(study)


if __name__ == "__main__":
    unittest.main()
