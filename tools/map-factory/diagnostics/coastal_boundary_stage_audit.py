"""Fresh complete retained boundary/counter audit; never a native flux model."""

import argparse
import json
from pathlib import Path
import shutil

import numpy as np

from coastal_drawdown_strata import ROOT, interval_metrics, quantiles, sha

POLICY = "calibration/pl1191-construction-v1/development/phase21-boundary-policy.md"
ARMS = {
    "outputs_retained": (
        "low-coast-oceania-dense-interface-attempt-1",
        "dense-source-interface-v1-results",
    ),
    "rates_zero": (
        "low-coast-oceania-rates-zero-attempt-1",
        "remaining-output-zero-v1-derived-results",
    ),
    "sources_absent": (
        "low-coast-oceania-source-absent-attempt-1",
        "source-record-absent-v1-results",
    ),
}


def load(p):
    return json.loads(p.read_text())


def write(p, d):
    p.write_text(json.dumps(d, indent=2, allow_nan=False) + "\n")


def stratum_id(*, ocean, bed, boundary, control):
    if ocean not in (0, 1) or any(v not in range(4) for v in (bed, boundary, control)):
        raise ValueError("Invalid named stratum coordinates")
    return ((ocean * 4 + bed) * 4 + boundary) * 4 + control


def boundary_strip_ids(*, ocean=1, bed=0, control=3):
    return [
        stratum_id(ocean=ocean, bed=bed, boundary=b, control=control) for b in range(4)
    ]


def stage(output_root, output):
    if output.exists():
        raise ValueError("Fresh retained-data protocol required")
    paths = [
        (
            output_root
            / "development-coast/early-drawdown-strata-v1-results/geometry-strata.npz",
            "geometry-strata.npz",
        ),
        (
            output_root
            / "development-coast/early-drawdown-strata-v1-results/result.json",
            "strata-metadata.json",
        ),
        (
            output_root / "phase20-source-response-comparison.json",
            "old-comparison.json",
        ),
        (
            output_root / "PL-1258-review-thread-authenticated.json",
            "review-thread.json",
        ),
    ]
    parent = output_root / "development-coast/source-record-absent-v1"
    for p in sorted((parent / "physical").iterdir()):
        if p.is_file():
            paths.append((p, "physical/" + p.name))
    for name in [
        "native-plan.json",
        "domains.json",
        "query-nodes.i32",
        "geometric-paths.json",
        "source-record-removal.json",
    ]:
        paths.append((parent / name, "source-protocol/" + name))
    proof = {}
    for label, (slug, result_dir) in ARMS.items():
        native = output_root / "development-native" / slug
        result = output_root / "development-coast" / result_dir
        d, receipt = load(result / "result.json"), load(result / "receipt.json")
        if len(d["samples"]) != 61 or receipt["result_sha256"] != sha(
            result / "result.json"
        ):
            raise ValueError("Incomplete or changed accepted cohort")
        hashes = receipt["native_files_sha256"]
        for name in ["result.json", "receipt.json"]:
            paths.append((result / name, label + "/" + name))
        checks = []
        for row in d["samples"]:
            for kind in ["water", "water-ground"]:
                p = native / "grids" / (row["prefix"] + "-" + kind + ".u16")
                if sha(p) != hashes["grids/" + p.name]:
                    raise ValueError("Retained actual grid changed")
                if kind == "water":
                    paths.append((p, label + "/grids/" + p.name))
                checks.append({"prefix": row["prefix"], "kind": kind, "sha256": sha(p)})
        p = native / "grids" / (d["samples"][0]["prefix"] + "-water-ground.u16")
        paths.append((p, label + "/actual-floor.u16"))
        proof[label] = checks
    output.mkdir(parents=True)
    for p, name in paths:
        q = output / name
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, q)
    write(output / "retained-grid-verification.json", proof)
    sources = [
        Path(__file__),
        ROOT / "diagnostics/test_coastal_boundary_stage_audit.py",
        ROOT / POLICY,
        ROOT / "diagnostics/coastal_drawdown_strata.py",
        ROOT / "uv.lock",
    ]
    write(
        output / "freeze.json",
        {
            "schema": "polli.coastal-boundary-stage-audit/1",
            "scope": "Read-only retained data, known outcomes; not outcome-blind or new native",
            "files_sha256": {
                str(p.relative_to(output)): sha(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "source_files_sha256": {
                str(p.relative_to(ROOT)): sha(p) for p in sorted(sources)
            },
        },
    )
    return {"freeze_sha256": sha(output / "freeze.json")}


def preflight(folder):
    f = load(folder / "freeze.json")
    for root, key in [(folder, "files_sha256"), (ROOT, "source_files_sha256")]:
        for name, digest in f[key].items():
            if sha(root / name) != digest:
                raise ValueError("Bound retained input/method changed: " + name)
    return f


def evaluate(folder, output):
    preflight(folder)
    if output.exists():
        raise ValueError("Fresh audit output required")
    with np.load(folder / "geometry-strata.npz") as z:
        ids = z["stratum_ids"]
    metadata = load(folder / "strata-metadata.json")["strata"]
    for r in metadata:
        if r["id"] != stratum_id(
            ocean=int(r["literal_ocean"]),
            bed=r["floor_relative_sea_bin"],
            boundary=r["ocean_edge_distance_bin"],
            control=r["control_distance_bin"],
        ):
            raise ValueError("Frozen axis metadata does not decode consistently")
    ocean = ids // 64 == 1
    map_edge = np.zeros(ids.shape, bool)
    map_edge[[0, -1], :] = True
    map_edge[:, [0, -1]] = True
    strips = boundary_strip_ids()
    assert strips == [67, 71, 75, 79]
    domains = {
        **{"stratum_" + str(i): ids == i for i in range(128)},
        "literal_map_edge": map_edge,
        "literal_ocean_map_edge": map_edge & ocean,
    }
    arms = {}
    for label in ARMS:
        base = folder / label
        d = load(base / "result.json")
        rows = d["samples"]
        floor = np.fromfile(base / "actual-floor.u16", "<u2").reshape(ids.shape)

        def depth(row):
            return np.fromfile(
                base / "grids" / (row["prefix"] + "-water.u16"), "<u2"
            ).reshape(ids.shape)

        initial = depth(rows[0])
        first = rows[0]
        last = [r for r in rows if r["minute"] <= 5][-1]
        traces = []
        for row in rows:
            q = depth(row)
            delta = q.astype("i4") - initial.astype("i4")
            m = ids == 79
            surface = (floor.astype(float) + q) / 64
            wet = q > 6.4
            traces.append(
                {
                    "prefix": row["prefix"],
                    "minute": row["minute"],
                    "before": row["before"],
                    "after": row["after"],
                    "stratum79_depth_delta_q": quantiles(delta[m]),
                    "stratum79_delta_q_distinct_values": int(len(np.unique(delta[m]))),
                    "correct_boundary_strips": [
                        {
                            "stratum_id": int(i),
                            "boundary_bin": b,
                            "control_bin": 3,
                            "vertices": int((ids == i).sum()),
                            "depth_delta_q": quantiles(delta[ids == i]),
                        }
                        for b, i in enumerate(strips)
                    ],
                    "all128_depth_delta_q": [
                        {"id": i, **quantiles(delta[ids == i])} for i in range(128)
                    ],
                    "complete_edge_domains": {
                        name: {
                            "all_vertices": int(mask.sum()),
                            "wet_vertices": int((mask & wet).sum()),
                            "wet_surface_m": quantiles(surface[mask & wet]),
                            "depth_delta_q": quantiles(delta[mask]),
                            "dry_vertices_not_observed_free_surface": int(
                                (mask & ~wet).sum()
                            ),
                        }
                        for name, mask in domains.items()
                        if name.startswith("literal_")
                    },
                }
            )
        early = interval_metrics(
            ids == 79, initial, depth(last), last["minute"] - first["minute"]
        )
        arms[label] = {
            "stratum79_early": early,
            "snapshots": len(rows),
            "elapsed_minutes": rows[-1]["minute"],
            "full_traces": traces,
            "actual_floor_min_q": int(floor.min()),
            "literal_ocean_floor_min_q": int(floor[ocean].min()),
            "floor_zero_nodes": int((floor == 0).sum()),
            "sea_zero_at_or_below_every_actual_floor": bool(np.all(floor >= 0)),
        }
    output.mkdir(parents=True)
    record = {
        "schema": "polli.coastal-boundary-stage-audit-result/1",
        "freeze_sha256": sha(folder / "freeze.json"),
        "primary_stratum79_unchanged": True,
        "axis_erratum": {
            "old_supplemental_strip_ids": [76, 77, 78, 79],
            "actual_old_varying_axis": "control_distance_bin; boundary fixed3",
            "old_labels_incorrectly_said": "boundary_distance_bin; control fixed3",
            "correct_boundary_strip_ids": strips,
            "scope": "Only phase20 supplemental strip fields/thirdplot/associated prose; corestratum79/all128early values and native data unchanged. Preserve old artifacts.",
        },
        "correct_boundary_strip_counts": [int((ids == i).sum()) for i in strips],
        "all128_metadata_axis_coordinates_verified": True,
        "full_grid_vertices": int(ids.size),
        "arms": arms,
        "mechanism_limit": "Uniform sampled integer deltas/counter correlations do NOT establish exact256frame evaporation cadence, physical flux or exclusive sink. Sea parameter causal sensitivity remains unmeasured.",
        "new_native_question": "One sea90→0 parameter-only arm on source-absent parent, preserving initial water/terrain/velocity/fullcohort; diagnosis only, not repair or geographic admission.",
    }
    write(output / "result.json", record)
    write(
        output / "receipt.json",
        {
            "freeze_sha256": sha(folder / "freeze.json"),
            "result_sha256": sha(output / "result.json"),
        },
    )
    return {
        "result_sha256": sha(output / "result.json"),
        "correct_boundary_strip_counts": record["correct_boundary_strip_counts"],
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    c = p.add_subparsers(dest="command", required=True)
    for name, args in [
        ("stage", ["output_root", "output"]),
        ("preflight", ["folder"]),
        ("evaluate", ["folder", "output"]),
    ]:
        s = c.add_parser(name)
        for n in args:
            s.add_argument(n, type=Path)
    args = vars(p.parse_args())
    print(json.dumps(globals()[args.pop("command")](**args), indent=2))
