"""Conditional source-line correspondence, not feature identity or a constructor."""

import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

import numpy as np

from bank_authority import ROOT, load, sha, write
from maintained_water_inventory import position
from waterway_pieces import catalog, digest, native_walk

POLICY = "conditional-source-line-quantization-v1"
SOURCE = "diagnostics/source_line_alignment.py"
DESIGN = "calibration/pl1191-construction-v1/development/phase14-source-line-policy.md"
WORLD = 2**26  # CONDITIONAL z14 * default4096, not a recovered historic extent.
EPS = 1e-5  # Floating projection roundtrip allowance, in lattice units.
LIMIT = 2**-0.5 + EPS  # Conditional nearest-integer Euclidean rounding bound.
SPACING = 0.125  # Fixed sampled-curve Lipschitz bound; never tuned to outcomes.
ROWS = [672, 683, 712, 713, 770, 809]


def world(points):
    points = np.asarray(points, float)
    if points.ndim != 2 or points.shape[1] != 2 or not np.isfinite(points).all():
        raise ValueError("Expected complete finite lon/lat points")
    lon, lat = points.T
    if np.any(np.abs(lat) >= 85.05113):
        raise ValueError("Outside Mercator test domain")
    return (
        np.column_stack(
            ((lon + 180) / 360, (1 - np.arcsinh(np.tan(np.deg2rad(lat))) / np.pi) / 2)
        )
        * WORLD
    )


def lonlat(points):
    points = np.asarray(points, float) / WORLD
    return np.column_stack(
        (
            points[:, 0] * 360 - 180,
            np.rad2deg(np.arctan(np.sinh(np.pi * (1 - 2 * points[:, 1])))),
        )
    )


def feet(point, line):
    a, edge = line[:-1], np.diff(line, axis=0)
    norm = np.sum(edge**2, axis=1)
    t = np.clip(np.sum((point - a) * edge, axis=1) / np.where(norm, norm, 1), 0, 1)
    projected = a + t[:, None] * edge
    return t, projected, np.linalg.norm(point - projected, axis=1)


def sample(line):
    return np.vstack(
        [
            a
            + np.linspace(
                0, 1, max(1, int(np.ceil(np.linalg.norm(b - a) / SPACING))) + 1
            )[:, None]
            * (b - a)
            for a, b in zip(line, line[1:])
        ]
    )


def directed_max(points, line):
    # Chunking bounds memory for complete long branches; no point selection.
    maximum = 0.0
    for start in range(0, len(points), 4096):
        p = points[start : start + 4096]
        a, edge = line[:-1], np.diff(line, axis=0)
        norm = np.sum(edge**2, axis=1)
        delta = p[:, None, :] - a
        t = np.clip(np.sum(delta * edge, axis=2) / np.where(norm, norm, 1), 0, 1)
        d = np.linalg.norm(delta - t[:, :, None] * edge, axis=2).min(axis=1)
        maximum = max(maximum, float(d.max()))
    return maximum


def ordered_vertices(points, line):
    """All vertices have nondecreasing feasible positions; not a Frechet proof."""
    previous = 0.0
    for point in points:
        possible = []
        for i, (a, b) in enumerate(zip(line, line[1:])):
            edge, delta = b - a, a - point
            n = float(edge @ edge)
            if n == 0:
                if np.linalg.norm(delta) <= LIMIT and i >= previous:
                    possible.append(float(i))
                continue
            center = -float(delta @ edge) / n
            discriminant = (
                LIMIT**2 - float(delta @ delta) + float(delta @ edge) ** 2 / n
            )
            if discriminant < 0:
                continue
            radius = np.sqrt(discriminant / n)
            lo, hi = max(0.0, center - radius, previous - i), min(1.0, center + radius)
            if lo <= hi:
                possible.append(i + lo)
        if not possible:
            return False
        previous = min(possible)
    return True


def compare(source, raw):
    """Enumerate every endpoint-supported ordered subchain in either direction."""
    t0, p0, d0 = feet(source[0], raw)
    t1, p1, d1 = feet(source[-1], raw)
    starts, ends = np.flatnonzero(d0 <= LIMIT), np.flatnonzero(d1 <= LIMIT)
    result = {
        "minimum_endpoint_distances_q": [float(d0.min()), float(d1.min())],
        "embeddings": [],
    }
    if len(starts) * len(ends) > 256:
        return {**result, "status": "unresolved_embedding_multiplicity"}
    for a in starts:
        for b in ends:
            u, v = a + t0[a], b + t1[b]
            if u == v:
                continue
            reverse = u > v
            lo, hi = sorted((u, v))
            middle = [raw[i] for i in range(1, len(raw) - 1) if lo < i < hi]
            segment = np.array(
                [p1[b] if reverse else p0[a], *middle, p0[a] if reverse else p1[b]]
            )
            if reverse:
                segment = segment[::-1]
            measured = max(
                directed_max(sample(source), segment),
                directed_max(sample(segment), source),
            )
            upper = measured + SPACING / 2
            order = ordered_vertices(source, segment) and ordered_vertices(
                segment, source
            )
            status = "incompatible_under_conditional_rounding_model"
            if measured <= LIMIT and order:
                status = (
                    "consistent_under_conditional_rounding_model"
                    if upper <= LIMIT
                    else "unresolved_sampling_margin"
                )
            result["embeddings"].append(
                {
                    "raw_start_segment": int(a),
                    "raw_end_segment": int(b),
                    "raw_start_t": float(t0[a]),
                    "raw_end_t": float(t1[b]),
                    "reverse_raw_order": bool(reverse),
                    "status": status,
                    "sampled_symmetric_distance_lower_q": measured,
                    "certified_symmetric_distance_upper_q": upper,
                    "monotone_vertex_correspondence": order,
                    "complete_raw_subchain_lonlat": lonlat(segment).tolist(),
                }
            )
    if not result["embeddings"]:
        result["status"] = "no_endpoint_supported_embedding"
    else:
        counts = Counter(e["status"] for e in result["embeddings"])
        result["embedding_status_counts"] = dict(counts)
        result["status"] = "candidate_embeddings_retained"
    return result


def quantized_node_candidates(q, raw):
    return [
        {"way": e["id"], "node": e["nodes"][int(i)], "vertex_index": int(i)}
        for e, ps in raw
        for i in np.flatnonzero(
            np.max(np.abs(np.floor(ps + 0.5) - np.rint(q)), axis=1) <= EPS
        )
    ]


def analyze(folder):
    geometry = load(folder / "source/lowland-river-south-america/geometry.json")
    pieces = catalog(geometry)
    captured = load(folder / "public/response.json")
    raw = []
    unsupported = []
    for e in captured["elements"]:
        if (
            e["type"] != "way"
            or "waterway" not in e.get("tags", {})
            or e["tags"]["waterway"] == "riverbank"
        ):
            unsupported.append(
                {
                    "type": e["type"],
                    "id": e["id"],
                    "scope": "not_a_public_waterway_line",
                }
            )
            continue
        try:
            points = [[p["lon"], p["lat"]] for p in e["geometry"]]
            if len(points) < 2 or len(points) != len(e["nodes"]):
                raise ValueError("Incomplete public way geometry/node references")
            raw.append((e, world(points)))
        except (ValueError, KeyError, TypeError) as error:
            unsupported.append(
                {
                    "type": e["type"],
                    "id": e["id"],
                    "scope": "unresolved_line_geometry",
                    "error": str(error),
                }
            )
    rows, incidence = [], {}
    for index in ROWS:
        feature = geometry["streams"][index]
        record = next(
            r
            for r in pieces["rows"]
            if r["field"] == "streams" and r["source_index"] == index
        )
        source = world(feature["pts"])
        residual = float(np.abs(source - np.rint(source)).max())
        comparisons = []
        for e, points in raw:
            comparison = (
                compare(source, points)
                if residual <= EPS
                else {"status": "unresolved_source_lattice", "embeddings": []}
            )
            for embedding in comparison["embeddings"]:
                if embedding["status"] == "consistent_under_conditional_rounding_model":
                    proposed = [
                        position(geometry["sq"], p)
                        for p in embedding["complete_raw_subchain_lonlat"]
                    ]
                    old = {
                        tuple(n) for clip in record["clips"] for n in clip["nodes_rc"]
                    }
                    new = set(map(tuple, native_walk(np.array(proposed))))
                    embedding["native_walk_sensitivity"] = {
                        "original_nodes": len(old),
                        "conditional_raw_nodes": len(new),
                        "removed_original_nodes_rc": [
                            list(n) for n in sorted(old - new)
                        ],
                        "added_raw_nodes_rc": [list(n) for n in sorted(new - old)],
                        "scope": "conditional read-only counterfactual, not a new authored graph",
                    }
            comparisons.append(
                {
                    "osm_way_id": e["id"],
                    "version": e.get("version"),
                    "timestamp": e.get("timestamp"),
                    "tags": e["tags"],
                    "complete_raw_geometry_sha256": digest(e["geometry"]),
                    "node_reference_sha256": digest(e["nodes"]),
                    **comparison,
                }
            )
        anchors = []
        for vertex_index, (point, q) in enumerate(zip(feature["pts"], source)):
            matches = quantized_node_candidates(q, raw)
            key = tuple(point)
            incidence.setdefault(key, []).append(
                {"row": record["id"], "vertex_index": vertex_index}
            )
            anchors.append(
                {
                    "vertex_index": vertex_index,
                    "public_quantized_node_candidates": matches,
                }
            )
        rows.append(
            {
                "id": record["id"],
                "source_sha256": record["source_sha256"],
                "clips_unchanged": record["clips"],
                "source_vertex_count": len(source),
                "conditional_lattice_max_residual_q": residual,
                "public_way_comparisons": comparisons,
                "all_vertex_node_anchors": anchors,
                "historical_source_identity": "unresolved: captured feature ID/tile/extent/version absent; geometry is not identity",
                "bank_width_and_floor": "unknown",
                "new_admission": False,
            }
        )
    return {
        "schema": "polli.source-line-alignment/1",
        "policy": POLICY,
        "conditional_world_grid": WORLD,
        "conditional_rounding_limit_q": LIMIT,
        "curve_sampling_spacing_q": SPACING,
        "historical_encoder_rounding_simplification_bound": "unknown; conditional model only",
        "public_line_count": len(raw),
        "other_or_unsupported_public_elements": unsupported,
        "rows": rows,
        "all_shared_captured_vertices": [
            {"lonlat": list(point), "incidences": owners}
            for point, owners in sorted(incidence.items())
            if len({o["row"] for o in owners}) > 1
        ],
        "all_five_case_scope_unchanged": load(folder / "source/case-bindings.json"),
        "physical_package": None,
        "new_admissions": 0,
        "holdout_inputs_accessed": False,
        "stable_water_promise": "unknown",
    }


def stage(bankroot, public, packing, output):
    if output.exists():
        raise ValueError("Use a fresh alignment protocol; retain every result")
    receipt = load(public / "capture-receipt.json")
    if (
        receipt["status"] != "captured"
        or sha(public / "response.json")
        != "3046ec83673bbb04439b86e35e2a872801aa0aa8f6dcdfdaccb1274a7a30e25c"
    ):
        raise ValueError("Expected exact already-captured public evidence")
    output.mkdir(parents=True)
    cases = []
    authority_path = (
        ROOT / "calibration/pl1191-construction-v1/bank-authority-freeze-v1.json"
    )
    authority = load(authority_path)
    expected_cases = {c["slug"]: c["freeze_sha256"] for c in authority["cases"]}
    for slug, expected_freeze in sorted(expected_cases.items()):
        case = bankroot / slug
        if sha(case / "freeze.json") != expected_freeze:
            raise ValueError("Case no longer matches original authority freeze")
        frozen = load(case / "freeze.json")
        for name, expected in frozen["files_sha256"].items():
            if sha(case / name) != expected:
                raise ValueError(f"Original case changed: {case.name}/{name}")
        audit = load(case / "bank-audit.json")
        dest = output / "source" / case.name
        dest.mkdir(parents=True)
        for src, name in [
            (case / "freeze.json", "previous-freeze.json"),
            (case / "input/input/source/geometry.json", "geometry.json"),
            (case / "bank-audit.json", "bank-audit.json"),
            (case / "input/port-plan.json", "port-plan.json"),
        ]:
            shutil.copyfile(src, dest / name)
        probes = case / "input/input/source/probes.json"
        if probes.exists():
            shutil.copyfile(probes, dest / "probes.json")
        cases.append(
            {
                "slug": case.name,
                "mandatory_parts": len(audit["eligible_clip_ids"]),
                "line_rows": audit["original_line_rows"],
                "polygon_rows": audit["original_polygon_rows"],
                "old_status": audit["original_status"],
                "old_freeze_sha256": sha(case / "freeze.json"),
                "physical_support": None
                if audit["components"] is None
                else "not_read_or_requalified",
            }
        )
    if len(cases) != 5 or sum(c["mandatory_parts"] for c in cases) != 583:
        raise ValueError("Incomplete predeclared five-case scope")
    write(output / "source/case-bindings.json", cases)
    shutil.copytree(public, output / "public")
    shutil.copytree(packing, output / "packing")
    dependencies = dict(frozen["source_files_sha256"])
    for name in (
        SOURCE,
        DESIGN,
        "calibration/pl1191-construction-v1/bank-authority-freeze-v1.json",
        "../../inputs.js",
        "capture.js",
        "../../package-lock.json",
    ):
        dependencies[name] = sha(ROOT / name)
    write(
        output / "prospective-freeze.json",
        {
            "schema": "polli.source-line-alignment-prospective/1",
            "policy": POLICY,
            "source_files_sha256": dependencies,
            "files_sha256": {
                str(p.relative_to(output)): sha(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "no_geometry_or_physical_edits": True,
        },
    )
    result = analyze(output)
    write(output / "alignment.json", result)
    write(
        output / "result-receipt.json",
        {
            "prospective_freeze_sha256": sha(output / "prospective-freeze.json"),
            "alignment_sha256": sha(output / "alignment.json"),
            "policy": POLICY,
        },
    )
    preflight(output)
    return {
        "prospective_freeze_sha256": sha(output / "prospective-freeze.json"),
        "result_receipt_sha256": sha(output / "result-receipt.json"),
        "new_admissions": 0,
    }


def preflight(folder):
    frozen = load(folder / "prospective-freeze.json")
    if (
        frozen["schema"] != "polli.source-line-alignment-prospective/1"
        or frozen["policy"] != POLICY
    ):
        raise ValueError("Wrong conditional read-only protocol")
    for name, expected in frozen["source_files_sha256"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"Alignment source changed: {name}")
    for name, expected in frozen["files_sha256"].items():
        if sha(folder / name) != expected:
            raise ValueError(f"Source or public cohort changed: {name}")
    receipt = load(folder / "result-receipt.json")
    if (
        sha(folder / "prospective-freeze.json") != receipt["prospective_freeze_sha256"]
        or sha(folder / "alignment.json") != receipt["alignment_sha256"]
        or analyze(folder) != load(folder / "alignment.json")
    ):
        raise ValueError("Full correspondence replay differs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, arguments in (
        ("stage", ("bankroot", "public", "packing", "output")),
        ("preflight", ("folder",)),
    ):
        command = commands.add_parser(name)
        for argument in arguments:
            command.add_argument(argument, type=Path)
    arguments = vars(parser.parse_args())
    print(
        json.dumps(
            globals()[arguments.pop("command")](**arguments)
            or {"status": "replay_pass"},
            indent=2,
        )
    )
