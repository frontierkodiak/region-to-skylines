"""Continuous even-odd source-polygon membership on complete fixed node domains."""

import argparse
from pathlib import Path
import shutil
import numpy as np

from bank_authority import ROOT, load, sha, write
from prepare import pixel
from qld_hydrographic_coverage import preflight as raster_preflight

POLICY = "qld-complete-source-point-membership-v2"
FILES = (
    "diagnostics/qld_point_coverage.py",
    "diagnostics/test_qld_point_coverage.py",
    "calibration/pl1191-construction-v1/development/phase27-point-coverage-policy.md",
)
# Numerical boundary ambiguity only, NOT provider accuracy or acceptance threshold.
BOUNDARY_M = 0.001


def even_odd(points, rings, epsilon):
    inside = np.zeros(len(points), dtype=bool)
    boundary = np.zeros(len(points), dtype=bool)
    for ring in rings:
        ring = np.asarray(ring, dtype=float)
        if (
            ring.ndim != 2
            or ring.shape[1] != 2
            or len(ring) < 4
            or not np.isfinite(ring).all()
            or not np.array_equal(ring[0], ring[-1])
        ):
            raise ValueError("Invalid/unclosed/nonfinite ring, not absent water")
        candidate = np.flatnonzero(
            np.all(points >= ring.min(axis=0) - epsilon, axis=1)
            & np.all(points <= ring.max(axis=0) + epsilon, axis=1)
        )
        q = points[candidate]
        local = np.zeros(len(q), dtype=bool)
        edge = np.zeros(len(q), dtype=bool)
        for a, b in zip(ring, ring[1:]):
            d = b - a
            length = float(d @ d)
            t = np.clip(((q - a) @ d) / length, 0, 1) if length else np.zeros(len(q))
            distance2 = np.sum((q - (a + t[:, None] * d)) ** 2, axis=1)
            edge |= distance2 <= epsilon**2
            if d[1] != 0:
                local ^= ((a[1] > q[:, 1]) != (b[1] > q[:, 1])) & (
                    q[:, 0] < a[0] + d[0] * (q[:, 1] - a[1]) / d[1]
                )
        inside[candidate] ^= local
        boundary[candidate] |= edge
    return inside & ~boundary, boundary


def stage(parent, raster_results, output):
    raster_preflight(parent)
    if load(raster_results / "receipt.json")["prospective_freeze_sha256"] != sha(
        parent / "freeze.json"
    ):
        raise ValueError("Wrong raster comparison lineage")
    if output.exists():
        raise ValueError("Fresh point coverage protocol required")
    output.mkdir(parents=True)
    shutil.copytree(parent, output / "input")
    shutil.copyfile(
        raster_results / "coverage.json", output / "raster-v1-comparison.json"
    )
    deps = dict(load(parent / "freeze.json")["source_files_sha256"])
    for n in FILES:
        deps[n] = sha(ROOT / n)
    write(
        output / "freeze.json",
        {
            "policy": POLICY,
            "source_files_sha256": deps,
            "files_sha256": {
                str(p.relative_to(output)): sha(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "raster_results_and_ring_counts_known": True,
            "point_memberships_not_yet_computed": True,
            "boundary_ambiguity_m": BOUNDARY_M,
            "physical_or_native": False,
        },
    )


def preflight(folder):
    f = load(folder / "freeze.json")
    if f["policy"] != POLICY:
        raise ValueError("Wrong point protocol")
    for base, key in ((ROOT, "source_files_sha256"), (folder, "files_sha256")):
        for n, value in f[key].items():
            if sha(base / n) != value:
                raise ValueError(f"Changed source/input: {n}")


def bank_nodes(old, component):
    own = {
        tuple(old["complete_source_topology"]["nodes"][i]["node_rc"])
        for i in component["graph_node_ids"]
    }
    bank = {
        (r + y, c + x) for r, c in own for y in (-1, 0, 1) for x in (-1, 0, 1)
    } - own
    return sorted(n for n in bank if 0 <= n[0] <= 1080 and 0 <= n[1] <= 1080)


def membership(nodes, index, masks):
    at = [index[tuple(n)] for n in nodes]
    known = {
        name: np.flatnonzero(v[0][at]).tolist() for name, v in sorted(masks.items())
    }
    boundary = {
        name: np.flatnonzero(v[1][at]).tolist() for name, v in sorted(masks.items())
    }
    return {
        "walk_occurrences": len(nodes),
        "unique_nodes": len(set(map(tuple, nodes))),
        "covered_occurrences": len({i for v in known.values() for i in v}),
        "boundary_unknown_occurrences": len({i for v in boundary.values() for i in v}),
        "per_external_body_occurrence_indices": known,
        "per_external_body_boundary_unknown_indices": boundary,
        "hydraulic_bank_identity_stage_capacity": None,
    }


def evaluate(folder, output):
    preflight(folder)
    if output.exists():
        raise ValueError("Fresh point coverage results required")
    output.mkdir(parents=True)
    src = folder / "input"
    geometry = load(src / "original-geometry.json")
    old = load(src / "original-complete-graph.json")
    clips = old["complete_source_topology"]["clips"]
    ports = [
        c
        for c in old["components"]
        if c["conditional_variable_stage_plan"]["status"]
        == "unresolved_open_port_lateral_or_exterior_bank"
    ]
    domain = set(tuple(n) for c in clips.values() for n in c["nodes_rc"])
    for c in ports:
        domain.update(bank_nodes(old, c))
    nodes = sorted(domain)
    xy = np.asarray([[c, r] for r, c in nodes], dtype=float)
    index = {n: i for i, n in enumerate(nodes)}
    bodies = load(src / "external-source/layer-63-complete.json")["features"]
    masks = {}
    records = []
    groups = {}
    for f in bodies:
        attrs = f["attributes"]
        name = f"OBJECTID:{attrs['objectid']}"
        record = {"id": name, "attributes": attrs}
        try:
            raw = f["geometry"]["rings"]
            projected = [[pixel(geometry["sq"], p[:2]) for p in ring] for ring in raw]
            inside, uncertain = even_odd(xy, projected, BOUNDARY_M / 16)
            masks[name] = (inside, uncertain)
            orientations = [
                float(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(r, r[1:])) / 2)
                for r in raw
            ]
            record.update(
                ring_count=len(raw),
                ring_signed_areas=orientations,
                domain_nodes_inside=int(inside.sum()),
                domain_nodes_boundary_unknown=int(uncertain.sum()),
            )
        except (KeyError, TypeError, ValueError, IndexError) as error:
            record.update(status="unresolved_geometry", reason=str(error))
        records.append(record)
        key = "|".join(
            str(attrs.get(k)) for k in ("feature_type", "function", "perenniality")
        )
        groups.setdefault(key, []).append(name)
    result = {
        "policy": POLICY,
        "prospective_freeze_sha256": sha(folder / "freeze.json"),
        "complete_domain_nodes_rc": nodes,
        "boundary_ambiguity_m": BOUNDARY_M,
        "all_external_waterbodies": records,
        "all_original_clipped_line_parts": [
            {
                "clip": n,
                "source_scope": c["source_scope"],
                **membership(c["nodes_rc"], index, masks),
            }
            for n, c in sorted(clips.items())
        ],
        "all_19_coastal_open_port_components": [
            {
                "component": c["id"],
                "source_clips": c["source_clips"],
                "full_in_square_bank_union": membership(
                    bank_nodes(old, c), index, masks
                ),
                "raw_classified_bank_membership": {
                    k: membership(
                        bank_nodes(old, c),
                        index,
                        {n: masks[n] for n in v if n in masks},
                    )
                    for k, v in sorted(groups.items())
                },
                "physical_admission": False,
            }
            for c in ports
        ],
        "original_source_mask_or_geometry_changed": False,
        "new_physical_or_native": False,
        "raster_v1_unchanged_and_not_replaced": True,
        "provider_accuracy_or_hydraulic_qualification": None,
    }
    write(output / "coverage.json", result)
    write(
        output / "receipt.json",
        {
            "prospective_freeze_sha256": sha(folder / "freeze.json"),
            "coverage_sha256": sha(output / "coverage.json"),
            "new_physical_or_native": False,
        },
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for n, args in (
        ("stage", ["parent", "raster_results", "output"]),
        ("preflight", ["folder"]),
        ("evaluate", ["folder", "output"]),
    ):
        q = sub.add_parser(n)
        for a in args:
            q.add_argument(a, type=Path)
    args = vars(p.parse_args())
    globals()[args.pop("command")](**args)
