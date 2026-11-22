"""Read-only whole-domain head envelopes for source-only local supply proposals.

A connected sub-stage floor is a conservative raster model, not a hydraulic
component, surveyed bank, flow direction, or qualified supply budget. No source
is placed and no stream is certified as a pond.
"""

import argparse
from collections import Counter
import hashlib
from pathlib import Path
import shutil

import numpy as np
from scipy import ndimage

from bank_authority import ROOT, load, sha, write
from coastal_floor_audit import grid
from crp import N, decode_u16, read_package
from maintained_water_inventory import source_tag
from region import raster
from template import manager_tag
from water_diagnostics import bind_sources, decode_water
from waterway_pieces import catalog, digest

POLICY = "source-only-local-supply-head-envelope-v1"
DESIGN = "calibration/pl1191-construction-v1/development/phase22-supply-policy.md"
METHOD = "diagnostics/local_supply_envelope.py"
RATE = 128


def component_envelope(floor, initial, mapped, stage_q, candidates, adjacency):
    """Cover every proposed source node, including all connected off-source land."""
    floor, initial, mapped = np.asarray(floor), np.asarray(initial), np.asarray(mapped)
    if (
        floor.ndim != 2
        or initial.shape != floor.shape
        or mapped.shape != floor.shape
        or floor.dtype.kind not in "iu"
        or initial.dtype.kind not in "iu"
        or np.any(floor < 0)
        or np.any(initial < 0)
        or np.any(floor > 65535)
        or np.any(initial > 65535)
        or not 0 < stage_q <= 131070
        or adjacency not in (4, 8)
    ):
        raise ValueError(
            "Expected complete quantized floor/depth and explicit adjacency"
        )
    candidates = np.asarray(candidates, dtype=np.int64)
    if (
        candidates.ndim != 1
        or np.any(candidates < 0)
        or np.any(candidates >= floor.size)
    ):
        raise ValueError("Source candidate outside the complete floor")
    if np.any(floor.ravel()[candidates] >= stage_q):
        raise ValueError("Proposed source is not below its declared stage")
    labels, _ = ndimage.label(
        floor < stage_q, ndimage.generate_binary_structure(2, adjacency // 4)
    )
    slices = ndimage.find_objects(labels)
    results = []
    for label in sorted(int(v) for v in np.unique(labels.ravel()[candidates])):
        if label == 0:
            raise ValueError("Lost source node")
        box = slices[label - 1]
        expanded = tuple(
            slice(max(0, s.start - 1), min(floor.shape[i], s.stop + 1))
            for i, s in enumerate(box)
        )
        domain = labels[expanded] == label
        rim = ndimage.binary_dilation(domain, np.ones((3, 3))) & ~domain
        local_floor = floor[expanded].astype(np.int64)
        freeboard = int(local_floor[rim].min()) - stage_q if rim.any() else None
        rows, cols = np.nonzero(domain)
        nodes = (rows + expanded[0].start) * floor.shape[1] + cols + expanded[1].start
        own_candidates = candidates[labels.ravel()[candidates] == label]
        outside = ~mapped.ravel()[nodes]
        dry = initial.ravel()[nodes] == 0
        exterior = (
            expanded[0].start == 0
            and bool(domain[0].any())
            or expanded[0].stop == floor.shape[0]
            and bool(domain[-1].any())
            or expanded[1].start == 0
            and bool(domain[:, 0].any())
            or expanded[1].stop == floor.shape[1]
            and bool(domain[:, -1].any())
        )
        reasons = []
        if exterior:
            reasons.append("open_square_boundary_requires_explicit_port_plan")
        if freeboard is None or freeboard < 32:
            reasons.append("full_untouched_exterior_half_metre_freeboard_not_met")
        if outside.any():
            reasons.append("substage_domain_includes_unmapped_ground")
        if stage_q > 65535:
            reasons.append("target_exceeds_encoded_control_stage_range")
        results.append(
            {
                "id": f"stage:{stage_q}:adj:{adjacency}:component:{label}",
                "stage_q": int(stage_q),
                "adjacency": adjacency,
                "nodes": int(nodes.size),
                "nodes_i32_sha256": hashlib.sha256(
                    nodes.astype("<i4").tobytes()
                ).hexdigest(),
                "candidate_nodes": own_candidates.tolist(),
                "unmapped_nodes": int(outside.sum()),
                "initially_dry_unmapped_nodes": int((outside & dry).sum()),
                "first_unmapped_node": int(nodes[outside][0])
                if outside.any()
                else None,
                "first_dry_unmapped_node": int(nodes[outside & dry][0])
                if (outside & dry).any()
                else None,
                "touches_square_boundary": bool(exterior),
                "full_rim_freeboard_q": freeboard,
                "rim_witness_rc": (
                    np.array(
                        np.unravel_index(
                            np.argmin(np.where(rim, local_floor, 131071)), domain.shape
                        )
                    )
                    + [expanded[0].start, expanded[1].start]
                ).tolist()
                if rim.any()
                else None,
                "geometry_reasons": reasons,
                "static_envelope_only": True,
                "hydraulic_connectivity_and_budget": "unknown",
            }
        )
    return results


def source_masks(geometry):
    """All rows/parts retained; only explicit intermittent/tunnel exclusions."""
    pieces = catalog(geometry)
    rows, masks = [], []
    mapped = np.flipud(
        raster(geometry["sq"], geometry.get("oceans", []), polygons=True)
    )
    for row in pieces["rows"]:
        feature = (
            geometry.get(row["field"], [])[row["source_index"]]
            if "source_index" in row
            else {}
        )
        row = {**row, "name": feature.get("name"), "class": feature.get("class")}
        mask = np.zeros((1081, 1081), bool)
        for clip in row["clips"]:
            for r, c in clip["nodes_rc"]:
                mask[1080 - r, c] = True
        rows.append(row)
        masks.append(mask)
        if row["status"] == "perennial_surface":
            mapped |= mask
    for field in ("lakes", "riverAreas"):
        for i, feature in enumerate(geometry.get(field, [])):
            status = "perennial_surface"
            if source_tag(feature, "intermittent") in (True, 1, "1", "yes", "true"):
                status = "excluded_intermittent"
            if source_tag(feature, "brunnel") == "tunnel":
                status = "excluded_underground"
            try:
                mask = np.flipud(raster(geometry["sq"], [feature], polygons=True))
                if not mask.any() and status == "perennial_surface":
                    status = "unsupported_or_outside_polygon_retained"
            except (ValueError, TypeError, KeyError, IndexError):
                mask = np.zeros((1081, 1081), bool)
                status = "unresolved_polygon"
            rows.append(
                {
                    "id": f"{field}:{i}",
                    "status": status,
                    "source_sha256": digest(feature),
                    "name": feature.get("name"),
                    "class": feature.get("class"),
                }
            )
            masks.append(mask)
            if status == "perennial_surface":
                mapped |= mask
    return rows, masks, mapped


def physical(folder):
    packages = list(folder.glob("*.crp"))
    if len(packages) != 1:
        raise ValueError("Expected exactly one unchanged physical package")
    payload = next(
        a["payload"]
        for a in read_package(packages[0].read_bytes())[1]
        if a["kind"] == 52
    )
    decoded = decode_water(payload)
    bind_sources(decoded, load(folder / "hydrology.json"))
    tag = manager_tag("TerrainManager")
    if payload.count(tag) != 1:
        raise ValueError("Ambiguous physical terrain")
    terrain, offset = decode_u16(payload, N, payload.index(tag) + len(tag))
    delta, _ = decode_u16(payload, int(np.count_nonzero(terrain)), offset)
    if (
        delta.any()
        or terrain.astype("<u2").tobytes() != (folder / "terrain.u16").read_bytes()
    ):
        raise ValueError("Physical terrain differs from captured authored grid")
    if decoded["depth"].astype("<u2").tobytes() != (folder / "water.u16").read_bytes():
        raise ValueError("Physical initial water differs from captured grid")
    end = decoded["end"] - 14
    start = end - 43 * len(decoded["sources"])
    controls = [
        {**c, "raw43_hex": payload[start + 43 * i : start + 43 * (i + 1)].hex()}
        for i, c in enumerate(decoded["sources"])
    ]
    return decoded, controls


def analyze(case):
    config = load(case / "case.json")
    source = case / "input"
    if config["kind"] == "geographic":
        ledger = load(source / "ledger.json")
        geometry_path = source / "source/geometry.json"
    else:
        ledger = None
        geometry_path = source / "physical/geometry.json"
    geometry = load(geometry_path)
    rows, masks, mapped = source_masks(geometry)
    result = {
        "case": case.name,
        "source_geometry_sha256": sha(geometry_path),
        "all_rows": rows,
        "row_scopes": dict(Counter(r["status"] for r in rows)),
        "mandatory_line_parts": sum(
            len(r.get("clips", [])) for r in rows if r["status"] == "perennial_surface"
        ),
        "all_original_contracts_and_probes_retained": True,
        "physical_admission": False,
        "new_controls": [],
        "no_earthwork_or_mask_change": True,
        "promise": "unknown",
    }
    if ledger and "retained_base_refusal" in ledger:
        result.update(
            original_base_refusal=ledger["retained_base_refusal"],
            floor=None,
            initial=None,
            controls=None,
            domains=None,
        )
        return result
    folder = source / "physical"
    decoded, controls = physical(folder)
    authored = grid(folder / "terrain.u16").astype(np.int64)
    initial = grid(folder / "water.u16").astype(np.int64)
    floor = (
        grid(case / "current-floor.u16").astype(np.int64)
        if config["kind"] == "coastal"
        else authored
    )
    if config["kind"] == "coastal" and sha(source / "physical/terrain.u16") != sha(
        case / "raw-native-terrain.u16"
    ):
        raise ValueError("Retained actual floor belongs to different physical terrain")
    stage = floor + initial
    all_source = np.zeros_like(mapped)
    entries = []
    for row, mask in zip(rows, masks):
        mandatory = row["status"] == "perennial_surface"
        if mandatory:
            all_source |= mask
        entries.append(
            {
                "id": row["id"],
                "status": row["status"],
                "source_nodes": int(mask.sum()),
                "initially_dry_nodes": int((mask & (initial == 0)).sum()),
                "source_footprint_under_1m_nodes": int((mask & (initial < 64)).sum()),
                "port_candidate_nodes": np.flatnonzero(mask & (initial >= 64)).tolist()
                if mandatory
                else [],
            }
        )
    candidates = np.flatnonzero(all_source & (initial >= 64))
    domains = []
    for target in sorted(int(v) for v in np.unique(stage.ravel()[candidates])):
        selected = candidates[stage.ravel()[candidates] == target]
        for adjacency in (4, 8):
            domains.extend(
                component_envelope(floor, initial, mapped, target, selected, adjacency)
            )
    result.update(
        floor={
            "kind": "exact-package actual captured t0"
            if config["kind"] == "coastal"
            else "authored quantized; actual unknown",
            "sha256": sha(case / "current-floor.u16")
            if config["kind"] == "coastal"
            else sha(folder / "terrain.u16"),
            "authored_different_nodes": int(np.count_nonzero(floor != authored)),
        },
        initial_sha256=sha(folder / "water.u16"),
        full_original_probes_sha256=sha(folder / "probes.json"),
        package_sha256=sha(next(folder.glob("*.crp"))),
        controls=controls,
        sea_m=decoded["sea_level_m"],
        candidate_rate_declaration={
            "encoded_setting": RATE,
            "model_radius_m": float(10 + 0.4 * np.sqrt(RATE)),
            "single_node_footprint_if_grid_centred": True,
            "integrated_flux_or_demand": "unknown; no control deployed",
        },
        source_support=entries,
        candidate_nodes=int(candidates.size),
        unique_declared_initial_heads=int(np.unique(stage.ravel()[candidates]).size),
        domains=domains,
        geometry_reason_counts=dict(
            Counter(reason for d in domains for reason in d["geometry_reasons"])
        ),
        open_junction_outlet_direction_and_bank_authority="unresolved; raster component is not a stream basin or surveyed width",
        existing_protection_and_refusals="unchanged in complete copied input; no candidate overrides old guards",
        rationale="Source-footprint depth alone cannot certify the full sub-stage domain. Nonempty geometry reasons refuse this fixed-head envelope; empty reasons remain unqualified, not admitted.",
    )
    return result


def stage(specification, output):
    if output.exists():
        raise ValueError("Fresh read-only protocol directory required")
    spec = load(specification)
    output.mkdir(parents=True)
    for entry in spec["cases"]:
        case = output / entry["name"]
        case.mkdir()
        shutil.copytree(entry["input"], case / "input")
        for key, name in (
            ("floor", "current-floor.u16"),
            ("raw_terrain", "raw-native-terrain.u16"),
            ("native_receipt", "native-session-receipt.json"),
        ):
            if entry.get(key):
                shutil.copyfile(entry[key], case / name)
        write(case / "case.json", {"kind": entry["kind"]})
    shutil.copyfile(spec["review_thread"], output / "review-thread.json")
    dependencies = sorted(
        {
            *ROOT.glob("*.py"),
            *ROOT.glob("diagnostics/*.py"),
            ROOT / DESIGN,
            ROOT / "pyproject.toml",
            ROOT / "uv.lock",
        }
    )
    write(
        output / "freeze.json",
        {
            "policy": POLICY,
            "source_files_sha256": {
                str(p.relative_to(ROOT)): sha(p) for p in dependencies
            },
            "files_sha256": {
                str(p.relative_to(output)): sha(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "cases": [e["name"] for e in spec["cases"]],
            "outcomes_known": "prior native results known; new CPU envelopes not yet evaluated",
            "new_native": False,
            "definition_sha256": "2d72a80690d26c2f7de729e36d785c790451b4d28f6837fbf7b177af25ea4886",
        },
    )


def preflight(folder):
    frozen = load(folder / "freeze.json")
    if frozen["policy"] != POLICY:
        raise ValueError("Wrong envelope policy")
    for root, key in ((ROOT, "source_files_sha256"), (folder, "files_sha256")):
        for name, expected in frozen[key].items():
            if sha(root / name) != expected:
                raise ValueError(f"Bound input/method changed: {name}")
    for name in frozen["cases"]:
        case = folder / name
        if load(case / "case.json")["kind"] == "coastal":
            receipt = load(case / "native-session-receipt.json")
            if receipt["map"]["sha256"] != sha(
                next((case / "input/physical").glob("*.crp"))
            ):
                raise ValueError("Actual floor package identity mismatch")


def evaluate(folder, output):
    preflight(folder)
    if output.exists():
        raise ValueError("Fresh CPU result directory required")
    output.mkdir(parents=True)
    for name in load(folder / "freeze.json")["cases"]:
        write(output / f"{name}.json", analyze(folder / name))
    write(
        output / "receipt.json",
        {
            "policy": POLICY,
            "input_freeze_sha256": sha(folder / "freeze.json"),
            "result_files_sha256": {
                p.name: sha(p) for p in sorted(output.glob("*.json"))
            },
            "new_physical_or_native": False,
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, arguments in (
        ("stage", ("specification", "output")),
        ("preflight", ("folder",)),
        ("evaluate", ("folder", "output")),
    ):
        cmd = sub.add_parser(name)
        for argument in arguments:
            cmd.add_argument(argument, type=Path)
    args = vars(parser.parse_args())
    globals()[args.pop("command")](**args)
