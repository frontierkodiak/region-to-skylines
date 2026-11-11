"""Prepare and qualify experimental compound resource candidates, entirely offline.

Uses existing prepared terrain/water/hydrology and pinned land-cover/evidence.
Repeats planning, replays the frozen plan, and stages exact packages. Does not
freeze golden checksums, run the game, or assert native acceptance.
"""

import argparse
from dataclasses import asdict
from io import BytesIO
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

import numpy as np
from PIL import Image

from crp import N, Reader, decode_u16, read_package
from map_metadata import buildable_area
from paint import load_plan, paint
from resources import Knobs
from soak import stage_prepared
from template import manager_tag, saved_camera
from verify_resources import M, check

ROOT = Path(__file__).resolve().parent
RESOURCE_REVISION = "0d3b873a903bca0275fcc90e110fc222e41e5e0f"
WRITER_REVISION = "fb77e74cb3c64801044c8b231d1265205d006cab"
SLUGS = ["asheville", "innsbruck", "rio", "pittsburgh", "charleston"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def inspect(folder, original, evidence):
    """Survey decoder checks plus latest writer metadata/camera preservation."""
    hydro = json.loads((folder / "hydrology.json").read_text())
    crp = folder / (hydro["map_id"] + ".crp")
    problems, facts = check(crp, evidence)
    if problems:
        raise ValueError(problems)
    if facts["forest_formula_match"] != 1:
        raise ValueError(
            "Forest does not match independently decoded tree positions exactly"
        )
    package, assets = read_package(crp.read_bytes())
    data = next(a["payload"] for a in assets if a["kind"] == 52)
    meta = M.parse_metadata(next(a["payload"] for a in assets if a["kind"] == 100))
    raw = np.fromfile(folder / "terrain.u16", dtype="<u2")
    depth = np.fromfile(folder / "water.u16", dtype="<u2")
    maximum = 25 * (1920 / 33.75) ** 2 * 255
    assert package["author"] == "" and meta["mapName"] == hydro["map_name"]
    assert meta["buildableArea"] == buildable_area(raw, meta["waterAmount"], maximum)
    assert abs(meta["maxResourceAmount"] - maximum) < 1
    assert meta["assetRef"] == hashlib.md5(data).hexdigest()
    tile = hydro["start_tile"]
    x, z = (tile % 5 - 2) * 1920, (tile // 5 - 2) * 1920
    y = float(raw[(z // 16 + 540) * 1081 + x // 16 + 540] / 64)
    area = M.section(data, "GameAreaManager")
    assert M.parse_start_tile(data, M.data_version(data))[1] == tile
    camera = saved_camera(data, area + 1)
    assert bytes.fromhex(camera["bytes"]) == struct.pack(
        ">h7f", 2, x, y, z, 1000, 0, 60, 0
    )
    grids, areas = M.parse_resources(data, M.data_version(data))
    plan = load_plan(folder / "plan.npz")
    for key in ["ore", "oil", "forest", "fertility", "tree"]:
        assert np.array_equal(grids[key], plan[key]), key
    tiles = (np.arange(512) * 18) >> 10
    water_totals = np.bincount(
        (tiles[:, None] * 9 + tiles[None, :]).ravel(),
        weights=grids["water"].ravel(),
        minlength=81,
    ).reshape(9, 9)
    assert np.array_equal(water_totals, areas["finalWater"])
    for name, expected in [("TerrainManager", raw), ("WaterSimulation", depth)]:
        actual, _ = decode_u16(data, N, M.section(data, name))
        assert np.array_equal(actual, expected), name
    _, original_assets = read_package(original.read_bytes())
    original_data = next(a["payload"] for a in original_assets if a["kind"] == 52)
    spec = json.loads((ROOT / "templates/native-corridors.json").read_text())
    net = next(r for r in spec["ranges"] if r["type"] == "NetManager+Data")
    size = net["end"] - net["start"]
    tag = manager_tag("NetManager")
    before, after = original_data.index(tag), data.index(tag)
    assert original_data[before : before + size] == data[after : after + size], (
        "Network changed while painting"
    )
    checksums = {hashlib.md5(a["payload"]).hexdigest(): a for a in assets}
    previews = {}
    for field, size in [("imageRef", (400, 224)), ("steamPreviewRef", (1800, 1008))]:
        asset = checksums[meta[field]]
        assert asset["kind"] == 3
        texture = Reader(asset["payload"])
        assert texture.number("B") == 0
        assert texture.string().startswith("ColossalFramework.Importers.Image,")
        assert texture.string() == asset["name"]
        assert texture.number("B") == 0 and texture.number("i") == 1
        png = texture.take(texture.number("i"))
        assert texture.pos == len(asset["payload"])
        with Image.open(BytesIO(png)) as image:
            image.load()
            assert image.format == "PNG" and image.size == size
            assert np.asarray(image).std() > 10
        previews[field] = {
            "asset_md5": meta[field],
            "size": size,
            "png_sha256": hashlib.sha256(png).hexdigest(),
        }
    return {
        **facts,
        "buildableArea": meta["buildableArea"],
        "camera": camera,
        "previews": previews,
        "checks": [
            "manager tails",
            "exact forest from tree positions",
            "grown theme-compatible trees",
            "exclusive ore/oil",
            "no invented start-tile ore/oil",
            "per-cell and per-tile resource amounts",
            "painted grids equal frozen plan",
            "terrain/water unchanged",
            "complete network bytes unchanged",
            "north-facing mode-2 camera",
            "blank author",
            "resolved decodable preview PNGs",
            "resource-path buildable score",
        ],
    }


def qualify(prepared, inputs, output, stage):
    output.mkdir(parents=True, exist_ok=True)
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT), (
        "Commit qualification source first"
    )
    pinned_sampler = subprocess.check_output(
        ["git", "show", f"{RESOURCE_REVISION}:tools/map-factory/landcover.py"], cwd=ROOT
    )
    rows = []
    for slug in SLUGS:
        source, resource, folder = prepared / slug, inputs / slug, output / slug
        if folder.exists():
            raise ValueError(f"Use a fresh candidate directory: {folder}")
        source_receipt = json.loads((source / "generation.json").read_text())
        hydro = json.loads((source / "hydrology.json").read_text())
        source_crp = source / (hydro["map_id"] + ".crp")
        assert sha(source_crp) == source_receipt["package"]["sha256"]
        cover = json.loads((resource / "landcover.json").read_text())
        assert sha(resource / "landcover.u8.gz") == cover["landcover_sha256"]
        assert sha(resource / "geometry.json") == cover["geometry_sha256"]
        assert hashlib.sha256(pinned_sampler).hexdigest() == cover["sampler_sha256"]
        assert json.loads((source / "geometry.json").read_text()) == json.loads(
            (resource / "geometry.json").read_text()
        )
        evidence_file = resource / "evidence.json"
        if evidence_file.exists():
            pinned_evidence = subprocess.check_output(
                [
                    "git",
                    "show",
                    f"{RESOURCE_REVISION}:tools/map-factory/fixtures/{slug}/evidence.json",
                ],
                cwd=ROOT,
            )
            assert evidence_file.read_bytes() == pinned_evidence
        evidence = (
            json.loads(evidence_file.read_text())["evidence"]
            if evidence_file.exists()
            else []
        )
        report = paint(
            source,
            resource / "landcover.u8.gz",
            folder,
            resource / "geometry.json",
            evidence_file if evidence_file.exists() else None,
            Knobs(),
        )
        for name in ["geometry.json", "landmarks.json", "probes.json"]:
            if (source / name).exists():
                shutil.copyfile(source / name, folder / name)
        for name in ["landcover.u8.gz", "landcover.json", "evidence.json"]:
            if (resource / name).exists():
                shutil.copyfile(resource / name, folder / name)
        for name in ["terrain.u16", "water.u16", "hydrology.json"]:
            assert sha(source / name) == sha(folder / name)
        crp = folder / source_crp.name
        with tempfile.TemporaryDirectory(prefix=f"{slug}-repeat-", dir=output) as tmp:
            repeat, replay = Path(tmp) / "repeat", Path(tmp) / "replay"
            repeated = paint(
                source,
                resource / "landcover.u8.gz",
                repeat,
                resource / "geometry.json",
                evidence_file if evidence_file.exists() else None,
                Knobs(),
            )
            replayed = paint(folder, None, replay, plan=folder / "plan.npz")
            assert (
                repeated["package"]["sha256"]
                == replayed["package"]["sha256"]
                == sha(crp)
            )
            assert sha(repeat / "plan.npz") == sha(folder / "plan.npz")
        findings = inspect(folder, source_crp, evidence)
        generation = {
            "package": report["package"],
            "prefill": source_receipt.get("prefill", True),
            "in_game_verified": False,
            "qualification": "experimental offline integration; not native acceptance",
            "source": {
                "commit": revision,
                "writer_parent": WRITER_REVISION,
                "resource_parent": RESOURCE_REVISION,
                "prepared": str(source),
                "package_sha256": sha(source_crp),
                "inputs_sha256": {
                    name: sha(source / name)
                    for name in ["terrain.u16", "water.u16", "hydrology.json"]
                },
            },
            "resource_plan": {"file": "plan.npz", "sha256": sha(folder / "plan.npz")},
            "resources": {
                "knobs": asdict(Knobs()),
                "report": "resources.json",
                "report_sha256": sha(folder / "resources.json"),
                "landcover": cover,
                "evidence": "exact pinned PR24 USGS fixture"
                if evidence
                else "no MRDS evidence supplied",
                "evidence_sha256": sha(evidence_file)
                if evidence_file.exists()
                else None,
                "topups": "balanced convention top-ups, not geological/crop evidence",
            },
            "offline_checks": findings,
            "limitations": [
                "Native resources, views and playability unverified",
                "No golden checksums updated",
            ]
            + (
                ["Rio R4 fails flood acceptance; parent will retune water; not a final"]
                if slug == "rio"
                else []
            ),
        }
        write_json(folder / "generation.json", generation)
        rows.append(
            {
                "slug": slug,
                "package_sha256": sha(crp),
                "plan_sha256": sha(folder / "plan.npz"),
                "generation": str(folder / "generation.json"),
                "offline_checks": findings,
            }
        )
        print(
            f"{slug}: deterministic plan/replay and independent offline checks pass; native unverified",
            flush=True,
        )
    staged = stage_prepared(output, stage, SLUGS)
    for slug, crp, probes in staged:
        data = json.loads(probes.read_text())
        assert (
            "new_game_panel" in data
            and "startup_views" in data
            and "ground_truth" in data
        )
        assert (
            data["ground_truth"]["rotation"]
            == -json.loads((output / slug / "geometry.json").read_text())["sq"][
                "rotation"
            ]
        )
        if (output / slug / "landmarks.json").exists():
            assert data["landmark_expectations"] == json.loads(
                (output / slug / "landmarks.json").read_text()
            )
        assert (
            sha(crp)
            == json.loads((output / slug / "generation.json").read_text())["package"][
                "sha256"
            ]
        )
    result = {
        "source_commit": revision,
        "in_game_verified": False,
        "status": "experimental offline qualification only",
        "stage": str(stage),
        "cases": rows,
    }
    write_json(output / "qualification.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["prepared", "inputs", "output", "stage"]:
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    qualify(**{k: v.resolve() for k, v in vars(args).items()})
