"""Project the reviewed PL-1215 directed-rail study into the one capability ledger.

Evidence only. This reads the exact archived raw bytes, manifests, freezes, selection,
protocols and results of the accepted native study and writes a deterministic projection
plus the ledger's rail study binding. It never runs the game, a collector, an archived
tool, a predictor, a scorer or a judge, and it never activates a certificate.

The four ``ship`` certificates, the frozen v3/start/water studies, the physical writers
and the historical native qualification contracts are not touched.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = "tools/map-factory/capability-evidence"
PREFIX = f"{EVIDENCE}/"

# Accepted native publication (PR78) and its base. A later merge commit is a different
# object and must never be substituted here.
SOURCE_COMMIT = "1a0e45c65745ba5f05cf22f947da2e88fed25277"
SOURCE_BASE = "29b095475ba2f93c7e918fefc08c736493670304"
SOURCE_ISSUE = "01a1fe64-7010-7533-bf2d-34ed498286c7"
SOURCE_THREAD = "01a1fec0-0768-7b0d-96fe-025862c1c155"
REVIEW_PASS = "01a1fecc-f7d3-78f0-a858-6552d25e4f00"
REVIEW_ADDENDUM = "01a1fed0-5a2b-759d-b58e-372e2d70d029"

STUDY = "directed-rail-v3"
PROJECTION = f"{PREFIX}rail-study.json"
PROJECTION_TOOL = "tools/map-factory/integrate_rail_evidence.py"
PREDICTIONS = f"{PREFIX}pl1119-v3-predictions.json"
PREDICTIONS_SHA = "1f2db0bb64e62965137cce05ffe0cea7bf8aa339c2a8a9e9560fafe4ef64ae03"
BASEMAPS = "tools/map-factory/survey/basemaps.json"

# Read-only native source closure. The native harness is NOT installed into the parent
# stack; these are evidence bytes so the frozen hashes can be re-checked without it.
SOURCE_CLOSURE = f"{PREFIX}rail-native-sources"
SOURCE_MANIFEST = f"{SOURCE_CLOSURE}/manifest.json"

SECTIONS = ("rail-v1", "rail-v2", "rail-v3", "rail-v3-followup-1")
# Read-only documents served beside the page; their bytes are bound like raw receipts.
DOCUMENTS = (
    "rail-v1/README.md",
    "rail-v3/README.md",
    "rail-v3/REPRODUCE.md",
    "rail-v3/RESULTS.md",
    "rail-v3/selection.json",
    "rail-v3-followup-1/README.md",
    "rail-v3-followup-1/RESULTS.md",
    "rail-v3-followup-1/cleanup-audit.json",
    "rail-v3-followup-1/strict-verifier-failure.txt",
    "rail-v3-followup-1/verification.json",
)
FINAL_SECTIONS = ("rail-v3", "rail-v3-followup-1")
EARLIER_SECTIONS = ("rail-v1", "rail-v2")
OPENING_DIRS = (
    f"{PREFIX}rail-v3/raw",
    f"{PREFIX}rail-v3-followup-1/raw",
)

PROTOCOL = {
    "category": "All",
    "diagnostics": "midpoint per selected directed pair; reverse first boundary without changing lanes "
    "(not assumed invalid); Train query from first boundary source to smallest Car-but-not-Train "
    "segment/lane at offset128 (invalid vehicle pair)",
    "entry": "NewGameFromMap/noWorkshop/non-inverted/mods-enabled",
    "id": "PL-1215-directed-rail-v3",
    "lane_types": ["Vehicle", "TransportVehicle", "CargoVehicle"],
    "max_length": 100000,
    "order": "distinct-edge first, then lexicographic from/to [segment,lane,offset]; "
    "first 128 boundary requests",
    "prediction": "direction-compatible candidates, not predicted native successes; all finite misses remain Unknown",
    "query": "NetworkOps.path_start mode=train; existing CreatePath overload",
    "random_seed": 857,
    "rule": "source away from outside node, destination towards it; swap direction for segment Invert; "
    "test native Forward/Backward bits directly, not composite Avoid enum values or display names",
    "scope": "sampled_native_lane_paths_at_opening; file identity, not memory attestation or strict no-mods",
    "vehicle": "Train",
}
LIMIT = 128
DLC_PANEL_ERRORS = [
    "Error: Assembly resolution failure. No assembly named 'ServicePointGroupPanel' was found.  [Serialization]",
    "Error: Assembly resolution failure. No assembly named 'HotelGroupPanel' was found.  [Serialization]",
    "Error: Assembly resolution failure. No assembly named 'RaceGroupPanel' was found.  [Serialization]",
]
LIMITS = (
    "Reviewed directed-rail native path study, not accuracy, blind holdout, geographic negative or a "
    "place-level rail promise. Selected requests are a bounded sample at opening in this exact loaded-file "
    "and plugin context; a failed query or an empty candidate list is Unknown, never absence. Pittsburgh's "
    "fixed cap left 112 candidates unqueried and Boston's two same-edge successes are not distinct-edge "
    "witnesses. The four positive cells agree with the preserved frozen-v3 rail candidates by exact artifact "
    "hash and CPU receipt lineage; that is positive-witness agreement on an already observed cohort, not "
    "accuracy. Native raw receipts bind CRP bytes, not freshly rehashed prepared inputs: the three input "
    "hashes are reused frozen lineage. File identity is not in-memory code attestation or strict no-mods; "
    "dynamic assemblies are excluded and three DLC-panel errors are retained at every opening. "
    "enabled_mod_count=0 does not mean unloaded/no mods: CitiesBridge, the harness and built-ins are loaded. "
    "No rail service, train spawning, station/port, editor/gameplay parity, sustained gameplay or human play "
    "is established. No native rail certificate is issued and no live Yes is claimed."
)
METHOD = (
    "Two fixed stock controls establish that this exact directed literal-boundary Train query can return a "
    "complete, released path whose first and last positions are the requested Outside offsets, that both "
    "controls carry reciprocal successes, and that a Train query to an explicit Car-but-not-Train lane is "
    "rejected. Only then does the unchanged nine-package geographic cohort run. Each opening freezes the full "
    "native network snapshot, endpoint/lane inventory and ordered requests before any query, then binds the "
    "actual executable and every resolved loaded-assembly file through the rendering process's namespace "
    "PID/start. Selected failures and unqueried candidates stay Unknown. Earlier selector revisions and "
    "repeats are retained as separate diagnostics, never pooled votes."
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(path):
    return sha(Path(path).read_bytes())


def read_json(path):
    return json.loads(Path(path).read_text())


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def decompress(section, relative):
    path = ROOT / PREFIX / section / (relative + ".gz")
    require(path.exists(), f"missing archived raw file {section}/{relative}")
    raw = path.read_bytes()
    return raw, gzip.decompress(raw)


def manifest(section):
    value = read_json(ROOT / PREFIX / section / "integrity.json")
    require(set(value) >= {"files"}, f"{section}: incomplete manifest")
    return value


def load_manifest_files(section):
    """Validate every archived file twice: compressed bytes and decompressed bytes."""
    records = []
    for record in manifest(section)["files"]:
        raw, plain = decompress(section, record["path"])
        require(
            sha(raw) == record["gzip_sha256"],
            f"{section}: compressed bytes changed for {record['path']}",
        )
        require(
            len(plain) == record["bytes"],
            f"{section}: decompressed length changed for {record['path']}",
        )
        require(
            sha(plain) == record["sha256"],
            f"{section}: decompressed bytes changed for {record['path']}",
        )
        records.append(
            {
                "section": section,
                "path": f"{PREFIX}{section}/{record['path']}.gz",
                "gzip_sha256": record["gzip_sha256"],
                "sha256": record["sha256"],
                "bytes": record["bytes"],
            }
        )
    return records


def selection_json():
    """The frozen pre-launch selection (not part of the raw receipt manifest)."""
    return read_json(ROOT / PREFIX / "rail-v3/selection.json")


def tokens(value):
    return set(value.split(", "))


def boundary_side(point):
    x, _, z = point
    return (
        ("east" if x > 0 else "west")
        if abs(x) > abs(z)
        else ("north" if z > 0 else "south")
    )


def endpoints(networks):
    """The directed-rail endpoint inventory, re-derived from the network snapshot."""
    directions = networks["direction_enum_values"]
    require(
        {
            k: directions[k]
            for k in ("Forward", "Backward", "AvoidForward", "AvoidBackward")
        }
        == {"Forward": 1, "Backward": 2, "AvoidForward": 11, "AvoidBackward": 7},
        "native direction enum values changed",
    )
    ends = []
    for segment in networks["segments"]:
        train = [
            lane for lane in segment["lanes"] if "Train" in tokens(lane["vehicle"])
        ]
        for key, offset in (("start", 0), ("end", 255)):
            flags = tokens(segment[key + "_flags"])
            if not train or "Outside" not in flags:
                continue
            lanes = sorted(train, key=lambda lane: lane["index"])
            for lane in lanes:
                require(
                    {
                        "direction",
                        "direction_bits",
                        "forward",
                        "backward",
                        "type",
                        "category",
                        "id",
                        "flags",
                    }
                    <= set(lane),
                    "incomplete native lane inventory",
                )
                require(
                    lane["forward"]
                    == bool(lane["direction_bits"] & directions["Forward"])
                    and lane["backward"]
                    == bool(lane["direction_bits"] & directions["Backward"]),
                    "normalized lane direction differs from native bits",
                )
            ends.append(
                {
                    "edge": boundary_side(segment["a" if key == "start" else "b"]),
                    "lanes": lanes,
                    "node": segment[key],
                    "node_flags": segment[key + "_flags"],
                    "offset": offset,
                    "roles": [
                        role for role in flags if role in {"OneWayIn", "OneWayOut"}
                    ],
                    "segment": segment["id"],
                    "segment_flags": segment["flags"],
                }
            )
    return sorted(ends, key=lambda end: (end["segment"], end["node"], end["offset"]))


def compatible(end, lane, *, source):
    if not tokens(lane["type"]) & set(PROTOCOL["lane_types"]):
        return False
    forward = (end["offset"] == 0) == source
    if "Invert" in tokens(end["segment_flags"]):
        forward = not forward
    return lane["forward" if forward else "backward"]


def derive_plan(networks):
    """The frozen enumeration: this is checked against the opening's own query freeze."""
    ends = endpoints(networks)
    boundary = []
    for a, b in itertools.permutations(ends, 2):
        if a["segment"] == b["segment"] or a["node"] == b["node"]:
            continue
        for lane_a in a["lanes"]:
            if not compatible(a, lane_a, source=True):
                continue
            for lane_b in b["lanes"]:
                if not compatible(b, lane_b, source=False):
                    continue
                boundary.append(
                    {
                        "capability": "rail",
                        "name": "directed-outside-to-outside",
                        "position_kind": "boundary",
                        "diagnostic": False,
                        "endpoint_edges": [a["edge"], b["edge"]],
                        "from": [a["segment"], lane_a["index"], a["offset"]],
                        "to": [b["segment"], lane_b["index"], b["offset"]],
                    }
                )
    boundary.sort(
        key=lambda row: (
            row["endpoint_edges"][0] == row["endpoint_edges"][1],
            row["from"],
            row["to"],
        )
    )
    requests = []
    for row in boundary[:LIMIT]:
        requests.append(row)
        requests.append(
            {
                **row,
                "position_kind": "midpoint",
                "diagnostic": True,
                "from": [row["from"][0], row["from"][1], 128],
                "to": [row["to"][0], row["to"][1], 128],
            }
        )
    if boundary:
        row = boundary[0]
        requests.append(
            {
                **row,
                "name": "reversed-positions-diagnostic",
                "diagnostic": True,
                "from": row["to"],
                "to": row["from"],
                "endpoint_edges": row["endpoint_edges"][::-1],
            }
        )
        invalid = sorted(
            [segment["id"], lane["index"], 128]
            for segment in networks["segments"]
            for lane in segment["lanes"]
            if "Car" in tokens(lane["vehicle"])
            and "Train" not in tokens(lane["vehicle"])
        )
        if invalid:
            requests.append(
                {
                    **row,
                    "name": "invalid-train-to-car-lane",
                    "position_kind": "invalid_vehicle_pair",
                    "diagnostic": True,
                    "from": row["from"],
                    "to": invalid[0],
                    "endpoint_edges": [row["endpoint_edges"][0], None],
                }
            )
    return {
        "endpoints": ends,
        "candidate_boundary_count": len(boundary),
        "boundary_limit": LIMIT,
        "requests": requests,
    }


def classify(row):
    result = row.get("result", {})
    if not result.get("complete") or not result.get("released"):
        return "Unknown"
    if not result.get("success"):
        return "selected_query_failure"
    positions = result.get("positions", [])
    request = row["request"]
    if (
        not positions
        or positions[0] != request["from"]
        or positions[-1] != request["to"]
    ):
        return "returned_endpoint_mismatch"
    return "exact_path_success"


def validate_path_result(row):
    """Every returned position is an exact native [segment, lane, 0-or-255] triple."""
    result = row["result"]
    positions = result.get("positions")
    require(isinstance(positions, list), "path result is not a position list")
    if not result.get("success"):
        require(positions == [], "rejected path reported positions")
        return
    require(positions, "successful path reported no positions")
    for position in positions:
        require(
            isinstance(position, list) and len(position) == 3,
            "returned position is not [segment, lane, offset]",
        )
        require(
            isinstance(position[0], int) and isinstance(position[1], int),
            "ambiguous returned segment/lane",
        )
        require(
            isinstance(position[2], int) and 0 <= position[2] <= 255,
            "ambiguous returned lane offset",
        )
    request = row["request"]
    if request["position_kind"] == "boundary":
        require(
            request["from"][2] in (0, 255) and request["to"][2] in (0, 255),
            "boundary request does not use exact 0-or-255 endpoints",
        )
    require(
        positions[0] == request["from"],
        "first returned position is not the requested source",
    )
    require(
        positions[-1] == request["to"],
        "last returned position is not the requested destination",
    )


def validate_identity(identity, build, label, *, opening):
    require(
        identity.get("build_matches") is True,
        f"{label}: build does not match the running files",
    )
    require(
        identity.get("unresolved_loaded_assemblies") == [],
        f"{label}: unresolved loaded assembly",
    )
    require(
        isinstance(identity.get("excluded_dynamic_assemblies"), list),
        f"{label}: dynamic exclusions not stated",
    )
    status = identity.get("status", {})
    require(status.get("plugins"), f"{label}: plugin flags missing")
    require(
        {"errors", "error_count", "enabled_mod_count"} <= set(status),
        f"{label}: plugin/error facts missing",
    )
    require(
        {"host_pid", "process_start_ticks", "executable", "observed_at"}
        <= set(identity),
        f"{label}: identity missing",
    )
    require(
        identity["executable"]["sha256"] == build["game_executable_sha256"],
        f"{label}: executable changed",
    )
    assemblies = identity["assemblies"]
    require(
        len({a["path"] for a in assemblies}) == len(assemblies),
        f"{label}: duplicate assembly path",
    )
    require(
        len({a["name"] for a in assemblies}) == len(assemblies),
        f"{label}: duplicate assembly name",
    )
    for assembly in assemblies:
        require(
            Path(assembly["path"]).is_absolute(), f"{label}: relative assembly path"
        )
        require(len(assembly["sha256"]) == 64, f"{label}: bad assembly hash")
    loaded = {Path(a["path"]).name: a["sha256"] for a in assemblies}
    for name, expected in {
        **build["game_assemblies"],
        "Cs1Harness.dll": build["dll_sha256"],
    }.items():
        require(
            loaded.get(name) == expected,
            f"{label}: loaded assembly missing or differs from build: {name}",
        )
    require(
        type(identity["host_pid"]) is int and identity["host_pid"] > 0,
        f"{label}: ambiguous host PID",
    )
    require(
        type(identity["namespace_pid"]) is int and identity["namespace_pid"] > 0,
        f"{label}: ambiguous namespace PID",
    )
    require(
        str(identity["process_start_ticks"]).isdigit(),
        f"{label}: ambiguous process start",
    )
    for flags in (identity["launch_args"], identity["command_line"]):
        require(
            "--noWorkshop" in flags and "--disableMods" not in flags,
            f"{label}: actual launch flags differ",
        )
    require(
        identity["command_line"][0] == identity["executable"]["path"],
        f"{label}: executable path differs",
    )
    errors = status["errors"]
    require(
        status["error_count"] == len(errors),
        f"{label}: error_count does not match the reported errors",
    )
    if opening:
        require(
            status["error_count"] == 3, f"{label}: reported native error count changed"
        )
        require(
            errors == DLC_PANEL_ERRORS,
            f"{label}: DLC-panel errors changed or were waived",
        )
    else:
        require(
            status["error_count"] == 0 and errors == [],
            f"{label}: launch-time errors changed",
        )
    require(status["enabled_mod_count"] == 0, f"{label}: enabled_mod_count changed")
    names = {plugin["name"]: plugin for plugin in status["plugins"]}
    for name, builtin in (
        ("HardMode", True),
        ("CitiesBridge", False),
        ("Cs1Harness", False),
    ):
        require(name in names, f"{label}: plugin flag missing for {name}")
        require(
            names[name]["builtin"] is builtin,
            f"{label}: plugin ownership flag changed for {name}",
        )
    return {
        "host_pid": identity["host_pid"],
        "namespace_pid": identity["namespace_pid"],
        "process_start_ticks": str(identity["process_start_ticks"]),
        "executable_sha256": identity["executable"]["sha256"],
        "assemblies": len(assemblies),
        "enabled_mod_count": status["enabled_mod_count"],
        "error_count": status["error_count"],
        "errors": errors,
        "plugins": status["plugins"],
        "dynamic_exclusions": identity["excluded_dynamic_assemblies"],
        "build_matches": True,
        "file_identity_only": True,
    }


def validate_context(observation):
    launch = observation["launch_runtime_identity"]
    opening = observation["runtime_identity"]
    build = observation["build_receipt"]
    require(
        (launch["host_pid"], str(launch["process_start_ticks"]))
        == (opening["host_pid"], str(opening["process_start_ticks"])),
        "launch/opening PID or start differs",
    )
    require(
        observation["observed_at"]
        <= launch["observed_at"]
        <= observation["native_context"]["observed_at"]
        <= opening["observed_at"]
        <= observation["finished_at"],
        "runtime timestamps out of order",
    )
    context = observation["native_context"]
    require(
        context["update_mode"] == "NewGameFromMap", "native entry is not NewGameFromMap"
    )
    require(context["invert_traffic"] == "False", "native traffic is inverted")
    require(context["no_workshop"] is True, "workshop was not disabled")
    require(context["mods_enabled"] is True, "mods were not enabled")
    session = observation["session"]
    require(
        session["map"]["sha256"] == observation["artifact_sha256"],
        "installed package changed",
    )
    require(session["mod_sha256"] == build["dll_sha256"], "installed mod changed")
    require(
        session["runtime_identity"] == opening, "session runtime differs from opening"
    )
    require(
        {row["pid"] for row in session["game_gpu"]} == {opening["host_pid"]},
        "rendering PID differs",
    )
    require(
        {"game", "steam_instances", "units_active"} <= set(session["cleanup"]),
        "cleanup facts missing",
    )
    built = validate_identity(opening, build, "opening", opening=True)
    validate_identity(launch, build, "launch", opening=False)
    return built


def summarize_opening(section, relative, selection, selection_sha):
    """Validate one archived opening and return its literal result summary."""
    _, plain = decompress(section, relative + "/observation.json")
    observation = json.loads(plain)
    attempt = Path(relative).name
    summary = {
        "attempt": attempt,
        "raw_path": relative,
        "section": section,
        "observed_at": observation.get("observed_at"),
        "finished_at": observation.get("finished_at"),
        "artifact_sha256": observation["artifact_sha256"],
        "completed": observation.get("completed") is True,
        "error": observation.get("error"),
        "context_bound": False,
        "identity": None,
        "cleanup": observation.get("session", {}).get("cleanup"),
        "boundary_successes": 0,
        "distinct_edge_boundary_successes": 0,
        "same_edge_boundary_successes": 0,
        "boundary_failures": 0,
        "boundary_unknown": 0,
        "diagnostics": [],
    }
    if "runtime_identity" not in observation:
        # A queue denial or other pre-launch stop: retained, never erased or retried.
        require(
            summary["completed"] is False,
            f"{relative}: completed opening lacks a runtime identity",
        )
        require(
            observation.get("error"),
            f"{relative}: unlaunched attempt has no recorded error",
        )
        require(
            not observation.get("paths"),
            f"{relative}: unlaunched attempt reported queries",
        )
        require(
            "build_receipt" not in observation,
            f"{relative}: unlaunched attempt carries a build receipt",
        )
        return observation, summary
    build = selection["build_receipt"]
    require(observation["schema"] == 2, f"{relative}: observation schema changed")
    require(observation["protocol"] == PROTOCOL, f"{relative}: protocol changed")
    require(
        observation["collector_sources"]
        == {
            "connections.py": selection["sources"][
                "tools/cs1-harness/cs1_harness/connections.py"
            ],
            "runtime_identity.py": selection["sources"][
                "tools/cs1-harness/cs1_harness/runtime_identity.py"
            ],
        }
        and observation["collector_sha256"]
        == observation["collector_sources"]["connections.py"],
        f"{relative}: collector source binding changed",
    )
    require(
        observation["build_receipt"] == build,
        f"{relative}: build receipt differs from selection freeze",
    )
    summary["context_bound"] = True
    summary["identity"] = validate_context(observation)

    freeze_relative = relative + "/query-freeze.json"
    has_freeze = (ROOT / PREFIX / section / (freeze_relative + ".gz")).exists()
    if not has_freeze:
        require(
            summary["completed"] is False,
            f"{relative}: completed opening lacks a query freeze",
        )
        return observation, summary
    _, frozen_plain = decompress(section, freeze_relative)
    frozen = json.loads(frozen_plain)
    _, networks_plain = decompress(section, relative + "/networks.json")
    networks = json.loads(networks_plain)
    require(
        observation.get("query_freeze_sha256") == sha(frozen_plain),
        f"{relative}: query freeze hash is unbound",
    )
    require(
        frozen["selection_sha256"] == selection_sha,
        f"{relative}: query freeze uses another selection",
    )
    require(
        frozen["artifact_sha256"] == observation["artifact_sha256"],
        f"{relative}: query freeze uses another package",
    )
    require(
        frozen["runtime_identity"] == observation["runtime_identity"],
        f"{relative}: query freeze uses another process",
    )
    require(
        frozen["protocol"] == PROTOCOL, f"{relative}: query freeze protocol changed"
    )
    require(
        frozen["networks_sha256"] == sha(networks_plain),
        f"{relative}: query freeze network snapshot is unbound",
    )
    derived = derive_plan(networks)
    require(
        frozen["plan"] == derived,
        f"{relative}: frozen directed enumeration is not reproducible",
    )
    coverage = observation.get("candidate_coverage", {}).get("rail", {})
    require(
        coverage.get("candidate_boundary_requests")
        == derived["candidate_boundary_count"]
        and coverage.get("planned_boundary_requests")
        == min(LIMIT, derived["candidate_boundary_count"])
        and coverage.get("diagnostic_requests")
        == sum(1 for r in derived["requests"] if r["diagnostic"])
        and coverage.get("boundary_limit") == LIMIT,
        f"{relative}: candidate coverage is unbound",
    )
    rows = observation.get("paths", [])
    require(
        [row["request"] for row in rows] == derived["requests"][: len(rows)],
        f"{relative}: queries left the frozen prefix",
    )
    require(
        bool(observation.get("completed")) == (len(rows) == len(derived["requests"])),
        f"{relative}: completed opening omitted frozen requests or ran extras",
    )
    previous = None
    for index, row in enumerate(rows):
        require(row.get("mode") == "train", f"{relative}: query mode changed")
        require(
            row.get("submitted_at", "") >= frozen["frozen_at"],
            f"{relative}: query predates the inventory freeze",
        )
        require(
            row.get("submitted_at", "") >= selection["frozen_at"],
            f"{relative}: query predates selection freeze",
        )
        require(
            previous is None or row["submitted_at"] >= previous,
            f"{relative}: request submission order changed",
        )
        previous = row["submitted_at"]
        validate_path_result(row)
        outcome = classify(row)
        request = derived["requests"][index]
        if request["diagnostic"]:
            summary["diagnostics"].append(
                {
                    "name": request["name"],
                    "position_kind": request["position_kind"],
                    "outcome": outcome,
                }
            )
        elif outcome == "exact_path_success":
            summary["boundary_successes"] += 1
            if request["endpoint_edges"][0] != request["endpoint_edges"][1]:
                summary["distinct_edge_boundary_successes"] += 1
            else:
                summary["same_edge_boundary_successes"] += 1
        elif outcome == "selected_query_failure":
            summary["boundary_failures"] += 1
        else:
            summary["boundary_unknown"] += 1
    summary["selected_boundary"] = sum(
        1 for r in derived["requests"] if not r["diagnostic"]
    )
    summary["candidate_boundary_count"] = derived["candidate_boundary_count"]
    summary["unqueried_boundary_candidates"] = max(
        0, derived["candidate_boundary_count"] - LIMIT
    )
    summary["missing_reason"] = (
        "no_pair_or_directed_lane" if not derived["requests"] else None
    )
    summary["query_frozen_at"] = frozen["frozen_at"]
    return observation, summary


def validate_cleanup(all_observations, all_summaries):
    """Recheck the later audit's complete coverage; never trust an empty `games` array."""
    audit = read_json(ROOT / PREFIX / "rail-v3-followup-1/cleanup-audit.json")
    require(
        audit["initial_integrity_sha256"]
        == digest(ROOT / PREFIX / "rail-v3/integrity.json"),
        "cleanup audit refers to different initial bytes",
    )
    require(
        audit["followup_integrity_sha256"]
        == digest(ROOT / PREFIX / "rail-v3-followup-1/integrity.json"),
        "cleanup audit refers to different continuation bytes",
    )
    require(
        audit["audit_source_sha256"]
        == digest(ROOT / PREFIX / "rail-v3-followup-1/review.py"),
        "cleanup audit source changed",
    )
    require(
        audit["scope"]
        == "read-only later exit audit; no process stopped; foreign Steam instances remain untouched",
        "cleanup audit scope changed",
    )
    launched = [
        observation for observation in all_observations if observation.get("session")
    ]
    # The audit must name every observation byte, launched or not, and no other.
    observed = {}
    for _, summary in all_summaries:
        observed[f"{summary['raw_path']}/observation.json"] = sha(
            decompress(summary["section"], f"{summary['raw_path']}/observation.json")[1]
        )
    require(
        set(audit["observation_sha256"]) == set(observed),
        "cleanup audit omits or invents an observation",
    )
    require(
        audit["observation_sha256"] == observed,
        "cleanup audit refers to different observation bytes",
    )
    # Every recorded game process, by PID and start ticks, is covered exactly once.
    recorded = {
        (
            observation["runtime_identity"]["host_pid"],
            str(observation["runtime_identity"]["process_start_ticks"]),
        )
        for observation in launched
    }
    covered = [(row["pid"], str(row["observed_start_ticks"])) for row in audit["games"]]
    require(
        len(covered) == len(set(covered)), "cleanup audit lists a game process twice"
    )
    require(
        set(covered) == recorded,
        "cleanup audit does not cover exactly the recorded game processes",
    )
    require(
        not any(row["owned_alive"] for row in audit["games"]),
        "an owned game is still recorded alive",
    )
    require(
        all(row["current_start_ticks"] is None for row in audit["games"]),
        "a recorded game PID is still present",
    )
    # Every telemetry owner PID from the process-gpu streams is accounted for.
    owners = set()
    for section in FINAL_SECTIONS:
        for relative in telemetry_streams(section):
            _, plain = decompress(section, relative)
            for line in plain.splitlines():
                if line:
                    owners.add(json.loads(line)["owner_pid"])
    require(owners, "no telemetry owner PID was recorded")
    require(
        set(audit["collector_pids"]) == owners,
        "cleanup audit does not cover every telemetry owner",
    )
    require(
        audit["collector_pids_still_present"] == [],
        "a telemetry owner is still present",
    )
    require(
        audit["owned_monitor_pids_still_present"] == [],
        "an owned monitor is still present",
    )
    # Every teardown remainder is named, absent later and not silently waived.
    remainders = {
        instance
        for observation in launched
        for instance in observation.get("session", {})
        .get("cleanup", {})
        .get("steam_instances", [])
    }
    require(
        set(audit["reported_steam_remainders"]) == remainders,
        "audit does not name every teardown remainder",
    )
    require(
        audit["reported_steam_remainders_still_present"] == [],
        "a listed Steam remainder is still present",
    )
    require(
        not (remainders & set(audit["current_steam_instances"])),
        "a listed Steam remainder is present in the later snapshot",
    )
    # The audit postdates every observation it claims to cover.
    for observation in all_observations:
        if observation.get("finished_at"):
            require(
                audit["observed_at"] >= observation["finished_at"],
                "cleanup audit predates an observation exit",
            )
    findings = []
    for observation, summary in all_summaries:
        cleanup = observation.get("session", {}).get("cleanup")
        if cleanup is None:
            continue
        if cleanup["game"] or cleanup["units_active"]:
            raise ValueError("a game or unit remained at teardown")
        if not cleanup["steam_instances"]:
            continue
        require(
            set(cleanup["steam_instances"]) <= set(remainders),
            "unbound Steam teardown remainder",
        )
        findings.append(
            {
                "attempt": summary["attempt"],
                "raw_cleanup": cleanup,
                "later_state": "Steam listed at teardown; later audit proves listed instance absent",
            }
        )
    return {
        "audited_at": audit["observed_at"],
        "audit_source_sha256": audit["audit_source_sha256"],
        "games_covered": len(covered),
        "collector_pids": sorted(owners),
        "reported_steam_remainders": sorted(remainders),
        "remaining_steam_instances": sorted(audit["current_steam_instances"]),
        "findings": findings,
        "coverage": "every observation's game PID/start, telemetry owner PID and reported teardown remainder; "
        "audit time after every observation; other owners' Steam untouched",
        "degraded": bool(findings),
    }


def telemetry_streams(section):
    return [
        record["path"]
        for record in manifest(section)["files"]
        if record["path"].endswith("process-gpu.jsonl")
    ]


def validate_source_closure(selection):
    """The 56 frozen harness sources and 17 C# build sources, from archived bytes."""
    frozen = selection["sources"]
    expected = {}
    for original, digest_value in frozen.items():
        name = Path(original).name
        archived = f"{SOURCE_CLOSURE}/{'mod' if original.startswith('tools/cs1-harness/mod/') else 'cs1_harness'}/{name}"
        path = ROOT / archived
        require(path.exists(), f"missing archived native source {original}")
        require(
            digest(path) == digest_value,
            f"archived native source differs from the freeze: {original}",
        )
        expected[original] = {"file": archived, "sha256": digest_value}
    require(len(frozen) == 56, "frozen harness source count changed")
    build = selection["build_receipt"]["sources"]
    require(len(build) == 17, "build-source count changed")
    for name, digest_value in build.items():
        archived = f"{SOURCE_CLOSURE}/mod/{name}"
        require((ROOT / archived).exists(), f"missing archived build source {name}")
        require(
            digest(ROOT / archived) == digest_value,
            f"archived build source differs from the receipt: {name}",
        )
    require(
        {
            Path(path).name
            for path in frozen
            if path.startswith("tools/cs1-harness/mod/")
        }
        == set(build),
        "the frozen mod sources and the build receipt name different files",
    )
    return {
        "files": expected,
        "build_sources": build,
        "harness_sources": len(frozen),
        "build_source_count": len(build),
    }


def earlier_revision(section):
    records = load_manifest_files(section)
    value = manifest(section)
    return {
        "section": section,
        "retained_at": value["retained_at"],
        "selection_sha256": value["selection_sha256"],
        "verifier_sha256": value["verifier_sha256"],
        "raw_files": len(records),
        "raw_files_sha256": {record["path"]: record["sha256"] for record in records},
        "status": "separate earlier selector revision; diagnostics only, never an independent vote",
    }


def build_study():
    raw_files = []
    counts = {}
    for section in SECTIONS:
        records = load_manifest_files(section)
        counts[section] = len(records)
        raw_files.extend(records)
    require(
        counts["rail-v3"] == 33 and counts["rail-v3-followup-1"] == 50,
        "final-protocol raw file counts changed",
    )
    require(
        counts["rail-v1"] == 14 and counts["rail-v2"] == 14,
        "earlier revision raw file counts changed",
    )
    selection_path = ROOT / PREFIX / "rail-v3/selection.json"
    selection = selection_json()
    require(selection["schema"] == 1, "selection schema changed")
    require(
        selection["source_base"] == SOURCE_BASE,
        "selection source base is not the accepted one",
    )
    require(selection["protocol"] == PROTOCOL, "selection protocol changed")
    require(seed_corpus(selection), "stock corpus selection is not reproducible")
    closure = validate_source_closure(selection)
    cohort_hashes = [case["artifact_sha256"] for case in selection["cohort"]]
    require(
        len(selection["cohort"]) == 9 and len(set(cohort_hashes)) == 9,
        "cohort is not the original nine packages",
    )
    require(
        [case["slug"] for case in selection["cohort"]]
        == [
            "asheville",
            "innsbruck",
            "rio",
            "pittsburgh",
            "charleston",
            "grand-canyon",
            "hong-kong",
            "yosemite",
            "boston",
        ],
        "cohort order changed",
    )
    require(
        [control["slug"] for control in selection["controls"]]
        == ["stock-1", "stock-2"],
        "controls changed",
    )
    require(
        [control["file"] for control in selection["controls"]]
        == ["AP Asanu Beach.crp", "AP Hanami Bay.crp"],
        "fixed stock controls changed",
    )

    predictions = read_json(ROOT / PREDICTIONS)
    require(
        digest(ROOT / PREDICTIONS) == PREDICTIONS_SHA, "frozen v3 predictions changed"
    )
    require(
        predictions["model"] == "square-capabilities-v3",
        "frozen predictions use another model",
    )
    require(
        selection["original_selection_sha256"] == predictions["selection_sha256"],
        "rail cohort and frozen predictions do not name the same original selection",
    )
    predicted = {case["artifact_sha256"]: case for case in predictions["cases"]}
    require(
        set(predicted) == set(cohort_hashes),
        "frozen predictions do not cover exactly the cohort",
    )

    observations, summaries = [], []
    by_artifact = {}
    for section, root in (
        ("rail-v3", "rail-v3/raw"),
        ("rail-v3-followup-1", "rail-v3-followup-1/raw"),
    ):
        for record in manifest(section)["files"]:
            relative = record["path"]
            if not relative.endswith("/observation.json"):
                continue
            observation, summary = summarize_opening(
                section,
                relative[: -len("/observation.json")],
                selection,
                sha(selection_path.read_bytes()),
            )
            require(
                summary["artifact_sha256"]
                in set(cohort_hashes)
                | {c["artifact_sha256"] for c in selection["controls"]},
                f"{relative}: unselected package",
            )
            observations.append(observation)
            summaries.append((observation, summary))
            by_artifact.setdefault(summary["artifact_sha256"], []).append(summary)
    for control in selection["controls"]:
        attempts = by_artifact.get(control["artifact_sha256"], [])
        require(
            attempts and all(a["completed"] for a in attempts),
            f"{control['slug']}: control did not complete",
        )
    controls = []
    for control in selection["controls"]:
        attempts = by_artifact[control["artifact_sha256"]]
        require(
            len(attempts) == 1,
            f"{control['slug']}: extra control openings are not this study's votes",
        )
        summary = attempts[0]
        invalid = [
            d
            for d in summary["diagnostics"]
            if d["name"] == "invalid-train-to-car-lane"
        ]
        require(
            len(invalid) == 1 and invalid[0]["outcome"] == "selected_query_failure",
            f"{control['slug']}: invalid Train-to-car diagnostic was not rejected",
        )
        reciprocal = summary["boundary_successes"] >= 2
        require(reciprocal, f"{control['slug']}: no reciprocal directed successes")
        controls.append(
            {
                "slug": control["slug"],
                "file": control["file"],
                "artifact_sha256": control["artifact_sha256"],
                "selected_boundary": summary["selected_boundary"],
                "distinct_edge_successes": summary["distinct_edge_boundary_successes"],
                "same_edge_successes": summary["same_edge_boundary_successes"],
                "selected_failures": summary["boundary_failures"],
                "reciprocal_positives": reciprocal,
                "invalid_vehicle_pair_rejected": True,
                "observed_at": summary["observed_at"],
                "attempt": summary["attempt"],
            }
        )
    require(
        {c["artifact_sha256"] for c in controls}
        == {c["artifact_sha256"] for c in selection["controls"]},
        "control packages differ from the fixed selection",
    )
    require(
        sum(c["selected_boundary"] for c in controls) == 32,
        "stock selected request total changed",
    )
    require(
        sum(c["distinct_edge_successes"] for c in controls) == 16,
        "stock distinct-edge success total changed",
    )

    cohort = []
    for case in selection["cohort"]:
        attempts = by_artifact.get(case["artifact_sha256"], [])
        require(attempts, f"{case['slug']}: no opening")
        completed = [a for a in attempts if a["completed"]]
        rows = []
        for attempt in attempts:
            rows.append(
                {
                    "attempt": attempt["attempt"],
                    "observed_at": attempt["observed_at"],
                    "finished_at": attempt["finished_at"],
                    "completed": attempt["completed"],
                    "error": attempt["error"],
                    "selected_boundary": attempt.get("selected_boundary", 0),
                    "distinct_edge_successes": attempt[
                        "distinct_edge_boundary_successes"
                    ],
                    "same_edge_successes": attempt["same_edge_boundary_successes"],
                    "selected_failures": attempt["boundary_failures"],
                    "unqueried_boundary_candidates": attempt.get(
                        "unqueried_boundary_candidates", 0
                    ),
                    "missing_reason": attempt.get("missing_reason"),
                    "query_frozen_at": attempt.get("query_frozen_at"),
                    "identity": attempt["identity"],
                    "cleanup": attempt["cleanup"],
                    "diagnostics": attempt["diagnostics"],
                }
            )
        frozen_case = predicted[case["artifact_sha256"]]
        distinct = sum(a["distinct_edge_boundary_successes"] for a in completed)
        cohort.append(
            {
                "slug": case["slug"],
                "square": case["square"],
                "artifact_sha256": case["artifact_sha256"],
                "cpu_report": case["cpu_report"],
                "cpu_report_sha256": case["cpu_report_sha256"],
                "inputs_sha256_frozen_prepared_lineage": frozen_case["inputs_sha256"],
                "normalized_input_sha256_frozen_prepared_lineage": frozen_case[
                    "normalized_input_sha256"
                ],
                "exporter_source_sha": frozen_case["exporter_source_sha"],
                "source_revision_limitation": frozen_case["source_revision_limitation"],
                "frozen_model_prediction": frozen_case["predictions"]["rail"],
                "status": "sampled_positive" if distinct else "Unknown",
                "attempts": rows,
            }
        )
    require(len(cohort) == 9, "cohort lost a case")
    totals = {
        "selected_boundary": sum(
            a["selected_boundary"]
            for c in cohort
            for a in c["attempts"]
            if a["completed"]
        ),
        "distinct_edge_successes": sum(
            a["distinct_edge_successes"]
            for c in cohort
            for a in c["attempts"]
            if a["completed"]
        ),
        "same_edge_successes": sum(
            a["same_edge_successes"]
            for c in cohort
            for a in c["attempts"]
            if a["completed"]
        ),
        "selected_failures": sum(
            a["selected_failures"]
            for c in cohort
            for a in c["attempts"]
            if a["completed"]
        ),
        "unqueried_boundary_candidates": sum(
            a["unqueried_boundary_candidates"]
            for c in cohort
            for a in c["attempts"]
            if a["completed"]
        ),
        "sampled_positive": sum(1 for c in cohort if c["status"] == "sampled_positive"),
        "unknown": sum(1 for c in cohort if c["status"] == "Unknown"),
    }
    require(totals["selected_boundary"] == 244, "cohort selected request total changed")
    require(
        totals["distinct_edge_successes"] == 9,
        "cohort distinct-edge success total changed",
    )
    require(
        totals["same_edge_successes"] == 2, "cohort same-edge success total changed"
    )
    require(totals["selected_failures"] == 233, "cohort failure total changed")
    require(
        totals["selected_boundary"]
        == totals["distinct_edge_successes"]
        + totals["same_edge_successes"]
        + totals["selected_failures"],
        "cohort totals do not add up",
    )
    require(
        totals["sampled_positive"] == 4 and totals["unknown"] == 5,
        "case status counts changed",
    )
    pittsburgh = next(c for c in cohort if c["slug"] == "pittsburgh")
    require(
        pittsburgh["attempts"][-1]["unqueried_boundary_candidates"] == 112,
        "Pittsburgh's unqueried candidate count changed",
    )
    for case in cohort:
        if case["slug"] in {"charleston", "grand-canyon", "yosemite"}:
            require(
                all(
                    a["selected_boundary"] == 0
                    and a["missing_reason"] == "no_pair_or_directed_lane"
                    for a in case["attempts"]
                ),
                f"{case['slug']}: expected no directed pair",
            )
        if case["slug"] == "boston":
            require(
                all(
                    a["same_edge_successes"] == 2
                    for a in case["attempts"]
                    if a["completed"]
                ),
                "Boston's same-edge successes are not separate",
            )

    launched = [
        observation for observation in observations if observation.get("session")
    ]
    require(len(launched) == 11, "runtime opening count changed")
    cleanup = validate_cleanup(observations, summaries)
    earlier = [earlier_revision(section) for section in EARLIER_SECTIONS]
    return {
        "schema": 1,
        "kind": "directed_rail_control_and_cohort_study",
        "study": STUDY,
        "source": {
            "publication_commit": SOURCE_COMMIT,
            "publication_base": SOURCE_BASE,
            "publication1a_pinned": True,
            "source_issue": SOURCE_ISSUE,
            "final_thread": SOURCE_THREAD,
            "independent_review_pass": REVIEW_PASS,
            "test_receipt_addendum": REVIEW_ADDENDUM,
            "publication_url": "https://github.com/frontierkodiak/region-to-skylines/pull/78",
            "source_url": f"https://github.com/frontierkodiak/region-to-skylines/tree/{SOURCE_COMMIT}/{PREFIX}rail-v3",
            "note": "publication1a is not a native observation date and does not claim the publication commit "
            "existed before collection",
        },
        "protocol": PROTOCOL,
        "frozen_predictions": {
            "file": PREDICTIONS,
            "sha256": PREDICTIONS_SHA,
            "model": predictions["model"],
            "model_source_head": predictions["model_source_head"],
            "model_source_files_sha256": predictions["model_source_files_sha256"],
            "freeze_tool_sha256": predictions["freeze_tool_sha256"],
            "selection_sha256": predictions["selection_sha256"],
            "frozen_at": predictions["frozen_at"],
            "scope": predictions["scope"],
            "binding": "exact artifact sha256 + cpu receipt sha256, never place name",
            "preserved_byte_for_byte": True,
        },
        "selection": {
            "frozen_at": selection["frozen_at"],
            "source_base": selection["source_base"],
            "stock_rule": selection["stock_rule"],
            "cohort_gate": selection["cohort_gate"],
            "corpus_sha256": selection["corpus_sha256"],
            "corpus_count": 104,
            "original_selection_sha256": selection["original_selection_sha256"],
            "fixed_controls": [control["file"] for control in selection["controls"]],
        },
        "source_closure": {
            "manifest_file": SOURCE_MANIFEST,
            "prefix": SOURCE_CLOSURE,
            "harness_sources": closure["harness_sources"],
            "build_sources": closure["build_sources"],
            "build_source_count": closure["build_source_count"],
            "files": closure["files"],
        },
        "controls": controls,
        "cohort": cohort,
        "totals": totals,
        "earlier_revisions": earlier,
        "cleanup": cleanup,
        "documents": [
            {"path": f"{PREFIX}{name}", "sha256": digest(ROOT / PREFIX / name)}
            for name in DOCUMENTS
        ],
        "raw_files": raw_files,
        "raw_file_counts": {
            "final_protocol": counts["rail-v3"] + counts["rail-v3-followup-1"],
            "earlier_revisions": counts["rail-v1"] + counts["rail-v2"],
            "total": len(raw_files),
            "runtime_openings": len(launched),
        },
        "method": METHOD,
        "limits": LIMITS,
    }


def seed_corpus(selection):
    """The fixed stock rule must still select the same two builtin filenames."""
    corpus = read_json(ROOT / BASEMAPS)
    require(
        digest(ROOT / BASEMAPS) == selection["corpus_sha256"],
        "stock corpus bytes changed",
    )
    rows = [row for row in corpus if row["file"] != "CO.crp"]
    require(len(rows) == 104, "stock corpus count changed")
    require(
        set(selection["corpus_inventory"]) == {row["file"] for row in rows},
        "corpus inventory changed",
    )
    eligible = sorted(
        (
            row
            for row in rows
            if row.get("meta", {}).get("builtin") == 1
            and row["meta"].get("incomingTrainTracks", 0) > 0
            and row["meta"].get("outgoingTrainTracks", 0) > 0
        ),
        key=lambda row: row["file"],
    )
    return [row["file"] for row in eligible[:2]] == [
        control["file"] for control in selection["controls"]
    ]


def summary_of(study, projection_sha):
    """The exact, bounded block the ledger carries. Kept small on purpose."""
    return {
        "kind": study["kind"],
        "study": study["study"],
        "source_commit": study["source"]["publication_commit"],
        "source_base": study["source"]["publication_base"],
        "source_issue": study["source"]["source_issue"],
        "projection_file": PROJECTION,
        "projection_sha256": projection_sha,
        "projection_tool_file": PROJECTION_TOOL,
        "projection_tool_sha256": digest(ROOT / PROJECTION_TOOL),
        "source_closure_manifest": SOURCE_MANIFEST,
        "source_closure_sha256": digest(ROOT / SOURCE_MANIFEST),
        "frozen_predictions_file": PREDICTIONS,
        "frozen_predictions_sha256": PREDICTIONS_SHA,
        "raw_files": study["raw_file_counts"]["total"],
        "final_protocol_raw_files": study["raw_file_counts"]["final_protocol"],
        "earlier_revision_raw_files": study["raw_file_counts"]["earlier_revisions"],
        "runtime_openings": study["raw_file_counts"]["runtime_openings"],
        "controls": [
            {
                key: control[key]
                for key in (
                    "slug",
                    "file",
                    "artifact_sha256",
                    "selected_boundary",
                    "distinct_edge_successes",
                    "same_edge_successes",
                    "selected_failures",
                    "reciprocal_positives",
                    "invalid_vehicle_pair_rejected",
                    "observed_at",
                )
            }
            for control in study["controls"]
        ],
        "totals": study["totals"],
        "cohort": [
            {
                "slug": case["slug"],
                "square": case["square"],
                "artifact_sha256": case["artifact_sha256"],
                "status": case["status"],
                "frozen_model_level": case["frozen_model_prediction"]["level"],
                "attempts": [
                    {
                        key: attempt[key]
                        for key in (
                            "attempt",
                            "observed_at",
                            "finished_at",
                            "completed",
                            "error",
                            "selected_boundary",
                            "distinct_edge_successes",
                            "same_edge_successes",
                            "selected_failures",
                            "unqueried_boundary_candidates",
                            "missing_reason",
                        )
                    }
                    for attempt in case["attempts"]
                ],
            }
            for case in study["cohort"]
        ],
        "documents": study["documents"],
        "cleanup": {
            "audited_at": study["cleanup"]["audited_at"],
            "degraded": study["cleanup"]["degraded"],
            "findings": study["cleanup"]["findings"],
            "coverage": study["cleanup"]["coverage"],
        },
        "certificates": "none",
        "limits": study["limits"],
    }


RAIL_STUDY_LINE = f'      "rail_study": "{STUDY}",\n'


def indent_fragment(value):
    lines = json.dumps(value, indent=2).splitlines()
    return "\n".join("  " + line if index else line for index, line in enumerate(lines))


def write(study):
    """Write the projection and patch only the owned ledger fragments, idempotently."""
    payload = encoded(study)
    (ROOT / PROJECTION).write_bytes(payload)
    projection_sha = sha(payload)
    block = summary_of(study, projection_sha)
    ledger_path = ROOT / "capabilities.json"
    original = ledger_path.read_text()
    if RAIL_STUDY_LINE in original:
        original = original.replace(RAIL_STUDY_LINE, "", 1)
    rail_marker = original.index('"id": "rail"')
    require(
        '"rail_study"' not in original, "ledger carries an unexpected rail study field"
    )
    insert_at = original.index("\n", rail_marker)
    original = original[: insert_at + 1] + RAIL_STUDY_LINE + original[insert_at + 1 :]
    if '"rail_studies"' in original:
        marker = original.index('"rail_studies"')
        start = original.index("{", marker)
        depth, end = 0, None
        for index in range(start, len(original)):
            if original[index] == "{":
                depth += 1
            elif original[index] == "}":
                depth -= 1
                if depth == 0:
                    end = index + 1
                    break
        require(end is not None, "unbalanced rail_studies block")
        original = original[:start] + indent_fragment({STUDY: block}) + original[end:]
        ledger_path.write_text(original)
        return projection_sha
    text = original.rstrip()
    require(text.endswith("}"), "unexpected ledger tail")
    ledger_path.write_text(
        text[:-1].rstrip()
        + ',\n  "rail_studies": '
        + indent_fragment({STUDY: block})
        + "\n}\n"
    )
    return projection_sha


def verify_current(study):
    """A checked-in projection and ledger binding must match the archived bytes exactly."""
    projection = ROOT / PROJECTION
    require(projection.exists(), "missing the rail study projection")
    payload = projection.read_bytes()
    require(
        payload == encoded(study), "the rail study projection is stale or reformatted"
    )
    expected = summary_of(study, sha(payload))
    ledger = read_json(ROOT / "capabilities.json")
    rail = next(
        capability
        for capability in ledger["capabilities"]
        if capability["id"] == "rail"
    )
    require(
        rail.get("rail_study") == STUDY,
        "Rail does not reference the directed rail study",
    )
    require(
        ledger.get("rail_studies") == {STUDY: expected},
        "ledger rail study binding is stale or unbound",
    )
    require(
        not any(
            cert.get("capability") == "rail"
            for cert in ledger["native_path_certificates"]
        ),
        "a rail native certificate exists",
    )
    return sha(payload)


def archive_native(tree):
    """One-time, reproducible copy of the frozen native sources into the evidence prefix.

    ``tree`` is a clean checkout of the accepted publication commit. The archive never
    installs the native harness into the parent stack and is never executed by the app.
    """
    source = Path(tree)
    selection = selection_json()
    require(
        selection["sources"]["tools/cs1-harness/cs1_harness/rail_study.py"].__len__()
        == 64,
        "unexpected freeze",
    )
    files = {}
    for original in selection["sources"]:
        relative = Path(original)
        require(
            relative.parts[:3] == ("tools", "cs1-harness", relative.parts[2]),
            f"unexpected source path {original}",
        )
        target = ROOT / SOURCE_CLOSURE / relative.parts[2] / relative.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((source / original).read_bytes())
        files[original] = {
            "file": str(target.relative_to(ROOT)),
            "sha256": digest(target),
        }
    build = selection["build_receipt"]["sources"]
    for name in build:
        original = f"tools/cs1-harness/mod/{name}"
        target = ROOT / SOURCE_CLOSURE / "mod" / name
        require(
            original in files, f"build source is not in the frozen source map: {name}"
        )
        require(
            files[original]["sha256"] == build[name],
            f"archived build source differs: {name}",
        )
    manifest_value = {
        "schema": 1,
        "source_commit": SOURCE_COMMIT,
        "harness_sources": len(files),
        "build_sources": len(build),
        "files": files,
        "scope": "read-only frozen native source closure for hash verification; not installed, not executed",
    }
    (ROOT / SOURCE_MANIFEST).write_bytes(encoded(manifest_value))
    return digest(ROOT / SOURCE_MANIFEST)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate without writing")
    parser.add_argument(
        "--archive-native",
        metavar="TREE",
        help="re-archive the frozen native source closure",
    )
    args = parser.parse_args()
    if args.archive_native:
        print(
            json.dumps(
                {"source_closure_sha256": archive_native(args.archive_native)}, indent=2
            )
        )
        return
    study = build_study()
    if args.check:
        projection_sha = verify_current(study)
        print(
            json.dumps(
                {
                    "ok": True,
                    "projection_sha256": projection_sha,
                    "totals": study["totals"],
                    "raw_files": study["raw_file_counts"],
                },
                indent=2,
            )
        )
        return
    print(json.dumps({"projection_sha256": write(study)}, indent=2))


if __name__ == "__main__":
    main()
