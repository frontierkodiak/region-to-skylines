"""Author PL-912's versioned byte contract from held inputs and fresh receipts.

Not a test and not an acceptance operation. Historical fixtures are never edited.
Only the richer resource reference is rebuilt; shipping bytes must equal the held
native-tested package. No network capture, game launch or new candidate is made.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from freeze_fixtures import freeze
from generate import ROOT


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value_digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def author(evidence_root):
    fixtures = ROOT / "fixtures"
    historical = read(fixtures / "manifest.json")
    evaluation_path = fixtures / "minor-stream-candidate/native-evaluation.json"
    evaluation = read(evaluation_path)
    assert evaluation["status"] == "partial_not_accepted"
    assert digest(ROOT / "region.py") == evaluation["production_writer_sha256"]
    version = "pl912-stream-only-v1"
    target = fixtures / "contracts" / version
    target.mkdir(parents=True, exist_ok=True)
    sources = {
        name: digest(ROOT.parents[1] / name)
        for name in historical["cases"][0]["shipping"]["source_files_sha256"]
    }
    contract = {
        "format": 1,
        "version": version,
        "status": "partial_not_accepted",
        "scope": "Current default byte/evidence contract, NOT full native acceptance",
        "historical_manifest_sha256": digest(fixtures / "manifest.json"),
        "historical_native_qualification_sha256": digest(
            fixtures / "native-qualification.json"
        ),
        "native_evaluation_file": "minor-stream-candidate/native-evaluation.json",
        "native_evaluation_sha256": digest(evaluation_path),
        "native_tested_head": evaluation["native_tested_head"],
        "source_files_sha256": sources,
        "unverified": [
            "strict_disableMods_ordinary_menu",
            "macOS",
            "populated_long_term",
        ],
        "reference_scope": "Richer offline resource reference; not the exact native-tested shipping CRP",
        "shipping_scope": "Exact shipping CRP from the fresh 022d795 native evaluation",
        "cases": [],
    }
    with tempfile.TemporaryDirectory(
        prefix="partial-contract-", dir=evidence_root
    ) as tmp:
        temporary = Path(tmp)
        flat = temporary / "inputs"
        flat.mkdir()
        for old in historical["cases"]:
            slug = old["slug"]
            source = fixtures / slug
            for name, expected in old["files_sha256"].items():
                assert digest(source / name) == expected, (
                    slug,
                    name,
                    "historical input/output changed",
                )
            shutil.copyfile(source / "input.png", flat / f"{slug}.png")
            for name in ["geometry.json", "banks.f32"]:
                (flat / f"{slug}-{name}").write_bytes(
                    gzip.decompress((source / (name + ".gz")).read_bytes())
                )
            if (source / "landmarks.json").exists():
                shutil.copyfile(
                    source / "landmarks.json", flat / f"{slug}-landmarks.json"
                )
        output = temporary / "reference"
        freeze(flat, output, resource_inputs=fixtures)
        for reference in read(output / "manifest.json")["cases"]:
            slug = reference["slug"]
            old = next(c for c in historical["cases"] if c["slug"] == slug)
            measured = next(c for c in evaluation["cases"] if c["slug"] == slug)
            prepared = evidence_root / "fallback/inputs" / slug
            run = evidence_root / "qualification-frozen" / slug
            report, verdict = read(run / "report.json"), read(run / "verdict.json")
            assert report["harness"] == {
                "commit": evaluation["native_tested_head"],
                "dirty": False,
            }
            for name in [
                "report.json",
                "verdict.json",
                "session-receipt.json",
                "audit-common.json",
            ]:
                assert digest(run / name) == measured["receipt_sha256"][name]
            assert report["game_minutes"] >= 60 and not any(
                report["session"]["cleanup"].values()
            )
            assert all(measured["initial_audits"].values())
            generation = read(prepared / "generation.json")
            package = generation["package"]
            assert (
                package["sha256"]
                == verdict["map_sha256"]
                == digest(prepared / f"PL857-{slug}.crp")
            )
            hydro = read(prepared / "hydrology.json")
            native = {
                "native_crp_sha256": package["sha256"],
                "prepared_sha256": {},
                "water_sources_sha256": value_digest(hydro["sources"]),
                "node_positions_sha256": value_digest(hydro["node_positions"]),
                "start_tile": hydro["start_tile"],
                "sea_level_m": hydro["sea_level_m"],
                "template_sha256": sources[
                    "tools/map-factory/templates/native-corridors.crp"
                ],
                "layout_sha256": sources[
                    "tools/map-factory/templates/native-corridors.json"
                ],
                "harness_commit": evaluation["native_tested_head"],
                "game_minutes": report["game_minutes"],
                "verdict": verdict["verdict"],
                "failed_checks": verdict["failed"],
                "receipt_sha256": measured["receipt_sha256"],
                "strict_vanilla_verified": False,
            }
            for name in ["terrain.u16", "water.u16"]:
                actual = digest(run / "grids" / (report["first_dump"] + "-" + name))
                assert (
                    actual
                    == digest(prepared / name)
                    == reference["prepared_sha256"][name]
                )
                native["prepared_sha256"][name] = actual
            ref_hydro = json.loads(
                gzip.decompress((output / slug / "hydrology.json.gz").read_bytes())
            )
            for field in ["sources", "node_positions", "start_tile", "sea_level_m"]:
                assert ref_hydro[field] == hydro[field], (slug, field)
            files = dict(old["files_sha256"])
            overrides = {}
            for name, sha in reference["files_sha256"].items():
                files[name] = sha
                if sha != old["files_sha256"].get(name):
                    dest = target / slug / name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(output / slug / name, dest)
                    overrides[name] = str(dest.relative_to(fixtures))
            shipping = dict(old["shipping"])
            shipping["historical_capture_source_commit"] = shipping.pop("source_commit")
            shipping["writer_source_commit"] = evaluation["native_tested_head"]
            shipping.update(
                expected_crp_sha256=package["sha256"],
                expected_crp_bytes=package["bytes"],
                expected_simulation_sha256=package["simulation_sha256"],
                source_files_sha256=sources,
            )
            contract["cases"].append(
                {
                    "slug": slug,
                    "reference": {
                        k: reference[k]
                        for k in [
                            "expected_crp_sha256",
                            "expected_crp_bytes",
                            "expected_simulation_sha256",
                            "preview_assets",
                            "prepared_sha256",
                            "resource_plan",
                            "resource_knobs",
                        ]
                    },
                    "shipping": shipping,
                    "files_sha256": files,
                    "fixture_files": overrides,
                    "native": native,
                }
            )
    (fixtures / "current.json").write_text(json.dumps(contract, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_root", type=Path)
    author(parser.parse_args().evidence_root)
