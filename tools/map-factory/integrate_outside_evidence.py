"""Import immutable native receipts; score frozen predictions without fitting them."""

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
KINDS = ("road", "rail", "ship", "air")
STUDY = "outside-v1"
SCOPE = "sampled_native_lane_paths_at_opening"
INPUTS = ("terrain.u16", "water.u16", "hydrology.json")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def project(evidence_root, predictions, source_commit):
    """One square/offset-kind row, not one vote per lane or archived player run."""
    tracked = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=evidence_root, text=True
    ).strip()
    if tracked != source_commit:
        raise ValueError("Native source must be the exact declared commit")
    subprocess.run(
        ["git", "diff", "--exit-code", "HEAD", "--", "."],
        cwd=evidence_root,
        check=True,
        capture_output=True,
    )
    evidence_bytes = (evidence_root / "evidence.json").read_bytes()
    evidence = json.loads(evidence_bytes)
    selection_bytes = (evidence_root / "selection.json").read_bytes()
    selection = json.loads(selection_bytes)
    water_bytes = (evidence_root / "water-support.json").read_bytes()
    water = {r["artifact_sha256"]: r for r in json.loads(water_bytes)["rows"]}
    prediction_bytes = predictions.read_bytes()
    frozen = json.loads(prediction_bytes)
    if sha(selection_bytes) != frozen["selection_sha256"]:
        raise ValueError("Native selection differs from the frozen prediction cohort")
    predicted = {r["artifact_sha256"]: r for r in frozen["cases"]}
    selected = {r["artifact_sha256"]: r for r in selection["cases"]}
    artifacts = {r["artifact_sha256"]: r for r in evidence["artifacts"]}
    if (
        len(predicted) != 9
        or predicted.keys() != artifacts.keys()
        or predicted.keys() != selected.keys()
    ):
        raise ValueError("Fixed nine exact-package cohort changed")
    base = f"https://github.com/frontierkodiak/region-to-skylines/blob/{source_commit}/tools/map-factory/capability-evidence/outside-v1/"
    checked = {}

    def raw(ref):
        relative = Path(ref["path"])
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or ref.get("encoding") != "gzip"
        ):
            raise ValueError("Invalid retained evidence reference")
        value = gzip.decompress((evidence_root / relative).read_bytes())
        if sha(value) != ref["sha256"]:
            raise ValueError(f"Retained evidence changed: {relative}")
        checked[str(relative)] = ref["sha256"]
        return value

    def link(ref):
        raw(ref)
        return {
            "url": base + ref["path"],
            "sha256": ref["sha256"],
            "hash_of": "decompressed_bytes",
        }

    rows = {kind: [] for kind in KINDS}
    certificates = []
    versions = {v["collector_sha256"]: v for v in evidence["collector_versions"]}
    network_source = evidence_root.parents[2] / "cs1-harness/mod/NetworkOps.cs"
    network_sha = sha(network_source.read_bytes())
    for digest, artifact in artifacts.items():
        prediction = predicted[digest]
        risk = json.loads(raw(artifact["water_risk_evidence"]))
        if {name: risk["inputs_sha256"][name] for name in INPUTS} != {
            name: prediction["inputs_sha256"][name] for name in INPUTS
        }:
            raise ValueError("Native prepared inputs differ from frozen model inputs")
        if artifact["reproduction_evidence"]:
            reproduction = json.loads(raw(artifact["reproduction_evidence"]))["cases"][
                artifact["slug"]
            ]
            if (
                not reproduction["baseline_comparison"]["package_unchanged"]
                or reproduction["generation"]["package"]["sha256"] != digest
            ):
                raise ValueError("Native exporter reproduction did not match")
        common = {
            "study": STUDY,
            "square": prediction["square"],
            "artifact_sha256": digest,
            "source_sha": artifact["exporter_source_sha"],
            "prediction_model": frozen["model"],
            "prediction_source_sha": frozen["model_source_head"],
            "prediction_files_sha256": frozen["model_source_files_sha256"],
            "prediction_frozen_at": frozen["frozen_at"],
        }
        support = water[digest]
        if support["water_sha256"] != prediction["inputs_sha256"]["water.u16"]:
            raise ValueError("Raster support belongs to different prepared water")
        rows["ship"].append(
            {
                **common,
                "oracle": "prepared_raster_support",
                "observed_at": evidence["generated_at"],
                "predicted": None,
                "observed": bool(support["rasters"][0]["deep_6m_edge_pairs"]),
                "claim": "Prepared-water raster only: two distinct edges at the existing 6m exporter criterion. Not a native depth threshold, width/turning test or geographic impossibility claim.",
                "rasters": support["rasters"],
                "evidence": [
                    link(support["raw_evidence"]),
                    {
                        "url": base + "water-support.json",
                        "sha256": sha(water_bytes),
                        "hash_of": "file_bytes",
                    },
                ],
            }
        )
        completed = []
        for attempt in artifact["attempts"]:
            ref = attempt["observation_evidence"]
            observation = json.loads(raw(ref))
            if observation["artifact_sha256"] != digest:
                raise ValueError("Native attempt belongs to another package")
            if observation.get("completed"):
                session = observation["session"]
                if (
                    session["map"]["sha256"] != digest
                    or session["mod_sha256"]
                    != observation["build_receipt"]["dll_sha256"]
                    or any(session["cleanup"].values())
                ):
                    raise ValueError("Native installed package/mod/cleanup mismatch")
                if (
                    observation["collector_sha256"] not in versions
                    or observation["build_receipt"]["sources"]["NetworkOps.cs"]
                    != network_sha
                ):
                    raise ValueError(
                        "Native collector/mod source has no matching retained binding"
                    )
                for path in observation["paths"]:
                    expected = {
                        "road": "car",
                        "rail": "train",
                        "ship": "ship",
                        "air": "plane",
                    }[path["request"]["capability"]]
                    if path.get("mode") != expected:
                        raise ValueError(
                            "Native vehicle mode differs from labelled capability"
                        )
                completed.append((attempt, observation))
            else:
                for kind in KINDS:
                    rows[kind].append(
                        {
                            **common,
                            "oracle": "native_attempt_error",
                            "observed_at": observation["finished_at"],
                            "predicted": None,
                            "observed": None,
                            "error": observation.get("error"),
                            "evidence": [link(ref)],
                        }
                    )
        if len(completed) != 1:
            raise ValueError(
                "Expected one complete fresh observation per fixed package; no best-attempt selection"
            )
        attempt, observation = completed[0]
        timestamp = observation["finished_at"]
        ref = attempt["observation_evidence"]
        evidence_links = [link(ref)]
        collector_link = link(versions[observation["collector_sha256"]]["raw_source"])
        panel_ref = attempt["native_evidence"]["panel.json"]
        panel = json.loads(raw(panel_ref))
        network_ref = attempt["native_evidence"]["networks.json"]
        segments = {s["id"]: s for s in json.loads(raw(network_ref))["segments"]}

        def two_edge(path):
            request = path["request"]
            a, b = (segments.get(request[key][0]) for key in ("from", "to"))
            if not a or not b or a["id"] == b["id"]:
                return False
            ends = [
                {
                    s[key]
                    for key in ("start", "end")
                    if "Outside" in s[key + "_flags"].split(", ")
                }
                for s in (a, b)
            ]
            return any(x != y for x in ends[0] for y in ends[1])

        # Native receipts, not assembler booleans, are the scoring source.
        for kind in KINDS:
            paths = [
                p for p in observation["paths"] if p["request"]["capability"] == kind
            ]
            generic = [p for p in paths if p["request"]["name"] == "outside-to-outside"]
            controls = {}
            for position in ("boundary", "midpoint"):
                subset = [
                    p
                    for p in generic
                    if p["request"].get("position_kind", "boundary") == position
                ]
                values = []
                for path in subset:
                    result = path.get("result", {})
                    value = (
                        result.get("success")
                        if result.get("complete")
                        and result.get("released")
                        and not path.get("error")
                        else None
                    )
                    if value is not None and type(value) is not bool:
                        raise ValueError(
                            "Native path outcome must be boolean or unknown"
                        )
                    values.append(value)
                observed = (
                    True
                    if True in values
                    else False
                    if values and all(v is False for v in values)
                    else None
                )
                rows[kind].append(
                    {
                        **common,
                        "oracle": f"native_probe_{position}_selected_pair",
                        "observed_at": timestamp,
                        "predicted": None,
                        "observed": observed,
                        "claim": "Probe diagnostic only, not a capability label: selected pairs can be same-role or lane-disconnected. Failure does not disprove other pairs.",
                        "requests": len(subset),
                        "successes": values.count(True),
                        "failures": values.count(False),
                        "unknowns": values.count(None),
                        "evidence": evidence_links,
                    }
                )
                for direction in (0, 1):
                    group = [
                        p for p in subset if p["request"]["direction"] == direction
                    ]
                    controls[f"{position}_{direction}"] = bool(group) and all(
                        p.get("result", {}).get("complete") is True
                        and p["result"].get("released") is True
                        and p["result"].get("success") is True
                        and not p.get("error")
                        for p in group
                    )
            two_edge_paths = [p for p in paths if two_edge(p)]
            successful = [
                p
                for p in two_edge_paths
                if p.get("result", {}).get("complete") is True
                and p["result"].get("released") is True
                and p["result"].get("success") is True
                and not p.get("error")
            ]
            rows[kind].append(
                {
                    **common,
                    "oracle": "native_two_edge_witness",
                    "observed_at": timestamp,
                    "predicted": prediction["predictions"][kind]["predicted"],
                    "observed": True if successful else None,
                    "observation_status": "witness"
                    if successful
                    else "probe_limited"
                    if two_edge_paths
                    else "no_two_edge_request",
                    "claim": "A fresh completed native path joins segments at distinct outside nodes. No witness remains Unknown; a finite selected-pair failure cannot prove capability absence.",
                    "successful_requests": [p["request"] for p in successful],
                    "failed_requests": sum(
                        p.get("result", {}).get("complete") is True
                        and p["result"].get("success") is False
                        for p in two_edge_paths
                    ),
                    "evidence": [*evidence_links, link(network_ref)],
                }
            )
            named = [p for p in paths if p["request"]["name"] != "outside-to-outside"]
            rows[kind].append(
                {
                    **common,
                    "oracle": "native_path_fresh_named",
                    "observed_at": timestamp,
                    "predicted": None,
                    "observed": None,
                    "claim": "Different named endpoint/start-access predicate; not scored against the frozen edge-to-edge model.",
                    "outcomes": [
                        {
                            "request": p["request"],
                            "observed": p.get("result", {}).get("success")
                            if p.get("result", {}).get("complete")
                            else None,
                            "error": p.get("error"),
                        }
                        for p in named
                    ],
                    "evidence": evidence_links,
                }
            )
            fields = {
                "road": ("incomingRoads", "outgoingRoads"),
                "rail": ("incomingTrainTracks", "outgoingTrainTracks"),
                "ship": ("incomingShipPath", "outgoingShipPath"),
                "air": ("incomingPlanePath", "outgoingPlanePath"),
            }[kind]
            rows[kind].append(
                {
                    **common,
                    "oracle": "native_panel",
                    "observed_at": timestamp,
                    "predicted": None,
                    "observed": any(panel["connections"][key] for key in fields),
                    "counts": [panel["connections"][key] for key in fields],
                    "claim": "Panel presence/counts, not the edge-to-edge model predicate or native pathfinding.",
                    "evidence": [link(panel_ref)],
                }
            )
            if (
                kind in ("ship", "air")
                and all(controls.values())
                and prediction["predictions"][kind]["predicted"] is True
            ):
                build = observation["build_receipt"]
                certificates.append(
                    {
                        "study": STUDY,
                        "capability": kind,
                        "scope": SCOPE,
                        "artifact_sha256": digest,
                        "inputs_sha256": {
                            name: prediction["inputs_sha256"][name] for name in INPUTS
                        },
                        "native_context": {
                            "game_assemblies": build["game_assemblies"],
                            "mod_sha256": build["dll_sha256"],
                            "collector_sha256": observation["collector_sha256"],
                            "protocol": evidence["native_protocol"],
                        },
                        "collector_sha256": observation["collector_sha256"],
                        "observed_at": timestamp,
                        "controls": controls,
                        "blocked_by": ["running_game_identity_not_recorded"],
                        "evidence": [
                            *evidence_links,
                            collector_link,
                            {
                                "url": f"https://github.com/frontierkodiak/region-to-skylines/blob/{source_commit}/tools/cs1-harness/mod/NetworkOps.cs",
                                "sha256": network_sha,
                                "hash_of": "source_bytes",
                            },
                        ],
                        "limitations": "Only sampled lane paths at opening in this exact control-mod environment; no continuous clearance, terminal service, strict no-mods or sustained water claim.",
                    }
                )
        # Archives remain available but cannot rescue fresh probes or qualify promises.
        for kind in KINDS:
            archived = [
                r
                for r in evidence["rows"]
                if r["artifact_sha256"] == digest
                and r["capability_id"] == kind
                and r["oracle_type"] == "native_path"
                and r.get("archive_context")
            ]
            if archived:
                rows[kind].append(
                    {
                        **common,
                        "oracle": "native_path_archived_player",
                        "observed_at": max(r["observed_at"] for r in archived),
                        "predicted": None,
                        "observed": None,
                        "claim": "Historical player-modified context; not a fresh-export witness.",
                        "successes": sum(r["observed"] is True for r in archived),
                        "failures": sum(r["observed"] is False for r in archived),
                        "evidence": [link(archived[0]["raw_evidence"])],
                    }
                )
    study = {
        "source_commit": source_commit,
        "source_url": base + "README.md",
        "evidence_sha256": sha(evidence_bytes),
        "selection_sha256": sha(selection_bytes),
        "water_support_sha256": sha(water_bytes),
        "predictions_file": str(predictions.relative_to(ROOT)),
        "predictions_sha256": sha(prediction_bytes),
        "projection_tool_sha256": sha(Path(__file__).read_bytes()),
        "prediction_model": frozen["model"],
        "prediction_source_sha": frozen["model_source_head"],
        "source_revision_basis": "source_sha is the native study's reproduced exporter revision, not a claim about an unresolved original archived-export revision. The immutable frozen prediction file retains its original null revisions and limitations.",
        "scope": evidence["scope"],
        "native_rows_retained_upstream": len(evidence["rows"]),
        "method": "One scored cell per square/capability: a fresh successful path on segments at distinct outside nodes is a positive witness. No such witness is Unknown, not a negative. Selected-pair diagnostics, named access legs, archives and panels are separate; failed requests are retained and cannot be rescued into a global verdict.",
        "limits": "Retrospective projection, not accuracy: some native runs predate prediction freeze; every model-negative cell lacks native testing, and generic failures are not exhaustive. Negative feasibility is not validated. No native depth/width/grade threshold fitted. All nine water-risk screens are warnings. Runtime game binary/assemblies were not launch-hashed, so exact-environment qualification is withheld. Service, sustained water and global impossibility remain unmeasured.",
        "qualification_candidates": certificates,
        "unscored_upstream_oracles": [
            "captured_feature",
            "generated_connection",
            "actual_service",
            "geographic_impossibility",
        ],
        "projection_raw_files_checked": len(checked),
    }
    return rows, [], study


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native_root", type=Path)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    predictions = (
        ROOT / "tools/map-factory/capability-evidence/pl1119-v3-predictions.json"
    )
    rows, certificates, study = project(
        args.native_root.resolve(), predictions, args.source_commit
    )
    path = ROOT / "capabilities.json"
    ledger = json.loads(path.read_text())
    ledger["evidence_studies"] = {STUDY: study}
    ledger["native_path_certificates"] = certificates
    for capability in ledger["capabilities"]:
        if capability["id"] in rows:
            capability["game_agreement"] = rows[capability["id"]]
            capability["status"] = "native_scored_not_boundary_fitted"
    path.write_text(json.dumps(ledger, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: dict(Counter(row["oracle"] for row in value))
                for key, value in rows.items()
            },
            indent=2,
        )
    )
    print(
        f"{len(certificates)} exact-export sampled-path certificates; no geographic promises"
    )


if __name__ == "__main__":
    main()
