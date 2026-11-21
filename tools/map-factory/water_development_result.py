"""Validate a matched native development intervention, not a holdout score."""

import argparse
import json
import math
from pathlib import Path

from crp import read_package
from maintained_water import storage_outcome
from run_water_panel import validate
from water_diagnostics import bind_sources, decode_water, digest
from water_risk_corpus import native_outcome, sha


def read_samples(native):
    with (native / "timeline.jsonl").open() as stream:
        return [row for line in stream if (row := json.loads(line))["kind"] == "sample"]


def verify_loaded_sources(samples, expected):
    """Check the configured native table at every recorded water sample."""
    count = 0
    for row in samples:
        sources = row["water"]["sources"]
        if len(sources) != len(expected):
            raise ValueError("Loaded native source count differs from package")
        for actual, encoded in zip(sources, expected):
            if (
                actual["id"] != encoded["index"] + 1
                or actual["type"] != encoded["type"]
                or actual["input_rate"] != encoded["intake_rate"]
                or actual["output_rate"] != encoded["output_rate"]
                or not math.isclose(
                    actual["target"],
                    encoded["target_fixed"] / 64,
                    rel_tol=0,
                    abs_tol=0.0001,
                )
                or [actual["x"], actual["z"]] != encoded["position"][::2]
            ):
                raise ValueError(
                    f"Loaded native source differs at {row['label']}: {encoded['index']}"
                )
        count += 1
    if count < 13:
        raise ValueError("Missing full thirteen-sample source readback")
    return {
        "samples": count,
        "sources_per_sample": len(expected),
    }


def verify_source_factor(diagnostic, decoded):
    """Reject a changed target, position, rate direction, or initial grid."""
    mode = diagnostic["mode"]
    before = diagnostic["source_controls"]
    if mode in {"reservoir-output-off", "river-output-off", "all-output-off"}:
        field, indices_key, other_key = (
            "output_rate",
            "changed_output_indices",
            "changed_intake_indices",
        )
        classes = {
            row["index"]: row["class"] for row in diagnostic["control_classification"]
        }
        selected = {
            row["index"]
            for row in before
            if row[field] > 0
            and (
                mode == "all-output-off"
                or classes[row["index"]]
                == {"reservoir-output-off": "reservoir", "river-output-off": "river"}[
                    mode
                ]
            )
        }
    elif mode == "below-sea-intake-off":
        field, indices_key, other_key = (
            "intake_rate",
            "changed_intake_indices",
            "changed_output_indices",
        )
        selected = {
            row["index"]
            for row in before
            if row[field] > 0 and row["target_fixed"] / 64 < diagnostic["sea_level_m"]
        }
    else:
        raise ValueError("Unsupported source-only intervention")
    if (
        set(diagnostic[indices_key]) != selected
        or diagnostic[other_key]
        or diagnostic["initial_water_changed_cells"]
        or digest(decoded["depth"].astype("<u2").tobytes())
        != diagnostic["initial_water_before_sha256"]
        or decoded["sea_level_m"] != diagnostic["sea_level_m"]
        or len(before) != len(decoded["sources"])
    ):
        raise ValueError("Intervention differs from its declared source-only factor")
    for original, actual in zip(before, decoded["sources"]):
        expected = {**original, **({field: 0} if original["index"] in selected else {})}
        if actual != expected:
            raise ValueError("Unexpected field change in source-only factor")
    return {"field": field, "indices": sorted(selected)}


def result(baseline, staged, native, harness_source):
    """Bind native inputs/cleanup and retain the unchanged original water gates."""
    diagnostic = json.loads((staged / "diagnostic.json").read_text())
    hydro = json.loads((staged / "hydrology.json").read_text())
    package = hydro["map_id"] + ".crp"
    if sha(staged / package) != diagnostic["crp_sha256"]:
        raise ValueError("Diagnostic package hash changed")
    payload = next(
        a["payload"]
        for a in read_package((staged / package).read_bytes())[1]
        if a["kind"] == 52
    )
    decoded = decode_water(payload)
    bind_sources(decoded, hydro)
    factor = verify_source_factor(diagnostic, decoded)
    original_report = json.loads((baseline / "report.json").read_text())
    original_verdict = json.loads((baseline / "verdict.json").read_text())
    original_source = json.loads((baseline / "harness-source.json").read_text())
    if (
        original_report["game_minutes"] < 60
        or original_source.get("dirty") is not False
        or original_source.get("commit") != harness_source
    ):
        raise ValueError("Baseline lacks the same clean full-run harness identity")
    if original_report["session"]["map"]["sha256"] != diagnostic["source_crp_sha256"]:
        raise ValueError("Baseline native report belongs to a different package")
    for staged_name, baseline_name in [
        ("terrain.u16", "grids/t000-terrain.u16"),
        ("water.u16", "grids/t000-water.u16"),
        ("probes.json", "probes.json"),
        ("mapped-water.u8", "mapped-water.u8"),
    ]:
        if sha(staged / staged_name) != sha(baseline / baseline_name):
            raise ValueError(f"Matched observation input changed: {staged_name}")
    files = [package, "terrain.u16", "water.u16", "probes.json", "mapped-water.u8"]
    item = {
        "slug": hydro["map_id"],
        "package": package,
        "files_sha256": {name: sha(staged / name) for name in files},
    }
    report = validate(item, staged, native, harness_source)
    baseline_mod = original_report["session"].get("mod_sha256")
    native_mod = report["session"].get("mod_sha256")
    if not baseline_mod or native_mod != baseline_mod:
        raise ValueError("Matched development observations used different mod bytes")
    verdict = json.loads((native / "verdict.json").read_text())
    checks = {c["name"]: c for c in verdict["checks"]}
    baseline_checks = {c["name"]: c for c in original_verdict["checks"]}
    if verdict["thresholds"] != original_verdict["thresholds"]:
        raise ValueError("Native acceptance thresholds changed")
    baseline_samples, native_samples = read_samples(baseline), read_samples(native)
    return {
        "schema": "polli.water-development-intervention/1",
        "mode": diagnostic["mode"],
        "qualification": "causal development comparison only; NOT a stable-water promise or holdout result",
        "package_sha256": diagnostic["crp_sha256"],
        "source_package_sha256": diagnostic["source_crp_sha256"],
        "changed_output_indices": diagnostic["changed_output_indices"],
        "changed_intake_indices": diagnostic["changed_intake_indices"],
        "verified_factor": factor,
        "engineered_storage_comparator": {
            "baseline": storage_outcome(
                hydro,
                original_report,
                baseline_samples,
            ),
            "intervention": storage_outcome(
                hydro,
                report,
                native_samples,
            ),
        },
        "game_minutes": report["game_minutes"],
        "harness_source": harness_source,
        "runtime_binding": {
            "baseline_mod_sha256": baseline_mod,
            "intervention_mod_sha256": native_mod,
            "loaded_assembly_identity": "unverified by this old protocol; equal mod bytes and configured-source readback do not establish the later full loaded-assembly contract",
            "scope": "Development comparison only; no runtime qualification retrofitted onto the historical baseline.",
        },
        "baseline": native_outcome(original_report, original_verdict),
        "intervention": native_outcome(report, verdict),
        "baseline_flood_grids": baseline_checks["no_flooding"]["value"]["grids"],
        "intervention_flood_grids": checks["no_flooding"]["value"]["grids"],
        "native_curve": report["curve"],
        "isolated_initialized_losses": [
            {key: point[key] for key in ("name", "x", "z", "depth_start", "depth_end")}
            for point in report["points"]
            if point.get("wet_start")
            and not point.get("wet_end")
            and not point.get("wet_within_64m_end")
        ],
        "required_retention_checks": {
            name: {"status": checks[name]["status"], "value": checks[name]["value"]}
            for name in ("probes_wet_end", "probes_wet_throughout")
        },
        "native_overall_verdict": verdict["verdict"],
        "native_failed_checks": [
            c["name"] for c in verdict["checks"] if c["status"] == "fail"
        ],
        "cleanup": report["session"]["cleanup"],
        "native_files_sha256": {
            name: sha(native / name)
            for name in [
                "report.json",
                "verdict.json",
                "harness-source.json",
                "probes.json",
                "mapped-water.u8",
                "reference-water.u16",
            ]
        },
        "baseline_files_sha256": {
            name: sha(baseline / name)
            for name in [
                "report.json",
                "verdict.json",
                "probes.json",
                "mapped-water.u8",
                "reference-water.u16",
            ]
        },
        "diagnostic_sha256": sha(staged / "diagnostic.json"),
        "matched_observation_inputs": True,
        "loaded_source_readback": {
            "baseline": {
                **verify_loaded_sources(
                    baseline_samples, diagnostic["source_controls"]
                ),
                "timeline_sha256": sha(baseline / "timeline.jsonl"),
            },
            "intervention": {
                **verify_loaded_sources(native_samples, decoded["sources"]),
                "timeline_sha256": sha(native / "timeline.jsonl"),
            },
            "scope": "Configured rates/positions/targets, not measured flux",
        },
        "thresholds_sha256": digest(
            json.dumps(verdict["thresholds"], sort_keys=True).encode()
        ),
        "limits": [
            "One development intervention does not identify every failure mechanism.",
            "Thirteen samples do not prove continuous retention.",
            "No human, populated-city, long-term or release qualification.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("staged", type=Path)
    parser.add_argument("native", type=Path)
    parser.add_argument("--harness-source", required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            result(args.baseline, args.staged, args.native, args.harness_source),
            indent=2,
        )
    )
