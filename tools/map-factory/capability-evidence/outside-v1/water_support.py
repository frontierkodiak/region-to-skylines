"""Deterministic bounds for a deep-water raster path, not native ship limits."""

import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

HERE = Path(__file__).resolve().parent


def edge_pairs(depth, threshold, spacing):
    labels, _ = ndimage.label(depth >= threshold, np.ones((3, 3)))
    margin = int(320 / spacing)
    edges = {
        "south": set(labels[0, margin:-margin]) - {0},
        "north": set(labels[-1, margin:-margin]) - {0},
        "west": set(labels[margin:-margin, 0]) - {0},
        "east": set(labels[margin:-margin, -1]) - {0},
    }
    names = list(edges)
    return [
        [a, b]
        for i, a in enumerate(names)
        for b in names[i + 1 :]
        if edges[a] & edges[b]
    ]


def support(depth, stride):
    values = depth[::stride, ::stride]
    spacing = 16 * stride
    low, high = 0, int(values.max()) + 1
    while high - low > 1:
        middle = (low + high) // 2
        if edge_pairs(values, middle, spacing):
            low = middle
        else:
            high = middle
    return {
        "cell_spacing_m": spacing,
        "deep_6m_edge_pairs": edge_pairs(values, 6 * 64, spacing),
        "maximum_bottleneck_depth_m": low / 64,
        "meaning": "Largest positive depth threshold with an 8-connected raster component touching two distinct edges, each 320m away from corners. Zero means none at any positive encoded depth.",
    }


if __name__ == "__main__":
    rows = []
    for case in json.loads((HERE / "selection.json").read_text())["cases"]:
        water = Path(case["package"]).parent / "water.u16"
        raw = water.read_bytes()
        depth = np.frombuffer(raw, dtype="<u2").reshape(1081, 1081)
        retained = HERE / "raw" / case["slug"] / "prepared-water.u16.gz"
        retained.parent.mkdir(parents=True, exist_ok=True)
        retained.write_bytes(gzip.compress(raw, mtime=0))
        rows.append(
            {
                "slug": case["slug"],
                "artifact_sha256": case["artifact_sha256"],
                "water_path": str(water),
                "water_sha256": hashlib.sha256(raw).hexdigest(),
                "raw_evidence": {
                    "path": str(retained.relative_to(HERE)),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "encoding": "gzip",
                },
                "native_order": "south-first",
                "depth_unit_m": 1 / 64,
                "rasters": [support(depth, stride) for stride in [1, 4]],
            }
        )
    result = {
        "schema": 1,
        "rows": rows,
        "limitations": [
            "6m is the existing exporter choice, not a fitted native minimum.",
            "A raster witness is not continuous curve clearance, a shore/terminal approach, or sustained water support.",
            "No raster witness rules out only this raster/depth/edge-pair criterion, not every possible ship connection or a changed hydrology plan.",
            "Eight-neighbor steps may cut a diagonal corner; this is not a ship-width or turning-radius test.",
        ],
    }
    (HERE / "water-support.json").write_text(json.dumps(result, indent=2) + "\n")
    for row in rows:
        print(
            row["slug"],
            [
                (
                    r["cell_spacing_m"],
                    r["maximum_bottleneck_depth_m"],
                    bool(r["deep_6m_edge_pairs"]),
                )
                for r in row["rasters"]
            ],
        )
