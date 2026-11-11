"""Stage exact reference maps and run foreground native hydraulic checks.

Staging does not need Steam. Execution uses the separately checked-out CS1
harness, serially, and leaves its account-conflict/session guards intact.
"""

import argparse
import gzip
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess

import numpy as np

from crp import Reader, metadata_value, read_package, write_map
from region import raster
from surface_water import surface_geometry

ROOT = Path(__file__).resolve().parent


def mapped_water_reference(data, geometry, folder):
    """Freeze unbuffered geographic channels, not water observed after a run."""
    geometry, _ = surface_geometry(geometry)
    mask = np.zeros((1081, 1081), dtype=bool)
    for field in ["rivers", "streams"]:
        mask |= raster(geometry["sq"], geometry.get(field, []))
    for field in ["lakes", "riverAreas"]:
        mask |= raster(geometry["sq"], geometry.get(field, []), polygons=True)
    raw = np.flipud(mask).astype(np.uint8).tobytes()
    (folder / "mapped-water.u8").write_bytes(raw)
    data["mapped_water"] = {
        "file": "mapped-water.u8",
        "format": "cs1-water-mask-u8-v1",
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    data["mapped_water_provenance"] = {
        "geometry_sha256": hashlib.sha256(
            json.dumps(geometry, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "fields": ["rivers", "streams", "lakes", "riverAreas"],
        "buffer_m": 0,
        "frame": "1081-square uint8 south-first; x=ix*16-8640,z=iz*16-8640",
    }


def world_references(data, geometry, landmarks=None):
    sq = geometry["sq"]
    # PR #22 uses Cartesian counterclockwise angles; the browser square uses
    # clockwise angles. Its independent pyproj frame must represent the same
    # physical footprint without sharing the writer's pixel conversion.
    frame = {
        "lon": sq["lon"],
        "lat": sq["lat"],
        "size_m": 17280 * sq["scale"],
        "rotation": -sq["rotation"],
    }
    if landmarks is not None:
        data["landmark_expectations"] = landmarks
        frame["landmarks"] = [
            {k: point[k] for k in ["name", "lat", "lon"]}
            for point in landmarks["points"]
        ]
    data["ground_truth"] = frame


def panel_expectations(crp):
    """Require native selection to agree with the exact package being tested."""
    _, assets = read_package(crp.read_bytes())
    r = Reader(next(a["payload"] for a in assets if a["kind"] == 100))
    if r.number("B") or not r.string().startswith("MapMetaData,"):
        raise ValueError("Expected native map metadata")
    r.string()
    fields = {}
    for _ in range(r.number("i")):
        if r.number("B"):
            continue
        typename, name = r.string().split(",")[0], r.string()
        fields[name] = metadata_value(r, typename)
    return {
        "map_name": fields["mapName"],
        "author": "",
        "require_resource_bars": True,
        "require_window_capture": True,
        "buildableArea": fields["buildableArea"],
        "resources": {
            k: fields[k]
            for k in [
                "maxResourceAmount",
                "oilAmount",
                "oreAmount",
                "forestAmount",
                "fertileLandAmount",
                "waterAmount",
            ]
        },
        "connections": {
            direction + kind: fields[direction + kind]
            for direction in ["incoming", "outgoing"]
            for kind in ["Roads", "TrainTracks", "ShipPath", "PlanePath"]
        },
    }


def probes_for(hydro, descriptor):
    """Native water probes and complete authored network routes for one map."""
    points = [
        {"name": f"{name}:{i:02d}", "x": point[0], "z": point[2]}
        for name, positions in hydro["samples"].items()
        for i, point in enumerate(positions)
    ]
    pairs = {frozenset((s["from"], s["to"])): s["id"] for s in descriptor["segments"]}
    paths = []
    for route in descriptor["routes"]:
        nodes = route["nodes"]
        segments = [pairs[frozenset(pair)] for pair in zip(nodes, nodes[1:])]
        lane = 1 if route["kind"] == "rail" else 0
        paths.append(
            {
                "name": route["kind"],
                "from": [segments[0], lane, 128],
                "to": [segments[-1], lane, 128],
                "rail": route["kind"] == "rail",
                "expected_segments": segments,
            }
        )
    tile = hydro["start_tile"]
    return {
        "points": points,
        "paths": paths,
        "startup_views": {
            "opening": {"native_yaw_degrees": 0, "render_heading_degrees": 0},
            "area_zoom": {"native_yaw_degrees": 0, "render_heading_degrees": 0},
            "tolerance_degrees": 1,
            "opening_center": {
                "x": (tile % 5 - 2) * 1920,
                "z": (tile // 5 - 2) * 1920,
                "tolerance_m": 64,
            },
        },
        "views": [
            {
                "name": "start-tile",
                "x": (tile % 5 - 2) * 1920,
                "z": (tile // 5 - 2) * 1920,
                "size": 1000,
                "yaw": 0,
                "pitch": 60,
            },
            {"name": "overview", "x": 0, "z": 0, "size": 4000, "yaw": 0, "pitch": 70},
        ],
    }


def stage(output, slugs):
    """Reproduce golden packages, with every committed waterway sample as a probe."""
    fixtures = ROOT / "fixtures"
    manifest = json.loads((fixtures / "manifest.json").read_text())
    cases = {case["slug"]: case for case in manifest["cases"]}
    if unknown := set(slugs) - cases.keys():
        raise ValueError(f"Unknown fixture regions: {sorted(unknown)}")
    template, layout = ROOT / manifest["template"], ROOT / manifest["layout"]
    if hashlib.sha256(template.read_bytes()).hexdigest() != manifest["template_sha256"]:
        raise ValueError("Fixture template checksum changed")
    staged = []
    for slug in slugs:
        case = cases[slug]
        folder = output / "maps" / slug
        folder.mkdir(parents=True, exist_ok=True)
        for name in ["terrain.u16", "water.u16", "hydrology.json"]:
            encoded = (fixtures / slug / (name + ".gz")).read_bytes()
            if (
                hashlib.sha256(encoded).hexdigest()
                != case["files_sha256"][name + ".gz"]
            ):
                raise ValueError(f"Fixture checksum changed: {slug}/{name}.gz")
            (folder / name).write_bytes(gzip.decompress(encoded))
        crp = folder / f"PL857-{slug}.crp"
        resource_plan = None
        if case.get("resource_plan"):
            from paint import load_plan
            from resources import TREE_NAMES

            plan = fixtures / slug / case["resource_plan"]
            if (
                hashlib.sha256(plan.read_bytes()).hexdigest()
                != case["files_sha256"][plan.name]
            ):
                raise ValueError(f"Fixture resource plan changed: {slug}")
            resource_plan = (load_plan(plan), TREE_NAMES)
        receipt = write_map(
            template,
            layout,
            folder / "terrain.u16",
            folder / "water.u16",
            folder / "hydrology.json",
            crp,
            resources=resource_plan,
        )
        if receipt["sha256"] != case["expected_crp_sha256"]:
            raise ValueError(f"CRP reference mismatch: {slug}")
        hydro = json.loads((folder / "hydrology.json").read_text())
        probes = folder / "probes.json"
        data = probes_for(hydro, json.loads(layout.read_text()))
        data["new_game_panel"] = panel_expectations(crp)
        landmarks = fixtures / slug / "landmarks.json"
        geometry_bytes = (fixtures / slug / "geometry.json.gz").read_bytes()
        if (
            hashlib.sha256(geometry_bytes).hexdigest()
            != case["files_sha256"]["geometry.json.gz"]
        ):
            raise ValueError(f"Fixture geometry changed: {slug}")
        geometry = json.loads(gzip.decompress(geometry_bytes))
        mapped_water_reference(data, geometry, folder)
        world_references(
            data,
            geometry,
            json.loads(landmarks.read_text()) if landmarks.exists() else None,
        )
        probes.write_text(json.dumps(data, indent=2) + "\n")
        receipt.update({"slug": slug, "probes": len(data["points"])})
        (folder / "staging.json").write_text(json.dumps(receipt, indent=2) + "\n")
        staged.append((slug, crp, probes))
    return staged


def prepared_geometry(source, generation):
    """Bind acceptance geometry before staging; legacy unpainted inputs stay supported."""
    resources = generation.get("resources")
    resource_candidate = (
        resources is not None
        or generation.get("resource_plan") is not None
        or (source / "plan.npz").is_file()
    )
    declared = []
    if resource_candidate:
        expected = (
            resources.get("prepared_geometry_sha256")
            if isinstance(resources, dict)
            else None
        )
        declared.append(("resources.prepared_geometry_sha256", expected))
    # Enforce an existing declared unpainted input hash too; do not create a
    # caller-controlled opt-out for a resource candidate's required binding.
    inputs = generation.get("source", {}).get("inputs_sha256", {})
    if "geometry.json" in inputs:
        declared.append(("source.inputs_sha256.geometry.json", inputs["geometry.json"]))
    for field, expected in declared:
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError(f"Missing/malformed prepared geometry binding: {field}")
    path = source / "geometry.json"
    if not path.exists() and not declared:
        return None, None
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    for field, expected in declared:
        if actual != expected:
            raise ValueError(f"Prepared geometry changed since generation: {field}")
    json.loads(raw)  # reject unusable geometry before generating/staging the package
    return raw, {
        "file": "geometry.json",
        "sha256": actual,
        "generation_fields": [field for field, _ in declared],
        "binding": "generation"
        if declared
        else "legacy unpainted (no declared input hash)",
    }


def stage_prepared(inputs, output, slugs):
    """Check candidate bytes against their generation receipt before native testing."""
    staged = []
    template, layout = (
        ROOT / "templates/native-corridors.crp",
        ROOT / "templates/native-corridors.json",
    )
    for slug in slugs:
        source, folder = inputs / slug, output / "maps" / slug
        generation = json.loads((source / "generation.json").read_text())
        geometry_raw, geometry_binding = prepared_geometry(source, generation)
        folder.mkdir(parents=True, exist_ok=True)
        if geometry_raw is not None:
            (folder / "geometry.json").write_bytes(geometry_raw)
        for name in ["terrain.u16", "water.u16", "hydrology.json"]:
            shutil.copyfile(source / name, folder / name)
        hydro = json.loads((folder / "hydrology.json").read_text())
        crp = folder / (hydro["map_id"] + ".crp")
        resource_plan = None
        plan_path = source / "plan.npz"
        plan_binding = generation.get("resource_plan")
        if (
            plan_binding is not None or generation.get("resources")
        ) and not plan_path.is_file():
            raise ValueError(f"Prepared resource candidate is missing plan.npz: {slug}")
        if plan_path.is_file():
            from paint import load_plan
            from resources import TREE_NAMES

            plan_sha256 = hashlib.sha256(plan_path.read_bytes()).hexdigest()
            if plan_binding is not None and (
                plan_binding.get("file") != "plan.npz"
                or plan_binding.get("sha256") != plan_sha256
            ):
                raise ValueError(
                    f"Prepared resource plan changed since generation: {slug}"
                )
            shutil.copyfile(plan_path, folder / "plan.npz")
            resource_plan = (load_plan(folder / "plan.npz"), TREE_NAMES)
        receipt = write_map(
            template,
            layout,
            folder / "terrain.u16",
            folder / "water.u16",
            folder / "hydrology.json",
            crp,
            resources=resource_plan,
        )
        if receipt["sha256"] != generation["package"]["sha256"]:
            raise ValueError(f"Prepared candidate changed since generation: {slug}")
        data = probes_for(hydro, json.loads(layout.read_text()))
        data["new_game_panel"] = panel_expectations(crp)
        if geometry_raw is not None:
            geometry = json.loads(geometry_raw)
            mapped_water_reference(data, geometry, folder)
            data["mapped_water_provenance"]["source_geometry"] = geometry_binding
            world_references(
                data,
                geometry,
                json.loads((source / "landmarks.json").read_text())
                if (source / "landmarks.json").exists()
                else None,
            )
        if (source / "probes.json").exists():
            data["views"] = json.loads((source / "probes.json").read_text()).get(
                "views", []
            )
            for view in data["views"]:
                if view["name"] == "start-tile":
                    # Water preparation can select a different starting tile.
                    # Camera evidence must follow this package, not a prior run.
                    view["x"], view["z"] = hydro["start_area"]["landing"]
        probes = folder / "probes.json"
        probes.write_text(json.dumps(data, indent=2) + "\n")
        receipt.update(
            slug=slug,
            source_kind="prepared candidate",
            prefill=generation.get("prefill", True),
            geometry=geometry_binding,
        )
        if resource_plan is not None:
            receipt["resource_plan_sha256"] = plan_sha256
            receipt["generation"] = {
                "path": str(source / "generation.json"),
                "sha256": hashlib.sha256(
                    (source / "generation.json").read_bytes()
                ).hexdigest(),
            }
            source_crp = source / crp.name
            if hashlib.sha256(source_crp.read_bytes()).hexdigest() != receipt["sha256"]:
                raise ValueError(
                    f"Prepared resource package differs from its receipt: {slug}"
                )
        (folder / "staging.json").write_text(json.dumps(receipt, indent=2) + "\n")
        staged.append((slug, crp, probes))
    return staged


def summarize(report):
    """Keep failing waterways visible, rather than burying them in a total."""
    waterways = {}
    for point in report["points"]:
        name = point["name"].rsplit(":", 1)[0]
        row = waterways.setdefault(
            name, {"points": 0, "wet_end": 0, "ever_dry": 0, "minimum_depth_m": None}
        )
        row["points"] += 1
        row["wet_end"] += int(point["wet_end"])
        row["ever_dry"] += int(point["dry_samples"] > 0)
        minimum = row["minimum_depth_m"]
        row["minimum_depth_m"] = (
            point["depth_min"] if minimum is None else min(minimum, point["depth_min"])
        )
    return {
        "game_minutes": report["game_minutes"],
        "wall_seconds": report["wall_seconds"],
        "published_map": report["map"]["published"],
        "enabled_mod_count": report["menu_status"]["enabled_mod_count"],
        "strict_disableMods": False,
        "points_wet_start": report["points_wet_start"],
        "points_wet_end": report["points_wet_end"],
        "waterways": waterways,
        "extent": report["water"],
        "gpu": report["gpu"],
        "vram": report["vram"],
        "cleanup": report.get("session", {}).get("cleanup"),
        "paths_start": report.get("paths_start"),
        "paths_end": report.get("paths_end"),
        "not_verified": [
            "ordinary menu interaction with --disableMods",
            "absence of flooding requires grid and screenshot review",
        ]
        + ([] if report.get("paths_end") else ["native outside-connection paths"]),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--only",
        nargs="+",
        default=["asheville", "innsbruck", "rio", "pittsburgh", "charleston"],
    )
    parser.add_argument(
        "--harness",
        type=Path,
        help="tools/cs1-harness directory; omit to stage without launching",
    )
    parser.add_argument("--game-minutes", type=float, default=60)
    parser.add_argument(
        "--prepared",
        type=Path,
        help="Candidate case directories with generation receipts, instead of golden fixtures",
    )
    args = parser.parse_args()
    if args.game_minutes <= 0:
        parser.error("--game-minutes must be positive")
    output = args.output.resolve()
    cases = (
        stage_prepared(args.prepared.resolve(), output, args.only)
        if args.prepared
        else stage(output, args.only)
    )
    for slug, crp, probes in cases:
        print(
            f"{slug}: {'candidate' if args.prepared else 'exact reference'} map and probes staged",
            flush=True,
        )
        if args.harness is None:
            continue
        run = output / slug
        run.mkdir(parents=True, exist_ok=True)
        if (run / "report.json").exists():
            raise ValueError(f"Run already exists; use a fresh output directory: {run}")
        # Keep the child foreground: no game or test survives this command.
        with (run / "driver.log").open("w") as log:
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "--locked",
                    "cs1-harness",
                    "run",
                    "--map",
                    str(crp),
                    "--probes",
                    str(probes),
                    "--game-minutes",
                    str(args.game_minutes),
                    "--wait-minutes",
                    "120",
                    "--retry-minutes",
                    "30",
                    "--out",
                    str(run),
                ],
                cwd=args.harness.resolve(),
                stdout=log,
                stderr=log,
                check=False,
            )
        if result.returncode:
            raise SystemExit(
                f"{slug}: harness exited {result.returncode}; see {run / 'driver.log'}"
            )
        summary = summarize(json.loads((run / "report.json").read_text()))
        summary["map_sha256"] = hashlib.sha256(crp.read_bytes()).hexdigest()
        (run / "hydraulic-summary.json").write_text(
            json.dumps(summary, indent=2) + "\n"
        )
        print(
            f"{slug}: {summary['points_wet_end']}/{sum(r['points'] for r in summary['waterways'].values())} probes wet at end",
            flush=True,
        )


if __name__ == "__main__":
    main()
