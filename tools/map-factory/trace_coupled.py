"""Rerun the held-input bed/stage causal trace; no native launch or policy change."""

import argparse
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
from PIL import Image
import region


def trace(source, output):
    g = json.loads((source / "geometry.json").read_text())
    banks = (
        np.fromfile(source / "banks.f32", dtype="<f4").reshape(1081, 1081).astype(float)
    )
    browser = (
        np.asarray(
            Image.open(Path(__file__).parent / "fixtures/rio/input.png"), dtype=float
        )
        * 1024
        / 65535
    )
    ground = browser.copy()
    records = []
    deferred = []
    row, col = 313, 465
    line = next(
        n
        for n, s in enumerate(Path(region.__file__).read_text().splitlines(), 1)
        if s.strip().startswith("channel_depth =")
    )

    def observe(frame, event, arg):
        if (
            frame.f_code.co_name == "hydrology"
            and event == "line"
            and frame.f_lineno == line
        ):
            v = frame.f_locals
            status = region.portal_gravity_status(
                v["path"],
                banks,
                v["geometry"],
                v["grouped"][(v["name"], v["kind"])],
                v["channel"],
            )
            if status["defer_browser_cut"]:
                deferred.extend(status["source_features"])
            dist = np.hypot(v["x"] - col, v["y"] - row)
            i = int(dist.argmin())
            if dist[i] <= 4:
                records.append(
                    {
                        "name": v["name"],
                        "kind": v["kind"],
                        "component": v["component"],
                        "arc_m": v["arc"].tolist(),
                        "path_yx": v["path"].tolist(),
                        "uncarved_m": banks[v["y"], v["x"]].tolist(),
                        "browser_m": browser[v["y"], v["x"]].tolist(),
                        "wanted_stage_m": v["wanted"].tolist(),
                        "fitted_stage_m": v["fitted"].tolist(),
                        "bank_ceiling_m": v["ceiling"].tolist(),
                        "overbank_m": v["overbank"],
                        "short_river": v["short_river"],
                        "bank_limited": v["bank_limited"],
                        "nearest_index": i,
                        "portal_gravity": {
                            k: v for k, v in status.items() if k != "source_features"
                        },
                        "portal_distance_m": [
                            float(v["tunnel_distance"][tuple(p)])
                            for p in [v["path"][0], v["path"][-1]]
                        ],
                    }
                )
        return observe

    sys.settrace(observe)
    try:
        depth, report = region.hydrology(ground, banks, g)
    finally:
        sys.settrace(None)
    hydro = json.loads((source / "hydrology.json").read_text())
    controls = [
        s
        for s in hydro["sources"]
        if (s["position"][0] + 1200) ** 2 + (s["position"][2] - 3632) ** 2 < 500**2
    ]
    result = {
        "input_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                source / "banks.f32",
                source / "geometry.json",
                Path(__file__).parent / "fixtures/rio/input.png",
            ]
        },
        "control_world_xz": [-1200, 3632],
        "control_node": {
            "uncarved_m": banks[row, col],
            "browser_m": browser[row, col],
            "after_hydrology_m": ground[row, col],
            "initial_depth_m": depth[row, col],
        },
        "profiles": records,
        "deferred_source_features": list(
            {json.dumps(f, sort_keys=True): f for f in deferred}.values()
        ),
        "nearby_controls": controls,
        "visibility": report["surface_water_classification"],
        "native_interpolation": "four m_blockHeights vertices; 8-bit fixed-point bilinear, verified by native_water_ground",
    }
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "control_node": result["control_node"],
                "profiles": [
                    {
                        k: r[k]
                        for k in [
                            "name",
                            "component",
                            "short_river",
                            "bank_limited",
                            "overbank_m",
                            "portal_distance_m",
                        ]
                    }
                    for r in records
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    trace(a.source, a.output)
