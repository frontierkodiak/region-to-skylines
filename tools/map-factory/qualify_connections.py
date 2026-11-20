"""CPU-only real-connections exports and unchanged landed water-risk screening.

Read cohort.json frozen by capture-connections.mjs before any export. Uses frozen
shipping fixture inputs and raw fresh captures. Never invokes a game or changes a
connection default. Failed/flagged squares remain in the report, without waivers.
"""

import argparse
import gzip
import hashlib
import json
import shutil
import traceback
from pathlib import Path

import numpy as np

from real_roads import generate
from soak import panel_expectations, stage_prepared
from water_risk import assess

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def fixture_inputs(slug, folder):
    source = ROOT / "fixtures" / slug
    folder.mkdir(parents=True, exist_ok=True)
    for name, original in {
        "input.png": "input.png",
        "geometry.json": "shipping-geometry.json.gz",
        "banks.f32": "banks.f32.gz",
        "landcover.u8.gz": "landcover.u8.gz",
        "evidence.json": "shipping-evidence.json",
    }.items():
        data = (source / original).read_bytes()
        if original.endswith(".gz") and not name.endswith(".gz"):
            data = gzip.decompress(data)
        target = folder / name
        if target.exists() and target.read_bytes() != data:
            raise ValueError(f"Refusing changed cached fixture input: {target}")
        target.write_bytes(data)


def screen(folder):
    arrays = []
    for name in ["terrain.u16", "water.u16"]:
        path = folder / name
        data = np.fromfile(path, dtype="<u2") if path.is_file() else np.array([])
        arrays.append(data.reshape(1081, 1081) if data.size == 1081**2 else data)
    hydro_path = folder / "hydrology.json"
    hydro = json.loads(hydro_path.read_text()) if hydro_path.exists() else {}
    result = assess(*arrays, hydro)
    result["inputs_sha256"] = {
        name: sha(folder / name)
        for name in ["terrain.u16", "water.u16", "hydrology.json"]
        if (folder / name).is_file()
    }
    result["tool_sha256"] = {
        name: sha(ROOT / name) for name in ["water_risk.py", "water-risk-model.json"]
    }
    dump(folder / "water-risk.json", result)
    return result


def frozen_inputs(baseline, output):
    """Reuse an exact completed cohort, without selecting or fetching new inputs."""
    if baseline.resolve() == output.resolve():
        raise ValueError("Candidate output must differ from the preserved baseline")
    raw = (baseline / "cohort.json").read_bytes()
    plan = json.loads(raw)
    original_report = json.loads((baseline / "cpu-report.json").read_text())
    if original_report["selection"] != plan:
        raise ValueError("Baseline report differs from the frozen cohort")
    output.mkdir(parents=True, exist_ok=True)
    target = output / "cohort.json"
    if target.exists() and target.read_bytes() != raw:
        raise ValueError("Candidate cohort differs from frozen baseline")
    target.write_bytes(raw)
    for slug in plan["fixtures"] + [sq["slug"] for sq in plan["fresh"]]:
        source, destination = baseline / "inputs" / slug, output / "inputs" / slug
        original = original_report["cases"][slug]
        if original["status"] != "exported":
            raise ValueError(f"Baseline is not a completed export: {slug}")
        expected_inputs = original["inputs_sha256"]
        if set(p.name for p in source.iterdir()) != set(expected_inputs):
            raise ValueError(f"Frozen baseline input file set changed: {slug}")
        destination.mkdir(parents=True, exist_ok=True)
        if set(p.name for p in destination.iterdir()) - set(expected_inputs):
            raise ValueError(f"Unexpected candidate input files: {slug}")
        for path in source.iterdir():
            if not path.is_file():
                raise ValueError(f"Unexpected nested input directory: {path}")
            if sha(path) != expected_inputs[path.name]:
                raise ValueError(
                    f"Frozen baseline input bytes changed: {slug}/{path.name}"
                )
            target = destination / path.name
            if target.exists() and target.read_bytes() != path.read_bytes():
                raise ValueError(
                    f"Candidate input differs from frozen baseline: {target}"
                )
            shutil.copyfile(path, target)


def compare_export(folder, original):
    """Full package/grid/resource identities; hydrology includes new advisory metadata."""
    crp, baseline_crp = next(folder.glob("*.crp")), next(original.glob("*.crp"))
    files = {}
    for name in ["terrain.u16", "water.u16", "plan.npz"]:
        before, after = sha(original / name), sha(folder / name)
        files[name] = {
            "before_sha256": before,
            "after_sha256": after,
            "unchanged": before == after,
        }
    before, after = sha(baseline_crp), sha(crp)
    return {
        "before_crp_sha256": before,
        "after_crp_sha256": after,
        "package_unchanged": before == after,
        "files": files,
    }


def qualify(output, only=None, baseline=None):
    if baseline is not None:
        frozen_inputs(baseline, output)
    plan = json.loads((output / "cohort.json").read_text())
    slugs = plan["fixtures"] + [sq["slug"] for sq in plan["fresh"]]
    if only is not None and not set(only).issubset(slugs):
        raise ValueError("--only must be a subset of the frozen cohort")
    report_path = output / "cpu-report.json"
    report = (
        json.loads(report_path.read_text())
        if report_path.exists()
        else {
            "schema": 1,
            "scope": "Disposable CPU qualification; no native qualification or public shipping approval",
            "selection": plan,
            "cases": {},
        }
    )
    source_hashes = {
        str(path.relative_to(ROOT)): sha(path) for path in sorted(ROOT.glob("*.py"))
    }
    source_hashes["water-risk-model.json"] = sha(ROOT / "water-risk-model.json")
    for previous in report["cases"].values():
        previous.setdefault(
            "source_files_sha256", report.get("source_files_sha256", {})
        )
    report["source_files_sha256"] = source_hashes
    for slug in slugs:
        if only is not None and slug not in only:
            continue
        source, folder = output / "inputs" / slug, output / "maps" / slug
        previous = report["cases"].get(slug)
        if previous and previous["status"] == "exported":
            for name, expected in previous["water_risk"]["inputs_sha256"].items():
                if sha(folder / name) != expected:
                    raise ValueError(
                        f"Previously screened export changed: {slug}/{name}"
                    )
            package = next(folder.glob("*.crp"))
            if sha(package) != previous["generation"]["package"]["sha256"]:
                raise ValueError(f"Previously exported package changed: {slug}")
            print(f"{slug}: cached screened export retained", flush=True)
            continue
        row = {
            "slug": slug,
            "native_tested": False,
            "source_files_sha256": source_hashes,
        }
        folder.mkdir(parents=True, exist_ok=True)
        try:
            if slug in plan["fixtures"]:
                frozen_files = plan.get("frozen_input_files", {}).get(slug)
                if frozen_files is not None:
                    if not frozen_files or set(p.name for p in source.iterdir()) != set(
                        frozen_files
                    ):
                        raise ValueError(
                            f"Frozen original input file set changed: {slug}"
                        )
                    for name, expected in frozen_files.items():
                        if sha(source / name) != expected:
                            raise ValueError(
                                f"Frozen original input bytes changed: {slug}/{name}"
                            )
                else:
                    fixture_inputs(slug, source)
                row["input_kind"] = (
                    "frozen qualification input"
                    if frozen_files is not None
                    else "frozen shipping fixture"
                )
            else:
                row["input_kind"] = "fresh capture"
                capture = json.loads((source / "capture.json").read_text())
                expected_square = next(sq for sq in plan["fresh"] if sq["slug"] == slug)
                if capture["sq"] != expected_square:
                    raise ValueError(
                        f"Capture differs from frozen selected square: {slug}"
                    )
                for name, expected in capture["files_sha256"].items():
                    if sha(source / name) != expected:
                        raise ValueError(f"Captured input changed: {slug}/{name}")
            row["inputs_sha256"] = {
                p.name: sha(p) for p in source.iterdir() if p.is_file()
            }
            if any(folder.glob("*.crp")):
                raise ValueError(
                    "Export already exists; retain it and use a new output root to regenerate"
                )
            receipt = generate(
                source / "input.png",
                source / "geometry.json",
                folder,
                banks=source / "banks.f32",
                landcover=source / "landcover.u8.gz",
                evidence=source / "evidence.json"
                if (source / "evidence.json").exists()
                else None,
            )
            row["generation"] = receipt
            row["road_eligibility"] = receipt["real_roads"]["eligibility"]
            row["status"] = "exported"
        except Exception as error:
            row.update(status="failed", error=str(error))
            (folder / "cpu-error.log").write_text(traceback.format_exc())
        # Screen the final available prepared grids even after a writer failure.
        risk = screen(folder)
        row["water_risk"] = risk
        if risk["status"] == "declined":
            for crp in folder.glob("*.crp"):
                crp.unlink()
            row["status"] = "declined"
        elif row["status"] == "exported":
            try:
                staged = stage_prepared(output / "maps", output / "stage", [slug])
                _, crp, probes = staged[0]
                probe_data = json.loads(probes.read_text())
                if probe_data["new_game_panel"] != panel_expectations(crp):
                    raise ValueError("Panel expectations differ from generated CRP")
                original = folder / crp.name
                if sha(crp) != sha(original):
                    raise ValueError("Staged CRP differs from export")
                shutil.copyfile(
                    folder / "water-risk.json", crp.parent / "water-risk.json"
                )
                row["stage"] = {
                    "crp_sha256": sha(crp),
                    "probes_sha256": sha(probes),
                    "new_game_panel": probe_data["new_game_panel"],
                    "hydraulic_probe_reference": probe_data[
                        "hydraulic_probe_reference"
                    ],
                }
                if baseline is not None:
                    row["baseline_comparison"] = compare_export(
                        folder, baseline / "maps" / slug
                    )
            except Exception as error:
                row["stage_error"] = str(error)
                (folder / "stage-error.log").write_text(traceback.format_exc())
        report["cases"][slug] = row
        dump(report_path, report)
        print(
            f"{slug}: {row['status']}; water-risk={risk['status']}; staged={'stage' in row}",
            flush=True,
        )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--only", nargs="+", help="Run a subset without changing the frozen cohort"
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        help="Reuse this completed frozen cohort's exact inputs, preserve its exports, and compare bytes",
    )
    args = parser.parse_args()
    qualify(
        args.output.resolve(),
        args.only,
        args.baseline.resolve() if args.baseline else None,
    )
