"""Package CPU-passed experimental plans; never update shipping fixtures."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np

from minor_stream_candidate import inspect_package, SLUGS
from paint import paint
from probe_held_dem_design import q

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package(plans, output, only):
    manifest = json.loads((ROOT / "fixtures/manifest.json").read_text())
    # Fail before writing ANY package when any map lacks its complete preflight.
    for slug in only:
        report = json.loads((plans / slug / "report.json").read_text())
        assert report["model_regression_count"] == 0, slug
        assert report["source_footprint_error"] is None, slug
        assert report["new_planned_continuous_floor_guard"], slug
        assert report["horizontal_network_unchanged"], slug
        case = next(c for c in manifest["cases"] if c["slug"] == slug)
        for name, digest in case["files_sha256"].items():
            assert sha(ROOT / "fixtures" / slug / name) == digest, (slug, name)
    results = []
    for slug in only:
        fixture, plan = ROOT / "fixtures" / slug, plans / slug
        out = output / slug
        out.mkdir(parents=True, exist_ok=False)
        arrays = np.load(plan / "design-grids.npz")
        for field, name in [("ground", "terrain.u16"), ("initial_depth", "water.u16")]:
            q(arrays[field]).tofile(out / name)
        shutil.copyfile(plan / "hydrology.json", out / "hydrology.json")
        for name in ["geometry.json", "source-geometry.json"]:
            (out / name).write_bytes(
                gzip.decompress((fixture / "shipping-geometry.json.gz").read_bytes())
            )
        (out / "banks.f32").write_bytes(
            gzip.decompress((fixture / "banks.f32.gz").read_bytes())
        )
        painted = paint(
            out,
            fixture / "landcover.u8.gz",
            out,
            out / "geometry.json",
            fixture / "shipping-evidence.json"
            if (fixture / "shipping-evidence.json").exists()
            else None,
        )
        hydro = json.loads((out / "hydrology.json").read_text())
        result = {
            "preparation": {
                k: v
                for k, v in hydro.items()
                if k not in ["samples", "node_positions", "sources", "rivers"]
            },
            "package": painted["package"],
            "resources": {
                **{k: painted[k] for k in ["knobs", "trees", "unlockable", "placed"]},
                "prepared_geometry_sha256": sha(out / "geometry.json"),
            },
            "source": {"inputs_sha256": {"geometry.json": sha(out / "geometry.json")}},
            "resource_plan": {"file": "plan.npz", "sha256": sha(out / "plan.npz")},
            "prefill": True,
            "in_game_verified": False,
            "experimental_cpu_plan": {
                "sha256": sha(plan / "design-grids.npz"),
                "report_sha256": sha(plan / "report.json"),
            },
        }
        (out / "generation.json").write_text(json.dumps(result, indent=2) + "\n")
        inspect_package(out)
        results.append(
            {
                "slug": slug,
                "crp_sha256": painted["package"]["sha256"],
                "grids_sha256": {
                    name: sha(out / name) for name in ["terrain.u16", "water.u16"]
                },
            }
        )
        print(json.dumps(results[-1]), flush=True)
    (output / "packages.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plans", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--only",
        nargs="+",
        choices=SLUGS,
        default=SLUGS,
        help="Subset for a bounded short diagnostic; never qualifies the rest",
    )
    args = parser.parse_args()
    package(args.plans, args.output, args.only)
