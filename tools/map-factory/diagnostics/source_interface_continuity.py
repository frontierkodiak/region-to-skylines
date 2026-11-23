"""Retained source-walk continuity; not hydraulic connectivity or edit authority."""

import argparse
from collections import Counter
from pathlib import Path
import shutil

import numpy as np

from interface_observation import SIZE, hash_file, preflight as parent_preflight
from water_codec_audit import ROOT, check_files, load, write

POLICY = "source-walk-interface-continuity-v2"
FILES = (
    "diagnostics/source_interface_continuity.py",
    "diagnostics/test_source_interface_continuity.py",
    "calibration/pl1191-construction-v1/development/phase35-continuity-policy.md",
    "calibration/pl1191-construction-v1/development/phase35-continuity-policy-v2.md",
)


def native_cell(rc):
    if len(rc) != 2 or any(type(x) is not int or not 0 <= x < SIZE for x in rc):
        raise ValueError("Invalid original source raster cell")
    return (SIZE - 1 - rc[0]) * SIZE + rc[1]


def adjacent(a, b, mode):
    if mode not in (4, 8):
        raise ValueError("Explicit 4/8 adjacency required")
    ar, ac = divmod(a, SIZE)
    br, bc = divmod(b, SIZE)
    dr, dc = abs(ar - br), abs(ac - bc)
    return dr + dc == 1 if mode == 4 else max(dr, dc) == 1


def source_domain(boundary, old_cohort=None):
    t = boundary["complete_source_topology"]
    clips = []
    cells = set(old_cohort["native_nodes"] if old_cohort else [])
    for ident, clip in t["clips"].items():
        ns = [native_cell(rc) for rc in clip["nodes_rc"]]
        cells.update(ns)
        clips.append(
            {
                "clip_id": ident,
                "source_scope": clip["source_scope"],
                "eligible": ident in t["eligible_clip_ids"],
                "native_cells": ns,
                "original_source_clip": clip,
            }
        )
    graph_cells = [native_cell(n["node_rc"]) for n in t["nodes"]]
    cells.update(graph_cells)
    edges = set()
    for walk in t["walks"].values():
        for a, b in zip(walk, walk[1:]):
            if a != b:
                edges.add(tuple(sorted((a, b))))
    joins, unresolved, mappings = set(), [], []
    # conditional_surface_equality_nodes indexes PRE-QUOTIENT keys, not t['nodes'].
    # Resolve captured incidence through exact own source aliases in the quotient.
    aliases = {
        tuple(a): i for i, node in enumerate(t["nodes"]) for a in node["source_aliases"]
    }
    for ji, j in enumerate(t["literal_source_junctions"]):
        ids = []
        for incidence in j["incidence"]:
            clip = incidence["clip_id"]
            if clip not in t["eligible_clip_ids"]:
                continue
            x, z = t["clips"][clip]["points_xz"][incidence["clip_vertex"]]
            key = (clip, round((8640 - z) / 16), round((x + 8640) / 16))
            if key not in aliases:
                raise ValueError(
                    "Literal incidence absent from exact original graph aliases"
                )
            ids.append(aliases[key])
        ids = sorted(set(ids))
        mappings.append(
            {
                "junction_index": ji,
                "pre_quotient_indices": j["conditional_surface_equality_nodes"],
                "resolved_graph_ids": ids,
            }
        )
        if not ids or not j["joined_in_geometric_hypothesis"]:
            unresolved.append(ji)
        elif len({graph_cells[i] for i in ids}) != 1:
            unresolved.append(ji)
        else:
            for i in ids[1:]:
                if i != ids[0]:
                    joins.add(tuple(sorted((ids[0], i))))
    # A graph node belongs to exactly one retained geometric component.
    flat = [n for c in t["components"] for n in c]
    if sorted(flat) != list(range(len(graph_cells))):
        raise ValueError("Incomplete original graph components")
    return {
        "case": boundary["case"],
        "clips": clips,
        "native_cells": sorted(cells),
        "graph_cells": graph_cells,
        "walk_edges": [list(e) for e in sorted(edges)],
        "literal_same_cell_joins": [list(e) for e in sorted(joins)],
        "unresolved_literal_junction_indices": unresolved,
        "literal_junction_index_lineage": mappings,
        "components": t["components"],
        "all_sites": boundary["all_boundary_sites"],
        "old_observation_sites": old_cohort["sites"] if old_cohort else None,
        "no_hydraulic_authority_or_operations": True,
    }


def surface_state(heads, depths):
    h, d = np.asarray(heads), np.asarray(depths)
    if h.size == 0:
        return {
            "state": "no_support_unknown",
            "wet": 0,
            "total": 0,
            "head_min_q": None,
            "head_max_q": None,
            "spread_q": None,
        }
    wet = d > 0
    values = h[wet]
    if np.any(h[~wet] != -1) or np.any(values < 0):
        raise ValueError("Dry cells cannot be observed water surfaces")
    state = (
        "all_dry_no_surface"
        if not values.size
        else "mixed_dry_and_wet"
        if not wet.all()
        else "one_cell_equality_tautology"
        if h.size == 1
        else "all_wet_equal_q"
        if np.ptp(values) == 0
        else "all_wet_distinct_q"
    )
    return {
        "state": state,
        "wet": int(wet.sum()),
        "total": int(h.size),
        "head_min_q": int(values.min()) if values.size else None,
        "head_max_q": int(values.max()) if values.size else None,
        "spread_q": int(np.ptp(values)) if values.size else None,
    }


def path_state(cells, heads, depths, threshold):
    if threshold not in (1, 7):
        raise ValueError("Declared diagnostic thresholds only")
    wet = np.asarray(depths) >= threshold
    deltas = []
    jumps = {str(m): [] for m in (4, 8)}
    for i, (a, b) in enumerate(zip(cells, cells[1:])):
        for m in (4, 8):
            if a != b and not adjacent(a, b, m):
                jumps[str(m)].append(i)
        if a != b and adjacent(a, b, 8) and wet[i] and wet[i + 1]:
            deltas.append(int(heads[i + 1]) - int(heads[i]))
    return {
        "wet_occurrences": int(wet.sum()),
        "occurrences": len(cells),
        "complete_digital_path": {
            str(m): bool(len(cells) and wet.all() and not jumps[str(m)]) for m in (4, 8)
        },
        "unsupported_jump_edge_indices": jumps,
        "adjacent_wet_signed_head_delta_q": deltas,
        "has_increase": any(x > 0 for x in deltas),
        "has_decrease": any(x < 0 for x in deltas),
        "not_flow_direction_or_full_square_disconnection": True,
    }


def induced_counts(graph_cells, edges, joins, components, wet, mode):
    parent = list(range(len(graph_cells)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in [*edges, *joins]:
        if (
            wet[a]
            and wet[b]
            and (
                graph_cells[a] == graph_cells[b]
                or adjacent(graph_cells[a], graph_cells[b], mode)
            )
        ):
            ra, rb = find(a), find(b)
            parent[ra] = rb
    return [
        {
            "wet_graph_nodes": sum(bool(wet[n]) for n in c),
            "wet_induced_components": len({find(n) for n in c if wet[n]}),
        }
        for c in components
    ]


def stage(parent, results, review, consumed, output):
    f = parent_preflight(parent)
    receipt = load(results / "receipt.json")
    if receipt["input_freeze_sha256"] != hash_file(parent / "freeze.json"):
        raise ValueError("Wrong retained result lineage")
    check_files(results, receipt["files_sha256"])
    if (
        load(review)["acceptance_scope"]
        != "LIMITED_PHASE33_34_COUPLED_BOUNDARY_AND_RETAINED_INTERFACE_RESULTS_ONLY"
    ):
        raise ValueError("Wrong independent review")
    if output.exists():
        raise ValueError("Fresh protocol required")
    output.mkdir(parents=True)
    shutil.copytree(parent, output / "parent")
    shutil.copytree(results, output / "parent-results")
    shutil.copyfile(review, output / "review.json")
    shutil.copyfile(consumed, output / "review-consumed.json")
    cases = {}
    for name in f["cases"]:
        b = load(parent / "boundary-results" / f"{name}.json")
        cases[name] = source_domain(
            b, load(parent / "cohort.json") if name == "low-coast-oceania" else None
        )
    write(output / "source-cohort.json", cases)
    deps = dict(f["source_files_sha256"])
    deps.update({n: hash_file(ROOT / n) for n in FILES})
    write(
        output / "freeze.json",
        {
            "policy": POLICY,
            "cases": f["cases"],
            "source_files_sha256": deps,
            "files_sha256": {
                str(p.relative_to(output)): hash_file(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "prior_results_known": True,
            "new_outputs_not_yet_computed": True,
            "no_physical_or_native": True,
        },
    )


def evaluate(folder, output):
    f = load(folder / "freeze.json")
    if f["policy"] != POLICY or output.exists():
        raise ValueError("Exact protocol and fresh output required")
    check_files(ROOT, f["source_files_sha256"])
    check_files(folder, f["files_sha256"])
    domains = load(folder / "source-cohort.json")
    old_c = load(folder / "parent/cohort.json")
    old_r = load(folder / "parent-results/result.json")
    snapshots = load(folder / "parent-results/snapshots.json")
    d = domains["low-coast-oceania"]
    cells = d["native_cells"]
    lookup = {n: i for i, n in enumerate(cells)}
    old_indices = [lookup[n] for n in old_c["native_nodes"]]
    old = np.memmap(
        folder / "parent-results/interface-grid.i32",
        "<i4",
        mode="r",
        shape=tuple(old_r["grid_shape"]),
    )
    output.mkdir(parents=True)
    grid = np.memmap(
        output / "source-grid.i32",
        "<i4",
        mode="w+",
        shape=(len(snapshots), len(cells), 4),
    )
    for ti, snap in enumerate(snapshots):
        a = {}
        for kind in ("water-ground", "water-ground-target", "water"):
            name = f"grids/{snap['prefix']}-{kind}.u16"
            a[kind] = np.fromfile(folder / "parent/native" / name, "<u2")[cells].astype(
                np.int32
            )
        grid[ti, :, 0], grid[ti, :, 1], grid[ti, :, 2] = (
            a["water-ground"],
            a["water-ground-target"],
            a["water"],
        )
        grid[ti, :, 3] = np.where(a["water"] > 0, a["water-ground"] + a["water"], -1)
        if not np.array_equal(grid[ti, old_indices], old[ti]):
            raise ValueError("New full-source projection disagrees with accepted grid")
    grid.flush()
    paths = []
    for clip in d["clips"]:
        idx = [lookup[n] for n in clip["native_cells"]]
        paths.append(
            {
                "clip_id": clip["clip_id"],
                "source_scope": clip["source_scope"],
                "eligible": clip["eligible"],
                "captures": [
                    {
                        str(th): path_state(
                            clip["native_cells"], grid[ti, idx, 3], grid[ti, idx, 2], th
                        )
                        for th in (1, 7)
                    }
                    for ti in range(len(snapshots))
                ],
            }
        )
    sites = [
        {
            "site_id": s["site_id"],
            "site_kind": s["site_kind"],
            "active_potential": s["active_potential"],
            "captures": [
                surface_state(
                    grid[ti, [lookup[n] for n in s["native_nodes"]], 3],
                    grid[ti, [lookup[n] for n in s["native_nodes"]], 2],
                )
                for ti in range(len(snapshots))
            ],
        }
        for s in d["old_observation_sites"]
    ]
    graph_idx = [lookup[n] for n in d["graph_cells"]]
    components = []
    for ti in range(len(snapshots)):
        counts = {
            f"depth_ge{th}q_adj{m}": induced_counts(
                d["graph_cells"],
                d["walk_edges"],
                d["literal_same_cell_joins"],
                d["components"],
                grid[ti, graph_idx, 2] >= th,
                m,
            )
            for th in (1, 7)
            for m in (4, 8)
        }
        for ci, comp in enumerate(d["components"]):
            if ti == 0:
                components.append({"component_index": ci, "captures": []})
            ids = sorted({graph_idx[n] for n in comp})
            components[ci]["captures"].append(
                {
                    "wet_head_state": surface_state(grid[ti, ids, 3], grid[ti, ids, 2]),
                    "source_graph_models": {k: v[ci] for k, v in counts.items()},
                }
            )
    # Disjoint partition for review F1; old table remains unchanged.
    h = old[:, :, 3]
    partition = Counter()
    for i in range(h.shape[1]):
        v = h[:, i][h[:, i] >= 0]
        label = (
            "never_positive_depth"
            if not len(v)
            else "all61_wet_exact90"
            if len(v) == len(snapshots) and np.all(v == 5760)
            else "intermittent_wet_exact90"
            if np.all(v == 5760)
            else "constant_non90_wet_head"
            if np.ptp(v) == 0
            else "variable_wet_head"
        )
        partition[label] += 1
    summary = {
        "policy": POLICY,
        "case": "low-coast-oceania",
        "clips": len(paths),
        "eligible_clips": sum(p["eligible"] for p in paths),
        "sites": len(sites),
        "graph_components": len(components),
        "source_grid_shape": list(grid.shape),
        "source_grid_sha256": hash_file(output / "source-grid.i32"),
        "old_phase34_disjoint_partition": dict(sorted(partition.items())),
        "path_summary": {
            str(th): {
                "all61_complete_adj8": sum(
                    all(c[str(th)]["complete_digital_path"]["8"] for c in p["captures"])
                    for p in paths
                ),
                "ever_both_signed_head_directions": sum(
                    any(
                        c[str(th)]["has_increase"] and c[str(th)]["has_decrease"]
                        for c in p["captures"]
                    )
                    for p in paths
                ),
            }
            for th in (1, 7)
        },
        "no_hydraulic_disconnection_or_constant_stage_gate": True,
        "authority_or_field_operations": None,
        "physical_admission": False,
        "primary_rescore": False,
        "promise": "unknown",
    }
    write(output / "paths.json", paths)
    write(output / "sites.json", sites)
    write(output / "components.json", components)
    write(output / "result.json", summary)
    for case in f["cases"]:
        if case != "low-coast-oceania":
            b = load(folder / "parent/boundary-results" / f"{case}.json")
            write(
                output / f"{case}.json",
                {
                    "policy": POLICY,
                    "case": case,
                    "site_records": len(domains[case]["all_sites"]),
                    "clip_records": len(domains[case]["clips"]),
                    "status": "NULL_original_physical_support_unknown"
                    if b["physical"] is None
                    else "authored_only_native_continuity_unknown",
                    "observations": None,
                    "all_sources_contracts_refusals": "preserved in frozen input",
                    "physical_admission": False,
                    "promise": "unknown",
                },
            )
    write(
        output / "receipt.json",
        {
            "policy": POLICY,
            "input_freeze_sha256": hash_file(folder / "freeze.json"),
            "files_sha256": {p.name: hash_file(p) for p in sorted(output.iterdir())},
        },
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sp = p.add_subparsers(dest="command", required=True)
    s = sp.add_parser("stage")
    for n in ("parent", "results", "review", "consumed", "output"):
        s.add_argument(n, type=Path)
    e = sp.add_parser("evaluate")
    e.add_argument("folder", type=Path)
    e.add_argument("output", type=Path)
    a = p.parse_args()
    if a.command == "stage":
        stage(a.parent, a.results, a.review, a.consumed, a.output)
    else:
        evaluate(a.folder, a.output)


if __name__ == "__main__":
    main()
