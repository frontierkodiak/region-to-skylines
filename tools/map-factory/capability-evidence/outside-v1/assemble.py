"""Assemble auditable evidence rows; missing observations stay null, never false."""

import argparse
import datetime
import gzip
import hashlib
import json
import re
from pathlib import Path

FIELDS = {
    "road": ("incomingRoads", "outgoingRoads"),
    "rail": ("incomingTrainTracks", "outgoingTrainTracks"),
    "ship": ("incomingShipPath", "outgoingShipPath"),
    "air": ("incomingPlanePath", "outgoingPlanePath"),
}
HERE = Path(__file__).resolve().parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def retain(source, target):
    raw = source.read_bytes()
    destination = HERE / "raw" / (target + ".gz")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(gzip.compress(raw, mtime=0))
    return {
        "path": str(destination.relative_to(HERE)),
        "sha256": sha(raw),
        "encoding": "gzip",
        "original_path": str(source),
    }


def retain_path_events(source, target):
    original = source.read_bytes()
    raw = b"".join(
        line
        for line in original.splitlines(keepends=True)
        if json.loads(line)["kind"] == "paths"
    )
    destination = HERE / "raw" / (target + ".gz")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(gzip.compress(raw, mtime=0))
    return {
        "path": str(destination.relative_to(HERE)),
        "sha256": sha(raw),
        "encoding": "gzip",
        "original_path": str(source),
        "original_sha256": sha(original),
        "extraction": "Only unchanged original JSONL lines whose kind is paths; not the full timeline.",
    }


def retain_game_events(source, target):
    original = source.read_bytes()
    pattern = rb"^(Gfx Device:|Gfx Version:|\[Cs1Harness\]|ReflectionTypeLoadException:|TypeLoadException:|NullReferenceException:)"
    raw = b"".join(
        line for line in original.splitlines(keepends=True) if re.match(pattern, line)
    )
    destination = HERE / "raw" / (target + ".gz")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(gzip.compress(raw, mtime=0))
    return {
        "path": str(destination.relative_to(HERE)),
        "sha256": sha(raw),
        "encoding": "gzip",
        "original_path": str(source),
        "original_sha256": sha(original),
        "extraction": "Unchanged engine renderer, harness and exception-header lines only. Full game log stays in the run holding; account and DLC lines are not redistributed.",
    }


def assemble(selection, native, reproduction, attempt_id="attempt-1"):
    rows = []
    artifacts = []
    for case in selection["cases"]:
        slug = case["slug"]
        cpu_path = Path(case["cpu_report"])
        cpu_raw = cpu_path.read_bytes()
        if sha(cpu_raw) != case["cpu_report_sha256"]:
            raise ValueError("frozen CPU report changed")
        cpu = json.loads(cpu_raw)["cases"][slug]
        cpu_evidence = retain(
            cpu_path, "cpu-boston.json" if slug == "boston" else "cpu-archived.json"
        )
        exporter_sha = case["exporter_source_sha"]
        reproduction_evidence = None
        if slug != "boston" and (reproduction / "cpu-report.json").exists():
            reproduced = json.loads((reproduction / "cpu-report.json").read_text())[
                "cases"
            ].get(slug)
            if reproduced:
                if (
                    reproduced["generation"]["package"]["sha256"]
                    != case["artifact_sha256"]
                ):
                    raise ValueError(f"reproduction package differs: {slug}")
                if not reproduced["baseline_comparison"]["package_unchanged"]:
                    raise ValueError(f"reproduction comparison differs: {slug}")
                exporter_sha = case["requested_source_sha"]
                reproduction_evidence = retain(
                    reproduction / "cpu-report.json", "cpu-reproduction.json"
                )
        base = {
            "square": case["square"],
            "slug": slug,
            "exporter_source_sha": exporter_sha,
            "artifact_sha256": case["artifact_sha256"],
            "prediction": None,
            "observed": None,
            "observed_at": None,
        }
        folder = native / slug
        observation_path = folder / "observation.json"
        observation = (
            json.loads(observation_path.read_text())
            if observation_path.exists()
            else None
        )
        observation_evidence = (
            retain(observation_path, slug + "/" + attempt_id + "/observation.json")
            if observation
            else None
        )
        if observation and observation["artifact_sha256"] != case["artifact_sha256"]:
            raise ValueError(f"native observation belongs to another package: {slug}")
        native_refs = {}
        for filename in [
            "panel.json",
            "networks.json",
            "ship-water-at-opening.json",
            "gpu.csv",
            "game.log",
        ]:
            path = folder / filename
            if path.exists():
                writer = retain_game_events if filename == "game.log" else retain
                native_refs[filename] = writer(
                    path, slug + "/" + attempt_id + "/" + filename
                )
        package = cpu["generation"]["package"]["highways"]
        count_keys = {
            "road": ("incoming_roads", "outgoing_roads"),
            "rail": ("train_tracks", "train_tracks"),
            "ship": ("ship_paths", "ship_paths"),
            "air": ("plane_paths", "plane_paths"),
        }
        panel = (
            json.loads((folder / "panel.json").read_text())
            if (folder / "panel.json").exists()
            else None
        )
        stamp = observation.get("finished_at") if observation else None
        for capability, fields in FIELDS.items():
            counts = [package[k] for k in count_keys[capability]]
            common = {**base, "capability_id": capability}
            rows.append(
                {
                    **common,
                    "oracle_type": "generated_connection",
                    "observed": any(counts),
                    "counts": counts,
                    "raw_evidence": cpu_evidence,
                    "limitations": [
                        "Authored metadata/network receipt, not game behavior."
                    ],
                }
            )
            available = panel is not None and "connections" in panel
            panel_counts = (
                [panel["connections"][field] for field in fields] if available else None
            )
            rows.append(
                {
                    **common,
                    "oracle_type": "native_new_game_panel",
                    "prediction": any(counts),
                    "prediction_basis": "Authored package counts, not geographic feasibility.",
                    "observed": any(panel_counts) if available else None,
                    "counts": panel_counts,
                    "expected_counts": counts,
                    "counts_match": panel_counts == counts if available else None,
                    "observed_at": stamp,
                    "raw_evidence": native_refs.get("panel.json"),
                    "limitations": [
                        "Panel availability/count readback only; does not establish native lane path or service."
                    ],
                }
            )
            paths = (
                [
                    p
                    for p in observation.get("paths", [])
                    if p["request"]["capability"] == capability
                ]
                if observation
                else []
            )
            for path in paths or [None]:
                result = path.get("result", {}) if path else {}
                observed = result.get("success") if result.get("complete") else None
                rows.append(
                    {
                        **common,
                        "oracle_type": "native_path",
                        "prediction": (
                            True
                            if path["request"]["name"] != "outside-to-outside"
                            else None
                        )
                        if path
                        else None,
                        "observed": observed,
                        "observed_at": stamp,
                        "request": path.get("request") if path else None,
                        "path_result": result if path else None,
                        "error": path.get("error")
                        if path
                        else observation.get("error")
                        if observation
                        else "not run",
                        "raw_evidence": observation_evidence,
                        "limitations": [
                            "Only the named native lane endpoints/direction; no network repair. No request is unknown, not a failed path.",
                            "Path success does not establish ship water clearance, port/airport operation, passenger/cargo demand, or economic service.",
                        ],
                    }
                )
            rows.append(
                {
                    **common,
                    "oracle_type": "actual_service",
                    "raw_evidence": None,
                    "limitations": [
                        "Not tested by this quick-opening study; no port, airport or rail terminal service assertion."
                    ],
                }
            )
            rows.append(
                {
                    **common,
                    "oracle_type": "geographic_impossibility",
                    "raw_evidence": None,
                    "limitations": [
                        "A missing generated route, runway or rail observation is not proof that geography cannot support a connection."
                    ],
                }
            )
        archive = json.loads((HERE / "archives.json").read_text()).get(slug)
        if archive:
            archive = Path(archive)
            report = json.loads((archive / "report.json").read_text())
            if report["session"]["map"]["sha256"] != case["artifact_sha256"]:
                raise ValueError(f"archive package differs: {slug}")
            report_ref = retain(archive / "report.json", slug + "/archived-report.json")
            timeline_ref = retain_path_events(
                archive / "timeline.jsonl", slug + "/archived-timeline.jsonl"
            )
            events = [
                json.loads(line)
                for line in (archive / "timeline.jsonl").read_text().splitlines()
            ]
            path_events = [event for event in events if event["kind"] == "paths"]
            panel_path = archive / "new-game-panel.json"
            if panel_path.exists():
                panel_capture = json.loads(panel_path.read_text())
                observed_panel = panel_capture["observed"]
                if (
                    Path(observed_panel["path"]).name
                    != Path(report["session"]["map"]["installed"]).name
                ):
                    raise ValueError("archived panel selects another package")
                panel_ref = retain(panel_path, slug + "/archived-panel.json")
                native_refs["archived-panel.json"] = panel_ref
                for capability, fields in FIELDS.items():
                    counts = [observed_panel["connections"][field] for field in fields]
                    expected = [package[k] for k in count_keys[capability]]
                    rows.append(
                        {
                            **base,
                            "capability_id": capability,
                            "oracle_type": "native_new_game_panel",
                            "prediction": any(expected),
                            "observed": any(counts),
                            "counts": counts,
                            "expected_counts": expected,
                            "counts_match": counts == expected,
                            "observed_at": datetime.datetime.fromtimestamp(
                                panel_path.stat().st_mtime, datetime.UTC
                            ).isoformat(),
                            "raw_evidence": panel_ref,
                            "archive_context": {"harness": report["harness"]},
                            "limitations": [
                                "Exact-package-bound archived native panel, before player construction. Timestamp basis is original capture file mtime, not an embedded wall clock. Panel counts do not validate native paths or service."
                            ],
                        }
                    )
            for event, key in [
                (path_events[0], "paths_start"),
                (path_events[-1], "paths_end"),
            ]:
                if event["checks"] != report[key]:
                    raise ValueError(
                        "archived timeline path results differ from bound report"
                    )
                for path in event["checks"]:
                    rows.append(
                        {
                            **base,
                            "capability_id": "rail"
                            if path["name"].startswith("rail:")
                            else "road",
                            "oracle_type": "native_path",
                            "prediction": True,
                            "observed": path["success"] if path["complete"] else None,
                            "observed_at": datetime.datetime.fromtimestamp(
                                event["wall"], datetime.UTC
                            ).isoformat(),
                            "path_result": path,
                            "raw_evidence": report_ref,
                            "timeline_evidence": timeline_ref,
                            "archive_context": {
                                "phase": key,
                                "harness": report["harness"],
                                "scenario": report.get("requested_scenario"),
                            },
                            "limitations": [
                                "Exact-byte-bound historical car/train path observation during a first-hour player run (player roads/buildings may be present); no ship/air or service assertion."
                            ],
                        }
                    )
        geometry_path = (
            Path(case["package"]).parent.parent.parent
            / "inputs"
            / slug
            / "geometry.json"
        )
        geometry = json.loads(geometry_path.read_text())
        capture_path = geometry_path.parent / "capture.json"
        geometry_evidence = retain(geometry_path, slug + "/geometry.json")
        observed_features = {
            "road": sum(
                feature.get("class")
                in ("motorway", "trunk", "motorway_link", "trunk_link")
                for feature in geometry.get("roads", [])
            ),
            "rail": sum(
                feature.get("class") == "rail" for feature in geometry.get("roads", [])
            ),
            "ship": len(geometry.get("oceans", [])),
            "air": len(geometry.get("runways", [])),
        }
        for capability, count in observed_features.items():
            rows.append(
                {
                    **base,
                    "capability_id": capability,
                    "oracle_type": "captured_feature",
                    "observed": count > 0,
                    "feature_count": count,
                    "raw_evidence": geometry_evidence,
                    "limitations": [
                        "Raw captured fragments, not exhaustive geographic support or generated connections. Ship field counts ocean polygons, not all inland water. Historical fixture airport fallback is not a captured runway."
                    ],
                }
            )
        artifacts.append(
            {
                "slug": slug,
                "artifact_sha256": case["artifact_sha256"],
                "exporter_source_sha": exporter_sha,
                "cpu_evidence": cpu_evidence,
                "reproduction_evidence": reproduction_evidence,
                "input_coverage": {
                    "geometry_sha256": sha(geometry_path.read_bytes()),
                    "captured_airport": geometry.get("airport"),
                    "capture_receipt": retain(capture_path, slug + "/capture.json")
                    if capture_path.exists()
                    else None,
                    "limitations": "Captured features are not exhaustive coverage; fixture airport fallback may lie outside square.",
                },
                "water_risk_status": case["water_risk_status"],
                "water_risk_evidence": retain(
                    Path(case["package"]).parent / "water-risk.json",
                    slug + "/water-risk.json",
                ),
                "exporter_rules_receipt": cpu["generation"]["real_roads"],
                "native_evidence": native_refs,
                "observation_evidence": observation_evidence,
                "completed": observation.get("completed", False)
                if observation
                else False,
                "error": observation.get("error") if observation else "not run",
            }
        )
    for row in rows:
        if row["prediction"] is not None and row["oracle_type"] == "native_path":
            row["prediction_basis"] = (
                "Frozen named probe expectation, not an independent geographic model prediction."
            )
        elif row["oracle_type"] == "native_new_game_panel":
            row["prediction_basis"] = (
                "Authored package connection counts, not geographic feasibility."
            )
        if (
            row["oracle_type"] in {"native_path", "native_new_game_panel"}
            and "archive_context" not in row
        ):
            row["attempt_id"] = attempt_id
    return {
        "schema": 1,
        "issue": "PL-1121",
        "rows": rows,
        "artifacts": artifacts,
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "collector_versions": json.loads(
            (HERE / "collector-versions.json").read_text()
        )["versions"],
        "environment_events": json.loads((HERE / "startup-events.json").read_text())
        if (HERE / "startup-events.json").exists()
        else [],
        "agreement": None,
        "fitting": {
            "fitted_bounds": [],
            "held_out": ["boston"],
            "limitations": "No depth/width/grade intervention sweep; no fitted native threshold or aggregate agreement claim.",
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--reproduction", type=Path, required=True)
    parser.add_argument("--retry-native", type=Path, action="append", default=[])
    args = parser.parse_args()
    roots = [args.native.resolve(), *[path.resolve() for path in args.retry_native]]
    if len(set(roots)) != len(roots):
        raise ValueError("native attempt roots must be distinct")
    evidence = assemble(
        json.loads((HERE / "selection.json").read_text()),
        args.native,
        args.reproduction,
    )

    def native_attempt(case, identity):
        return {
            "attempt_id": identity,
            **{
                key: case[key]
                for key in [
                    "artifact_sha256",
                    "observation_evidence",
                    "native_evidence",
                    "completed",
                    "error",
                ]
            },
        }

    for case in evidence["artifacts"]:
        case["attempts"] = (
            [native_attempt(case, "attempt-1")] if case["observation_evidence"] else []
        )
    by_slug = {case["slug"]: case for case in evidence["artifacts"]}
    for index, retry_root in enumerate(args.retry_native, 2):
        identity = f"attempt-{index}"
        retry = assemble(
            json.loads((HERE / "selection.json").read_text()),
            retry_root,
            args.reproduction,
            identity,
        )
        observed = {
            case["slug"] for case in retry["artifacts"] if case["observation_evidence"]
        }
        evidence["rows"].extend(
            row
            for row in retry["rows"]
            if row["slug"] in observed
            and row["oracle_type"] in {"native_path", "native_new_game_panel"}
            and "archive_context" not in row
        )
        for case in retry["artifacts"]:
            if case["slug"] not in observed:
                continue
            target = by_slug[case["slug"]]
            target["attempts"].append(native_attempt(case, identity))
            target["completed"] = any(
                attempt["completed"] for attempt in target["attempts"]
            )
            target["error"] = None if target["completed"] else case["error"]
    (HERE / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    for row in evidence["rows"]:
        ref = row.get("raw_evidence")
        if (
            ref
            and sha(gzip.decompress((HERE / ref["path"]).read_bytes())) != ref["sha256"]
        ):
            raise ValueError("raw evidence hash mismatch")
    water = {
        row["slug"]: row
        for row in json.loads((HERE / "water-support.json").read_text())["rows"]
    }
    completed = sum(case["completed"] for case in evidence["artifacts"])
    md = [
        "# Observed outside-connection results",
        "",
        f"New native observations completed: {completed}/9 selected squares.",
        "",
        "A path witness means at least one selected native request succeeded. It does not mean every lane or direction passed.",
        "Failed requests and unknowns remain in evidence.json. No aggregate agreement score is calculated.",
        "",
        "Archived exact-package car and train paths are included. Those first-hour runs can contain player construction.",
        "",
        "| Square | Road path | Rail path | Ship path | Air path | 6 m raster witness |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for case in evidence["artifacts"]:
        cells = []
        for capability in FIELDS:
            observed = [
                row["observed"]
                for row in evidence["rows"]
                if row["slug"] == case["slug"]
                and row["capability_id"] == capability
                and row["oracle_type"] == "native_path"
            ]
            cells.append(
                "witness"
                if True in observed
                else "failed probes"
                if False in observed
                else "unknown"
            )
        raster = (
            "yes" if water[case["slug"]]["rasters"][0]["deep_6m_edge_pairs"] else "no"
        )
        md.append("| " + " | ".join([case["slug"], *cells, raster]) + " |")
    md.extend(
        [
            "",
            "The last column tests only a two-edge path through the authored raster at the exporter's existing 6 m depth choice. It is not a native ship threshold or a geographic impossibility result.",
            "",
            "## Retained attempt errors",
            "",
        ]
    )
    errors = [
        f"- {case['slug']} {attempt['attempt_id']}: {attempt['error']}"
        for case in evidence["artifacts"]
        for attempt in case["attempts"]
        if attempt["error"]
    ]
    md.extend(errors or ["No attempt errors recorded."])
    md.extend(
        [
            "",
            "Actual terminal service, strict no-mods behavior, continuous ship clearance, and sustained water safety are not verified.",
            "",
            "The nine water-risk reports remain unchanged. The held-out square is Boston. No native depth, width, or grade threshold was fitted.",
            "",
        ]
    )
    (HERE / "RESULTS.md").write_text("\n".join(md))
    print(
        f"{len(evidence['rows'])} rows; {sum(a['completed'] for a in evidence['artifacts'])}/9 native openings complete"
    )
