"""Project the immutable targeted follow-up; never activate a certificate."""

import argparse
from collections import Counter
from datetime import datetime
import gzip
import json
from pathlib import Path
import subprocess

from integrate_outside_evidence import INPUTS, KINDS, ROOT, SCOPE, boundary_probe, sha

SOURCE = "29b095475ba2f93c7e918fefc08c736493670304"
ORIGINAL = "4cef6fb620f403c603e597a46f3bb7d7e5feadb7"
STUDY = "outside-targeted-v2"
PREDICTIONS = "tools/map-factory/capability-evidence/pl1119-v3-predictions.json"
FREEZE_SHA = "1f2db0bb64e62965137cce05ffe0cea7bf8aa339c2a8a9e9560fafe4ef64ae03"
PREFIX = "tools/map-factory/capability-evidence/outside-v1/"
BASE = f"https://github.com/frontierkodiak/region-to-skylines/blob/{SOURCE}/"
LIMITS = (
    "Targeted retrospective follow-up, not accuracy, negative fitting or a blind "
    "holdout. Only sampled native lane paths at opening, in this exact loaded-file "
    "and plugin context. File identity is not in-memory code attestation; the native collector excludes AssemblyBuilder dynamic assemblies. Three missing DLC-panel assembly errors at every opening are retained, not clean whole-game acceptance. "
    "enabled_mod_count=0 does not mean unloaded/no mods: CitiesBridge, the harness "
    "and built-ins are loaded. No air v2 controls, actual terminal service, strict "
    "no-mods, native depth/width fit, geographic negatives or sustained water. "
    "All nine water screens warn; failures and omitted pairs remain Unknown."
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, indent=2) + "\n").encode()


def timestamp(value):
    parsed = datetime.fromisoformat(value)
    require(parsed.tzinfo is not None, "Unbound timestamp")
    return parsed


def runtime_context(observation, source_files):
    """Validate literal observations, not the producer's build_matches booleans."""
    o = observation
    launch, opening = o["launch_runtime_identity"], o["runtime_identity"]
    build, session = o["build_receipt"], o["session"]
    require(o["completed"] is True and not o.get("error"), "Incomplete observation")
    require(
        session["map"]["sha256"] == o["artifact_sha256"], "Installed package changed"
    )
    require(session["mod_sha256"] == build["dll_sha256"], "Installed mod changed")
    require(
        session["cleanup"] == {"game": [], "steam_instances": [], "units_active": []},
        "Cleanup unbound",
    )
    require(session["runtime_identity"] == opening, "Session runtime differs")
    identity_keys = (
        "host_pid",
        "namespace_pid",
        "process_start_ticks",
        "executable",
        "command_line",
        "launch_args",
    )
    require(
        all(launch[k] == opening[k] for k in identity_keys),
        "Launch/opening process changed",
    )
    require(
        type(opening["host_pid"]) is int
        and opening["host_pid"] > 0
        and type(opening["namespace_pid"]) is int
        and opening["namespace_pid"] > 0
        and str(opening["process_start_ticks"]).isdigit(),
        "Ambiguous PID/start",
    )
    require(
        {p["pid"] for p in session["game_gpu"]} == {opening["host_pid"]},
        "Rendering PID differs",
    )
    require(
        timestamp(o["observed_at"])
        <= timestamp(launch["observed_at"])
        <= timestamp(o["native_context"]["observed_at"])
        <= timestamp(opening["observed_at"])
        <= timestamp(o["finished_at"]),
        "Runtime times out of order",
    )
    require(
        opening["executable"]["sha256"] == build["game_executable_sha256"],
        "Executable changed",
    )
    require(launch["launch_args"] == session["launch_args"], "Launch flags differ")
    for identity in (launch, opening):
        require(
            identity["unresolved_loaded_assemblies"] == [], "Unresolved loaded assembly"
        )
        for flags in (identity["launch_args"], identity["command_line"]):
            require(
                "--noWorkshop" in flags and "--disableMods" not in flags,
                "Actual flags differ",
            )
        require(
            identity["command_line"][0] == identity["executable"]["path"],
            "Executable path differs",
        )
        assemblies = identity["assemblies"]
        require(
            len({a["path"] for a in assemblies}) == len(assemblies)
            and len({a["name"] for a in assemblies}) == len(assemblies),
            "Ambiguous assembly inventory",
        )
        for assembly in assemblies:
            require(
                Path(assembly["path"]).is_absolute()
                and len(assembly["sha256"]) == 64
                and assembly["loaded_module_mvid"]
                and assembly["binding"]
                in (
                    "loaded_assembly_location",
                    "native_plugin_owner_and_matching_loaded_module_mvid",
                ),
                "Unbound loaded assembly file",
            )
        loaded = {Path(a["path"]).name: a["sha256"] for a in assemblies}
        require(
            all(
                loaded.get(name) == digest
                for name, digest in {
                    **build["game_assemblies"],
                    "Cs1Harness.dll": build["dll_sha256"],
                }.items()
            ),
            "Loaded file differs from build",
        )
    require(
        launch["assemblies"] == opening["assemblies"],
        "Loaded inventory changed during opening",
    )
    require(
        all(source_files(name) == digest for name, digest in build["sources"].items()),
        "Mod source changed",
    )
    for state in (o["new_game_protocol"], o["loaded"], o["native_context"]):
        require(
            state["update_mode"] == "NewGameFromMap"
            and state["invert_traffic"] == "False",
            "Actual entry/traffic differs",
        )
    require(
        o["new_game_protocol"]["loading"] == o["listed"]["path"],
        "Opened package path differs",
    )
    require(
        o["native_context"]["no_workshop"] is True
        and o["native_context"]["mods_enabled"] is True
        and o["loaded"]["loading_complete"] is True,
        "Opening context incomplete",
    )
    for state in (session["menu_status"], o["loaded"]):
        require(
            state["plugins"]
            and state["enabled_mod_count"]
            == sum(p["enabled"] for p in state["plugins"]),
            "Plugin state unbound",
        )
        paths = {p["path"] for p in state["plugins"]}
        require(len(paths) == len(state["plugins"]), "Ambiguous plugins")
        require(
            all(
                any(Path(a["path"]).is_relative_to(p) for p in paths)
                for a in opening["assemblies"]
                if a["binding"] == "native_plugin_owner_and_matching_loaded_module_mvid"
            ),
            "Loaded plugin owner missing",
        )
    return {
        "game_assemblies": build["game_assemblies"],
        "runtime_game_assemblies": build["game_assemblies"],
        "runtime_game_sha256": opening["executable"]["sha256"],
        "mod_sha256": build["dll_sha256"],
        "collector_sha256": o["collector_sha256"],
        "collector_sources": o["collector_sources"],
        "build_receipt": build,
        "launch_runtime_identity": launch,
        "opening_runtime_identity": opening,
        "menu_plugins": session["menu_status"]["plugins"],
        "opening_plugins": o["loaded"]["plugins"],
        "opening_errors": o["loaded"]["errors"],
        "opening_error_count": o["loaded"]["error_count"],
        "dynamic_assembly_scope": "CoreOps.RuntimeIdentity excludes AssemblyBuilder dynamic assemblies; this inventory covers resolved loaded files only.",
        "menu_enabled_mod_count": session["menu_status"]["enabled_mod_count"],
        "opening_enabled_mod_count": o["loaded"]["enabled_mod_count"],
        "actual_native_context": o["native_context"],
        "new_game_protocol": o["new_game_protocol"],
        "installed_map": session["map"],
        "listed_map": o["listed"],
        "package_binding": "Retained hash-bound collector selects the listed map with Path.samefile(installed), then opens that exact listed path; host/Flatpak aliases need not be textually equal.",
        "cleanup": session["cleanup"],
        "protocol": {
            "entry": "NewGameFromMap",
            "no_workshop": True,
            "strict_disable_mods": False,
            "inverted_traffic": False,
        },
        "identity_limits": "Full resolved loaded-file inventory, not in-memory code attestation or strict no-mods.",
    }


def successful(path):
    result = path.get("result", {})
    return (
        not path.get("error")
        and all(result.get(k) is True for k in ("complete", "released", "success"))
        and bool(result.get("positions"))
        and result["positions"][0] == path["request"]["from"]
        and result["positions"][-1] == path["request"]["to"]
    )


def distinct_boundary(path, segments):
    if not boundary_probe(path, segments):
        return False
    edges = []
    for key in ("from", "to"):
        segment, _, offset = path["request"][key]
        x, _, z = segments[segment]["a" if offset == 0 else "b"]
        edge = [
            name
            for name, value, target in (
                ("west", x, -8640),
                ("east", x, 8640),
                ("south", z, -8640),
                ("north", z, 8640),
            )
            if abs(value - target) < 0.01
        ]
        if len(edge) != 1:
            return False
        edges.append(edge[0])
    return edges[0] != edges[1]


def paired_controls(paths, segments):
    """Four reciprocal controls on the same segment/lane pair, not pooled votes."""
    controls = {f"{p}_{d}": False for p in ("boundary", "midpoint") for d in (0, 1)}
    groups = {}
    for path in paths:
        q = path["request"]
        if q["name"] == "outside-to-outside":
            groups.setdefault(q["pair_index"], []).append(path)
    for group in groups.values():
        by_key = {
            (p["request"]["position_kind"], p["request"]["direction"]): p for p in group
        }
        if len(group) != 4 or len(by_key) != 4 or not all(successful(p) for p in group):
            continue
        b0, b1, m0, m1 = [
            by_key.get(k)
            for k in (
                ("boundary", 0),
                ("boundary", 1),
                ("midpoint", 0),
                ("midpoint", 1),
            )
        ]
        if not all((b0, b1, m0, m1)) or not all(
            distinct_boundary(p, segments) for p in (b0, b1)
        ):
            continue
        a, b, c, d = [p["request"] for p in (b0, b1, m0, m1)]
        if (
            a["from"] != b["to"]
            or a["to"] != b["from"]
            or c["from"] != d["to"]
            or c["to"] != d["from"]
            or any(c[k][:2] != a[k][:2] or c[k][2] != 128 for k in ("from", "to"))
        ):
            continue
        return dict.fromkeys(controls, True), [p["request"] for p in (b0, b1, m0, m1)]
    return controls, []


def project(native_root, predictions=ROOT / PREDICTIONS):
    native_root = native_root.resolve()
    repo = native_root.parents[3]
    require(
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip()
        == SOURCE,
        "Wrong exact native source",
    )
    # Check both index and working bytes against the named immutable commit.
    subprocess.run(
        ["git", "diff", "--exit-code", SOURCE, "--"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    require(sha(predictions.read_bytes()) == FREEZE_SHA, "Prediction freeze changed")
    frozen = json.loads(predictions.read_bytes())
    selection_raw = (native_root / "selection.json").read_bytes()
    require(sha(selection_raw) == frozen["selection_sha256"], "Fixed selection changed")
    evidence_raw = (native_root / "evidence.json").read_bytes()
    evidence = json.loads(evidence_raw)
    predicted = {c["artifact_sha256"]: c for c in frozen["cases"]}
    artifacts = {a["artifact_sha256"]: a for a in evidence["artifacts"]}
    require(
        len(predicted) == 9
        and predicted.keys()
        == artifacts.keys()
        == {c["artifact_sha256"] for c in json.loads(selection_raw)["cases"]},
        "Fixed nine packages changed",
    )
    checked = {}

    def raw(ref):
        path = Path(ref["path"])
        require(
            not path.is_absolute()
            and ".." not in path.parts
            and ref["encoding"] == "gzip",
            "Invalid raw reference",
        )
        value = gzip.decompress((native_root / path).read_bytes())
        require(sha(value) == ref["sha256"], "Raw bytes changed")
        checked[str(path)] = ref["sha256"]
        return value

    def refs(value):
        if isinstance(value, dict):
            if value.get("encoding") == "gzip":
                raw(value)
            for child in value.values():
                refs(child)
        elif isinstance(value, list):
            for child in value:
                refs(child)

    def link(ref):
        raw(ref)
        return {
            "url": BASE + PREFIX + ref["path"],
            "sha256": ref["sha256"],
            "hash_of": "decompressed_bytes",
        }

    original = json.loads(
        subprocess.check_output(
            ["git", "show", ORIGINAL + ":" + PREFIX + "evidence.json"], cwd=repo
        )
    )
    require(
        len(original["rows"]) == 619
        and all(
            all(
                new.get(k) == old.get(k)
                for k in (
                    "request",
                    "path_result",
                    "observed",
                    "observed_at",
                    "raw_evidence",
                    "artifact_sha256",
                    "capability_id",
                    "oracle_type",
                )
            )
            for old, new in zip(original["rows"], evidence["rows"])
        ),
        "Original observation fields changed",
    )
    original_files = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", ORIGINAL, "--", PREFIX + "raw/"],
        cwd=repo,
        text=True,
    ).splitlines()
    for file in original_files:
        require(
            (repo / file).read_bytes()
            == subprocess.check_output(
                ["git", "show", ORIGINAL + ":" + file], cwd=repo
            ),
            "Original raw file changed",
        )
    refs(evidence)
    refs(json.loads((native_root / "water-support.json").read_bytes()))
    versions = {v["collector_sha256"]: v for v in evidence["collector_versions"]}
    for digest, version in versions.items():
        require(sha(raw(version["raw_source"])) == digest, "Collector binding changed")
    rows = {k: [] for k in KINDS}
    candidates, receipts, attempts, completed = [], {}, [], []
    for digest, artifact in artifacts.items():
        prediction = predicted[digest]
        inputs = {k: prediction["inputs_sha256"][k] for k in INPUTS}
        risk = json.loads(raw(artifact["water_risk_evidence"]))
        require(
            {k: risk["inputs_sha256"][k] for k in INPUTS} == inputs,
            "Physical inputs changed",
        )
        # Read retained CPU provenance, including the actual reproduced package.
        cpu = json.loads(raw(artifact["cpu_evidence"]))["cases"][artifact["slug"]]
        require(cpu["generation"]["package"]["sha256"] == digest, "CPU package differs")
        cpu_links = [link(artifact["cpu_evidence"])]
        if artifact["reproduction_evidence"]:
            ref = artifact["reproduction_evidence"]
            reproduction = json.loads(raw(ref))["cases"][artifact["slug"]]
            require(
                reproduction["baseline_comparison"]["package_unchanged"] is True
                and reproduction["generation"]["package"]["sha256"] == digest,
                "CPU reproduction changed",
            )
            cpu_links.append(link(ref))
        runtime_attempts = []
        for attempt in artifact["attempts"]:
            ref = attempt["observation_evidence"]
            o = json.loads(raw(ref))
            require(o["artifact_sha256"] == digest, "Observation package changed")
            attempts.append(
                {
                    "artifact_sha256": digest,
                    "attempt_id": attempt["attempt_id"],
                    "schema": o.get("schema", 1),
                    "completed": o.get("completed") is True,
                    "observed_at": o["observed_at"],
                    "finished_at": o["finished_at"],
                    "error": o.get("error"),
                    "native_evidence": [
                        link(r) for r in attempt["native_evidence"].values()
                    ],
                    "evidence": [link(ref)],
                }
            )
            if o.get("schema") == 2 and o.get("completed") is True:
                runtime_attempts.append((attempt, o))
        require(
            len(runtime_attempts) <= 1, "Repeated runtime observations cannot be pooled"
        )
        if not runtime_attempts:
            continue
        attempt, o = runtime_attempts[0]
        version = versions[o["collector_sha256"]]
        require(
            o["collector_sources"]["connections.py"] == sha(raw(version["raw_source"])),
            "Collector differs",
        )
        for name, ref in version["dependencies"].items():
            require(o["collector_sources"][name] == sha(raw(ref)), "Helper differs")
        context = runtime_context(
            o, lambda name: sha((repo / "tools/cs1-harness/mod" / name).read_bytes())
        )
        network_ref = attempt["native_evidence"]["networks.json"]
        segments = {s["id"]: s for s in json.loads(raw(network_ref))["segments"]}
        common = {
            "study": STUDY,
            "square": prediction["square"],
            "artifact_sha256": digest,
            "source_sha": artifact["exporter_source_sha"],
            "observed_at": o["finished_at"],
            "observation_started_at": o["observed_at"],
            "evidence": [link(attempt["observation_evidence"]), link(network_ref)],
            "prediction_model": frozen["model"],
            "prediction_frozen_at": frozen["frozen_at"],
        }
        completed.append(
            {
                "artifact_sha256": digest,
                "attempt_id": attempt["attempt_id"],
                "requested_capabilities": o["requested_capabilities"],
            }
        )
        for kind in KINDS:
            paths = [p for p in o["paths"] if p["request"]["capability"] == kind]
            for p in paths:
                require(
                    p["mode"]
                    == {"road": "car", "rail": "train", "ship": "ship", "air": "plane"}[
                        kind
                    ],
                    "Vehicle mode differs",
                )
                for key in ("from", "to"):
                    segment, lane, _ = p["request"][key]
                    require(
                        segment in segments
                        and any(
                            entry["index"] == lane
                            for entry in segments[segment]["lanes"]
                        ),
                        "Unknown segment/lane",
                    )
            generic = [p for p in paths if p["request"]["name"] == "outside-to-outside"]
            if kind in o["requested_capabilities"]:
                coverage = o["candidate_coverage"][kind]
                require(
                    len(generic)
                    == coverage["planned_requests"]
                    <= min(coverage["candidate_requests"], coverage["request_limit"]),
                    "Bounded coverage differs",
                )
            require(
                kind in o["requested_capabilities"] or not paths,
                "Unexpected capability requests",
            )
            witnesses = [
                p for p in generic if distinct_boundary(p, segments) and successful(p)
            ]
            controls, control_requests = paired_controls(generic, segments)
            rows[kind].append(
                {
                    **common,
                    "oracle": "native_two_edge_witness",
                    "predicted": prediction["predictions"][kind]["predicted"],
                    "observed": True if witnesses else None,
                    "observation_status": "witness" if witnesses else "unknown",
                    "successful_requests": [p["request"] for p in witnesses],
                    "claim": "One targeted v2 package/capability cell, not an independent vote alongside v1. Finite failures remain Unknown.",
                }
            )
            rows[kind].append(
                {
                    **common,
                    "oracle": "targeted_v2_probe_diagnostics",
                    "predicted": None,
                    "observed": None,
                    "requested": kind in o["requested_capabilities"],
                    "candidate_coverage": o["candidate_coverage"].get(kind),
                    "outcomes": [
                        {
                            "request": p["request"],
                            "complete": p.get("result", {}).get("complete"),
                            "success": p.get("result", {}).get("success"),
                            "released": p.get("result", {}).get("released"),
                            "error": p.get("error"),
                        }
                        for p in paths
                    ],
                }
            )
            if kind != "ship" or not all(controls.values()) or not witnesses:
                continue
            require(
                prediction["predictions"][kind]["predicted"] is True,
                "Control witness contradicts frozen candidate",
            )
            ref = attempt["observation_evidence"]
            receipt = {
                "schema": 1,
                "scope": SCOPE,
                "artifact_sha256": digest,
                "inputs_sha256": inputs,
                "native_context": context,
                "observation_sha256": ref["sha256"],
                "observed_at": o["finished_at"],
                "observation_started_at": o["observed_at"],
                "source_commit": SOURCE,
                "evidence": common["evidence"],
                "limitations": LIMITS,
            }
            receipt_bytes = encoded(receipt)
            receipt_sha = sha(receipt_bytes)
            file = f"tools/map-factory/capability-evidence/runtime-identities/{receipt_sha}.json"
            receipts[file] = receipt_bytes
            candidates.append(
                {
                    "study": STUDY,
                    "capability": kind,
                    "scope": SCOPE,
                    "artifact_sha256": digest,
                    "inputs_sha256": inputs,
                    "native_context": context,
                    "observation_sha256": ref["sha256"],
                    "observed_at": o["finished_at"],
                    "controls": controls,
                    "control_requests": control_requests,
                    "runtime_identity_evidence": {"file": file, "sha256": receipt_sha},
                    "blocked_by": ["independent_review_pending"],
                    "evidence": [
                        *common["evidence"],
                        *cpu_links,
                        link(version["raw_source"]),
                        *[link(r) for r in version["dependencies"].values()],
                    ],
                    "limitations": LIMITS,
                }
            )
    study = {
        "source_commit": SOURCE,
        "source_url": BASE + PREFIX + "README.md",
        "original_source_commit": ORIGINAL,
        "evidence_sha256": sha(evidence_raw),
        "selection_sha256": sha(selection_raw),
        "predictions_file": PREDICTIONS,
        "predictions_sha256": FREEZE_SHA,
        "projection_tool_file": "tools/map-factory/integrate_outside_v2.py",
        "projection_tool_sha256": sha(Path(__file__).read_bytes()),
        "prediction_model": frozen["model"],
        "prediction_source_sha": frozen["model_source_head"],
        "method": "Targeted v2 follow-up is separate from immutable v1. One cell per package/capability; no pooled repeat votes. Ship candidates require one reciprocal pair with four complete exact-endpoint controls.",
        "limits": LIMITS,
        "native_rows_retained_upstream": len(evidence["rows"]),
        "projection_raw_files_checked": len(checked),
        "original_rows_fields_preserved": len(original["rows"]),
        "original_raw_files_preserved": len(original_files),
        "raw_files_sha256": checked,
        "attempts": attempts,
        "runtime_bound_observations": completed,
        "qualification_candidates": candidates,
    }
    return rows, study, receipts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native_root", type=Path)
    args = parser.parse_args()
    rows, study, receipts = project(args.native_root)
    ledger_path = ROOT / "capabilities.json"
    ledger = json.loads(ledger_path.read_bytes())
    require(
        ledger["evidence_studies"]["outside-v1"]["source_commit"] == ORIGINAL,
        "Original v1 binding changed",
    )
    require(
        not ledger["native_path_certificates"],
        "Importer cannot change active certificates",
    )
    ledger["evidence_studies"][STUDY] = study
    for cap in ledger["capabilities"]:
        if cap["id"] in rows:
            cap["game_agreement"] = [
                r for r in cap["game_agreement"] if r.get("study") != STUDY
            ] + rows[cap["id"]]
    for file, value in receipts.items():
        path = ROOT / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    ledger_path.write_bytes(encoded(ledger))
    print(
        json.dumps(
            {
                "candidates": len(study["qualification_candidates"]),
                "receipts": len(receipts),
                "witnesses": {
                    k: Counter(r["observed"] is True for r in v)[True]
                    for k, v in rows.items()
                },
                "active_certificates": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
