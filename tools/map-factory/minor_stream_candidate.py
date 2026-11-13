"""Regenerate PL-912 CPU candidates from pinned shipping inputs; never launch CS1.

Accepted fixtures and native receipts stay immutable. OUTPUT contains maps that
soak.py --prepared can stage, compressed candidate grids and a before/after PNG.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct

import numpy as np
from PIL import Image, ImageDraw

from generate import generate
from crp import N, decode_u16, read_package
from region import raster
from surface_water import surface_geometry
from template import manager_tag

ROOT = Path(__file__).resolve().parent
SLUGS = ["asheville", "innsbruck", "rio", "pittsburgh", "charleston"]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def grid(raw):
    return (
        np.flipud(np.frombuffer(raw, dtype="<u2").reshape(1081, 1081)).astype(float)
        / 64
    )


def panel(terrain, water):
    dy, dx = np.gradient(terrain, 16)
    shade = np.clip(0.72 + (dx - dy) / 1.5, 0.25, 1)
    rgb = shade[..., None] * np.array([195, 192, 173])
    rgb[water > 0.1] = [50, 125, 205]
    return Image.fromarray(rgb.astype(np.uint8))


def inspect_package(work):
    """Decode actual candidate bytes and preserve template topology/lane fields."""
    hydro = json.loads((work / "hydrology.json").read_text())
    spec = json.loads((ROOT / "templates/native-corridors.json").read_text())
    _, original = read_package((ROOT / "templates/native-corridors.crp").read_bytes())
    _, assets = read_package((work / (hydro["map_id"] + ".crp")).read_bytes())
    before = next(a["payload"] for a in original if a["kind"] == 52)
    actual = next(a["payload"] for a in assets if a["kind"] == 52)
    for name, manager in [
        ("terrain.u16", "TerrainManager"),
        ("water.u16", "WaterSimulation"),
    ]:
        tag = manager_tag(manager)
        start = actual.index(tag) + len(tag)
        decoded, _ = decode_u16(actual, N, start)
        np.testing.assert_array_equal(decoded, np.fromfile(work / name, dtype="<u2"))
    net = next(r for r in spec["ranges"] if r["type"] == "NetManager+Data")
    shift = actual.index(manager_tag("NetManager")) - net["start"]
    expected_net = bytearray(before[net["start"] : net["end"]])
    actual_net = bytearray(actual[net["start"] + shift : net["end"] + shift])
    for node in spec["nodes"]:
        at = node["offset"] - net["start"]
        position = struct.pack(">3f", *hydro["node_positions"][str(node["id"])])
        assert actual_net[at : at + 12] == position
        actual_net[at : at + 12] = expected_net[at : at + 12]
    for segment in spec["segments"]:
        at = segment["direction_offset"] - net["start"]
        vectors = struct.unpack_from(">6f", actual_net, at)
        assert abs(sum(v * v for v in vectors[:3]) - 1) < 1e-5
        assert all(abs(a + b) < 1e-6 for a, b in zip(vectors[:3], vectors[3:]))
        actual_net[at : at + 24] = expected_net[at : at + 24]
    assert actual_net == expected_net, "Unexpected topology or lane mutation"


def run(output):
    accepted = ROOT / "fixtures"
    manifest = json.loads((accepted / "manifest.json").read_text())
    report = {
        "status": "CPU candidate only; new native qualification required",
        "baseline": "c6ab58a",
        "writer_sha256": sha((ROOT / "region.py").read_bytes()),
        "cases": [],
    }
    sheet = Image.new("RGB", (1500, len(SLUGS) * 550), "#faf9f5")
    draw = ImageDraw.Draw(sheet)
    for index, slug in enumerate(SLUGS):
        fixture = accepted / slug
        case = next(c for c in manifest["cases"] if c["slug"] == slug)
        work = output / "inputs" / slug
        work.mkdir(parents=True, exist_ok=True)
        # Verify pinned inputs before reusing them, including shipping feature order.
        for name in [
            "input.png",
            "banks.f32.gz",
            "shipping-geometry.json.gz",
            "landcover.u8.gz",
            "shipping-evidence.json",
        ]:
            path = fixture / name
            if name not in case["files_sha256"]:
                assert name == "shipping-evidence.json"
                continue
            assert sha(path.read_bytes()) == case["files_sha256"][name], (slug, name)
        (work / "banks.f32").write_bytes(
            gzip.decompress((fixture / "banks.f32.gz").read_bytes())
        )
        (work / "source-geometry.json").write_bytes(
            gzip.decompress((fixture / "shipping-geometry.json.gz").read_bytes())
        )
        result = generate(
            fixture / "input.png",
            work / "source-geometry.json",
            work,
            work / "banks.f32",
            landcover=fixture / "landcover.u8.gz",
            evidence=fixture / "shipping-evidence.json"
            if (fixture / "shipping-evidence.json").exists()
            else None,
        )
        inspect_package(work)
        hydro = json.loads((work / "hydrology.json").read_text())
        old_hydro = json.loads(
            gzip.decompress((fixture / "hydrology.json.gz").read_bytes())
        )
        # No deleted probes, changed acceptance geometry or starting-tile relocation.
        assert hydro["samples"].keys() == old_hydro["samples"].keys(), slug
        assert hydro["start_tile"] == old_hydro["start_tile"], slug
        assert hydro["node_positions"].keys() == old_hydro["node_positions"].keys(), (
            slug
        )
        for key, before in old_hydro["node_positions"].items():
            after = hydro["node_positions"][key]
            assert before[::2] == after[::2], (slug, key, "horizontal network moved")
        geometry, _ = surface_geometry(json.loads((work / "geometry.json").read_text()))
        major = raster(geometry["sq"], geometry.get("rivers", []))
        detail = {
            "slug": slug,
            "crp_sha256": result["package"]["sha256"],
            "crp_bytes": result["package"]["bytes"],
            "start_tile": hydro["start_tile"],
            "horizontal_network_unchanged": True,
            "corridors": hydro["corridors"],
            "uncarved_reaches": sum(
                r.get("uncarved_infeasible_stream", False) for r in hydro["rivers"]
            ),
            "grids": {},
        }
        images = {}
        frozen = output / "fixtures" / slug
        frozen.mkdir(parents=True, exist_ok=True)
        for name in ["terrain.u16", "water.u16"]:
            before = gzip.decompress((fixture / (name + ".gz")).read_bytes())
            after = (work / name).read_bytes()
            a, b = grid(before), grid(after)
            delta = b - a
            detail["grids"][name] = {
                "before_sha256": sha(before),
                "after_sha256": sha(after),
                "changed_bytes": sum(x != y for x, y in zip(before, after)),
                "changed_cells": int(np.count_nonzero(delta)),
                "min_delta_m": float(delta.min()),
                "max_delta_m": float(delta.max()),
                "major_line_changed_cells": int(np.count_nonzero(delta[major])),
            }
            (frozen / (name + ".gz")).write_bytes(gzip.compress(after, mtime=0))
            images[name] = (a, b)
        (frozen / "hydrology.json.gz").write_bytes(
            gzip.compress((work / "hydrology.json").read_bytes(), mtime=0)
        )
        old_t, new_t = images["terrain.u16"]
        old_w, new_w = images["water.u16"]
        detail["major_initial_wet_cells"] = [
            int((old_w[major] > 0.1).sum()),
            int((new_w[major] > 0.1).sum()),
        ]
        assert not ((old_w > 0.1) & (new_w <= 0.1) & major).any(), slug
        # Crop the actual selected start tile plus one tile each side (central 3x3).
        start = hydro["start_tile"]
        cx, cy = 540 + (start % 5 - 2) * 120, 540 - (start // 5 - 2) * 120
        crop = (
            max(0, cx - 180),
            max(0, cy - 180),
            min(1081, cx + 180),
            min(1081, cy + 180),
        )
        delta = np.full((1081, 1081, 3), 225, dtype=np.uint8)
        delta[new_t > old_t] = [205, 70, 40]
        delta[new_t < old_t] = [125, 60, 175]
        delta[new_w != old_w] = [30, 125, 200]
        for column, (label, picture) in enumerate(
            [
                ("BEFORE: accepted prepared grids", panel(old_t, old_w)),
                ("AFTER: CPU candidate grids", panel(new_t, new_w)),
                (
                    "CHANGE: red=raised, purple=lowered, blue=water",
                    Image.fromarray(delta),
                ),
            ]
        ):
            y = index * 550
            draw.text((column * 500 + 10, y + 10), f"{slug} | {label}", fill="black")
            draw.text(
                (column * 500 + 10, y + 30),
                "Start tile + neighbors; terrain rendering, NOT a game capture",
                fill="black",
            )
            sheet.paste(
                picture.crop(crop).resize((490, 490)), (column * 500 + 5, y + 55)
            )
        report["cases"].append(detail)
        print(json.dumps(detail), flush=True)
    sheet.save(output / "before-after.png")
    (output / "fixtures" / "manifest.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
