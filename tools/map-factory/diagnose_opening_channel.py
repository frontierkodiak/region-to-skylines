"""Inspect a source channel against archived native evidence without launching CS1.

This diagnoses the accepted baseline, not the current candidate. Missing mapped
river polygons are reported as missing width evidence, never as proof of a creek.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from region import raster
from surface_water import surface_geometry

ROOT = Path(__file__).resolve().parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_grid(path):
    return np.flipud(np.fromfile(path, dtype="<u2").reshape(1081, 1081)) / 64


def polygon_support_catalog():
    """Missing polygon support does not measure the physical channel width."""
    catalog = []
    for case in json.loads((ROOT / "fixtures/manifest.json").read_text())["cases"]:
        source = ROOT / "fixtures" / case["slug"] / "geometry.json.gz"
        geometry, _ = surface_geometry(json.loads(gzip.decompress(source.read_bytes())))
        areas = raster(geometry["sq"], geometry.get("riverAreas", []), True)
        groups = {}
        for river in geometry.get("rivers", []):
            groups.setdefault(river.get("name") or "unnamed waterway", []).append(river)
        for name, features in sorted(groups.items()):
            mask = raster(geometry["sq"], features)
            if mask.any():
                catalog.append(
                    {
                        "slug": case["slug"],
                        "name": name,
                        "mapped_cells": int(mask.sum()),
                        "polygon_overlap_fraction": float(areas[mask].mean()),
                    }
                )
    return catalog


def diagnose(slug, name, native, output, section_x):
    fixture = ROOT / "fixtures" / slug
    case = next(
        c
        for c in json.loads((ROOT / "fixtures/manifest.json").read_text())["cases"]
        if c["slug"] == slug
    )
    for name_on_disk in ["geometry.json.gz", "banks.f32.gz", "input.png"]:
        assert (
            sha((fixture / name_on_disk).read_bytes())
            == case["files_sha256"][name_on_disk]
        )
    qualification = next(
        c
        for c in json.loads((ROOT / "fixtures/native-qualification.json").read_text())[
            "cases"
        ]
        if c["slug"] == slug
    )
    session = json.loads((native / "session-receipt.json").read_text())
    assert session["map"]["sha256"] == qualification["native_crp_sha256"]
    terrain_raw = (native / "grids/t000-terrain.u16").read_bytes()
    assert sha(terrain_raw) == qualification["prepared_sha256"]["terrain.u16"]
    initial_raw = (native / "grids/t000-water.u16").read_bytes()
    assert sha(initial_raw) == qualification["prepared_sha256"]["water.u16"]
    review = json.loads((native / "startup-views-review.json").read_text())
    assert (
        sha((native / "startup-opening.png").read_bytes())
        == review["opening"]["sha256"]
    )
    geometry, _ = surface_geometry(
        json.loads(gzip.decompress((fixture / "geometry.json.gz").read_bytes()))
    )
    hydro = json.loads(gzip.decompress((fixture / "hydrology.json.gz").read_bytes()))
    banks = np.frombuffer(
        gzip.decompress((fixture / "banks.f32.gz").read_bytes()), dtype="<f4"
    ).reshape(1081, 1081)
    browser = np.asarray(Image.open(fixture / "input.png"), dtype=float) * 1024 / 65535
    terrain = read_grid(native / "grids/t000-terrain.u16")
    waters = {
        m: read_grid(native / f"grids/t{m:03}-water.u16") for m in [0, 15, 30, 45, 60]
    }
    mask = raster(
        geometry["sq"], [r for r in geometry["rivers"] if r.get("name") == name]
    )
    areas = raster(geometry["sq"], geometry.get("riverAreas", []), True)
    camera = json.loads((native / "startup-world.json").read_text())["camera"]
    assert (
        sha((native / "startup-world.json").read_bytes())
        == json.loads((native / "startup-views.json").read_text())[
            "startup_world_sha256"
        ]
    )
    # Camera-centred bounds diagnose the opening; this is not an acceptance mask.
    cx, _, cz = camera["current_position"]
    roi = np.s_[
        round(540 - cz / 16) - 50 : round(540 - cz / 16) + 50,
        round(540 + cx / 16) - 70 : round(540 + cx / 16) + 90,
    ]
    local = np.zeros_like(mask)
    local[roi] = mask[roi]
    rows, cols = np.nonzero(local)
    assert len(rows), "Named source channel is not in the opening neighborhood"
    report = {
        "scope": "archived accepted baseline only; no candidate native qualification",
        "slug": slug,
        "source_waterway": name,
        "source_class": "river",
        "native_crp_sha256": session["map"]["sha256"],
        "camera": camera,
        "evidence_sha256": {
            str(p.relative_to(native)): sha(p.read_bytes())
            for p in [
                native / "startup-opening.png",
                native / "startup-world.json",
                native / "grids/t000-terrain.u16",
                *[native / f"grids/t{m:03}-water.u16" for m in waters],
            ]
        },
        "opening_source_bounds_world_m": {
            "x": [int((cols.min() - 540) * 16), int((cols.max() - 540) * 16)],
            "z": [int((540 - rows.max()) * 16), int((540 - rows.min()) * 16)],
        },
        "source_polygon_overlap_fraction": float(areas[mask].mean()),
        "polygon_support_catalog": polygon_support_catalog(),
        "profile_summaries": [
            r for r in hydro["rivers"] if r["name"] == name and r["class"] == "river"
        ],
        "sample_points": [],
        "cross_sections": [],
    }
    for world_x in section_x:
        x = round(540 + world_x / 16)
        if not 2 <= x <= 1078:
            raise ValueError("Cross-section must stay inside the native grid")
        source_rows = np.flatnonzero(local[:, x])
        if not len(source_rows):
            raise ValueError(f"No source channel at cross-section x={world_x} m")
        y = int(np.median(source_rows))
        report["sample_points"].append(
            {
                "node_north_first": [x, y],
                "world_xz_m": [(x - 540) * 16, (540 - y) * 16],
                "uncarved_m": float(banks[y, x]),
                "browser_m": float(browser[y, x]),
                "prepared_m": float(terrain[y, x]),
                "exact_native_depth_m": {
                    str(m): float(w[y, x]) for m, w in waters.items()
                },
                "maximum_depth_within_32m_m": {
                    str(m): float(w[y - 2 : y + 3, x - 2 : x + 3].max())
                    for m, w in waters.items()
                },
            }
        )
        ys = np.arange(max(0, y - 12), min(1081, y + 15))
        report["cross_sections"].append(
            {
                "x_m": int((x - 540) * 16),
                "z_m": ((540 - ys) * 16).tolist(),
                "uncarved_m": banks[ys, x].tolist(),
                "browser_m": browser[ys, x].tolist(),
                "prepared_m": terrain[ys, x].tolist(),
                "initial_depth_m": waters[0][ys, x].tolist(),
                "native_60_depth_m": waters[60][ys, x].tolist(),
            }
        )
    fig, axes = plt.subplots(2, 2, figsize=(16, 10), layout="constrained")
    axes[0, 0].imshow(Image.open(native / "startup-opening.png"))
    axes[0, 0].set_title("Accepted PL-926 native opening (unaltered screenshot)")
    axes[0, 0].axis("off")
    dy, dx = np.gradient(terrain, 16)
    shade = np.clip(0.7 + (dx - dy) / 1.5, 0.25, 1)
    image = shade[..., None] * np.array([195, 192, 173])
    image[waters[60] > 0.1] = [50, 125, 205]
    image[local] = [210, 45, 45]
    a = axes[0, 1]
    a.imshow(
        image[roi].astype(np.uint8),
        extent=[
            (roi[1].start - 540) * 16,
            (roi[1].stop - 540) * 16,
            (540 - roi[0].stop) * 16,
            (540 - roi[0].start) * 16,
        ],
    )
    a.set_title(f"Native minute-60 grid; red = source {name}")
    a.set_xlabel("Native world x (m)")
    a.set_ylabel("Native world z (m)")
    for section, a in zip(report["cross_sections"], axes[1]):
        z = np.array(section["z_m"])
        a.plot(
            z,
            section["uncarved_m"],
            label="Uncarved DEM",
            color="black",
            linestyle="--",
        )
        a.plot(z, section["browser_m"], label="Browser excavation", color="#ab6630")
        a.plot(z, section["prepared_m"], label="Prepared bed", color="#555555")
        for m, key, color in [
            (0, "initial_depth_m", "#62a8d5"),
            (60, "native_60_depth_m", "#0065a8"),
        ]:
            depth = np.array(section[key])
            surface = np.array(section["prepared_m"]) + depth
            a.plot(
                z,
                np.where(depth > 0.1, surface, np.nan),
                label=f"Native {m} min surface (>0.1 m depth)",
                color=color,
                linewidth=2,
            )
        a.set_title(
            f"Cross-section x={section['x_m']} m; source line is not the thalweg"
        )
        a.set_xlabel("Native world z (m)")
        a.set_ylabel("Height (game m)")
        a.grid(alpha=0.2)
        a.legend(fontsize=8)
    fig.suptitle(
        "PL-912 Rio opening diagnosis: baseline observations, NOT a new native run",
        fontsize=16,
    )
    output.mkdir(parents=True, exist_ok=True)
    fig.savefig(output / "opening-diagnosis.png", dpi=130)
    plt.close(fig)
    (output / "opening-diagnosis.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k
                in [
                    "native_crp_sha256",
                    "source_polygon_overlap_fraction",
                    "opening_source_bounds_world_m",
                    "sample_points",
                ]
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--waterway", required=True)
    parser.add_argument("--section-x-m", type=int, nargs=2, required=True)
    args = parser.parse_args()
    diagnose(args.slug, args.waterway, args.native, args.output, args.section_x_m)
