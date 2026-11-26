"""Localize every retained flooding/loss component; never change old scores."""

from pathlib import Path
import json
import sys

import numpy as np
from scipy import ndimage as ndi
from PIL import Image, ImageDraw, ImageFont

from stock_water import raster

ROOT = Path(sys.argv[1])
OUT = Path(sys.argv[2])
NATIVE = Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / "trial-d-native"
PREPARED = Path(sys.argv[4]) if len(sys.argv) > 4 else ROOT / "trial-d-prepared"
LABEL = sys.argv[5] if len(sys.argv) > 5 else "rejected PR107"
OUT.mkdir(exist_ok=True)


def run(slug):
    folder = NATIVE / (slug + "-attempt-1")
    prep = PREPARED / slug
    hydro = json.loads((prep / "hydrology.json").read_text())
    geo = json.loads((prep / "geometry.json").read_text())

    def grid(p):
        return np.fromfile(p, dtype="<u2").reshape(1081, 1081).astype("i4")

    terrain = grid(prep / "terrain.u16") / 64
    original = np.flipud(
        np.fromfile(
            ROOT.parent / "gameplay-water/inputs" / slug / "banks.f32", dtype="<f4"
        ).reshape(1081, 1081)
    )
    initial = grid(prep / "water.u16")
    wet = initial >= 7
    mapped = np.fromfile(folder / "mapped-water.u8", dtype="u1").reshape(1081, 1081) > 0
    near = ndi.distance_transform_edt(~(wet | mapped)) <= 8
    paths = sorted((folder / "grids").glob("t*-water.u16"))
    assert len(paths) == 13
    water = np.stack([grid(p) for p in paths])
    flood = (water > 32) & ~near
    labels, n = ndi.label(wet, np.ones((3, 3)))
    source_mask = np.zeros(wet.shape, dtype=bool)
    source_labels = []
    for source in hydro["sources"]:
        x, _, z = source["position"]
        row, col = round((z + 8640) / 16), round((x + 8640) / 16)
        source_mask[row, col] = True
        source_labels.append(int(labels[row, col]))
    source_distance = ndi.distance_transform_edt(~source_mask) * 16
    lakes = np.flipud(raster(geo["sq"], geo.get("lakes", []), True))
    river_areas = np.flipud(raster(geo["sq"], geo.get("riverAreas", []), True))
    lines = np.flipud(raster(geo["sq"], geo.get("rivers", []) + geo.get("streams", [])))
    line_distance = ndi.distance_transform_edt(~lines) * 16
    tunnel_features = [
        f
        for field in ["rivers", "streams"]
        for f in geo.get(field, [])
        if f.get("brunnel") == "tunnel"
    ]
    tunnels = np.flipud(raster(geo["sq"], tunnel_features))
    tunnel_distance = (
        ndi.distance_transform_edt(~tunnels) * 16
        if tunnels.any()
        else np.full(wet.shape, np.inf)
    )
    lake_distance = (
        ndi.distance_transform_edt(~lakes) * 16
        if lakes.any()
        else np.full(wet.shape, np.inf)
    )
    river_area_distance = (
        ndi.distance_transform_edt(~river_areas) * 16
        if river_areas.any()
        else np.full(wet.shape, np.inf)
    )
    rows, cols = np.indices(wet.shape)
    edge_distance = np.minimum.reduce([rows, cols, 1080 - rows, 1080 - cols]) * 16
    counts = np.bincount(labels.ravel())
    retained = []
    loss = np.zeros(wet.shape, dtype=bool)
    worst = np.ones(n + 1)
    worst_time = np.zeros(n + 1, dtype=int)
    lost_masks = []
    for t, depth in enumerate(water):
        nearby = ndi.distance_transform_edt(~(depth >= 7)) <= 4
        kept = np.bincount(labels[wet & nearby], minlength=n + 1)
        fraction = np.divide(kept, counts, out=np.ones(n + 1), where=counts > 0)
        lower = fraction < worst
        worst[lower] = fraction[lower]
        worst_time[lower] = t
        lost_masks.append(wet & ~nearby)
    for identity in range(1, n + 1):
        body = labels == identity
        if counts[identity] < 54 or worst[identity] >= 0.95:
            continue
        lost = body & lost_masks[worst_time[identity]]
        ever_lost = body & np.any(lost_masks, axis=0)
        loss |= ever_lost
        rr, cc = np.nonzero(body)
        retained.append(
            {
                "id": identity,
                "initial_nodes": int(counts[identity]),
                "minimum_retained": float(worst[identity]),
                "worst_time": paths[worst_time[identity]].name,
                "lost_nodes": int(lost.sum()),
                "ever_lost_nodes": int(ever_lost.sum()),
                "sources_in_body": source_labels.count(identity),
                "edge": bool((edge_distance[body] == 0).any()),
                "lake_nodes": int((body & lakes).sum()),
                "river_area_nodes": int((body & river_areas).sum()),
                "line_nodes": int((body & lines).sum()),
                "context": (
                    "river-area/channel"
                    if (body & river_areas).any()
                    else "lake/stream interface"
                    if (body & lakes).any() and (body & lines).any()
                    else "pond/lake"
                    if (body & lakes).any()
                    else "river/stream reach"
                ),
                "center_xz": [
                    float(cc.mean() * 16 - 8640),
                    float(rr.mean() * 16 - 8640),
                ],
            }
        )
    union = flood.any(axis=0)
    fl, nf = ndi.label(union, np.ones((3, 3)))
    components = []
    for identity in range(1, nf + 1):
        body = fl == identity
        rr, cc = np.nonzero(body)
        curve = [int((f & body).sum()) for f in flood]
        components.append(
            {
                "id": identity,
                "union_nodes": int(body.sum()),
                "peak_nodes": max(curve),
                "nodes_by_time": curve,
                "first_time": paths[next(i for i, v in enumerate(curve) if v)].name,
                "bbox_xz": [
                    int(cc.min() * 16 - 8640),
                    int(rr.min() * 16 - 8640),
                    int(cc.max() * 16 - 8640),
                    int(rr.max() * 16 - 8640),
                ],
                "center_xz": [
                    float(cc.mean() * 16 - 8640),
                    float(rr.mean() * 16 - 8640),
                ],
                "minimum_source_distance_m": float(source_distance[body].min()),
                "minimum_edge_distance_m": int(edge_distance[body].min()),
                "minimum_line_distance_m": float(line_distance[body].min()),
                "minimum_lake_distance_m": float(lake_distance[body].min()),
                "minimum_river_area_distance_m": float(river_area_distance[body].min()),
                "minimum_tunnel_distance_m": float(tunnel_distance[body].min()),
                "raised_terrain_nodes_gt2cm": int(
                    ((terrain - original > 0.02) & body).sum()
                ),
                "terrain_m_range": [
                    float(terrain[body].min()),
                    float(terrain[body].max()),
                ],
                "terrain_cut_max_m": float(
                    np.maximum(original - terrain, 0)[body].max()
                ),
                "terrain_raise_max_m": float(
                    np.maximum(terrain - original, 0)[body].max()
                ),
            }
        )
        component = components[-1]
        nearest = min(
            [
                (component["minimum_lake_distance_m"], "pond/lake"),
                (component["minimum_river_area_distance_m"], "broad river"),
                (component["minimum_line_distance_m"], "river/stream"),
            ],
            key=lambda item: item[0],
        )
        component["context"] = (
            (
                "road-graded ground"
                if component["raised_terrain_nodes_gt2cm"]
                else "unraised ground"
            )
            + f"; nearest mapped {nearest[1]} at {nearest[0]:.0f}m"
            + (
                "; captured tunnel/culvert nearby"
                if component["minimum_tunnel_distance_m"] <= 128
                else ""
            )
            + (
                "; map-edge reach"
                if component["minimum_edge_distance_m"] <= 128
                else "; inland"
            )
        )
    components.sort(key=lambda r: -r["union_nodes"])
    retained.sort(key=lambda r: -r["lost_nodes"])
    result = {
        "square": slug,
        "scope": "All 13 retained grids. Red flood is >0.5m outside the unchanged 128m initial/mapped margin; red stipple is lost support from every >=54-node authored body failing 95% nearby retention. Raster components are not hydraulic bodies.",
        "flood_km2_by_time": [round(int(f.sum()) * 0.000256, 4) for f in flood],
        "flood_components": components,
        "losing_bodies": retained,
        "sea_level_m": hydro["sea_level_m"],
        "all_flood_nodes_within128m_of_source": int(
            (union & (source_distance <= 128)).sum()
        ),
        "all_flood_nodes_within128m_of_edge": int(
            (union & (edge_distance <= 128)).sum()
        ),
        "flood_union_nodes": int(union.sum()),
        "lost_body_nodes": int(loss.sum()),
    }
    (OUT / (slug + "-localization.json")).write_text(
        json.dumps(result, indent=2) + "\n"
    )
    # The figure is generated from the measured grids, not an edited game image.
    lo, hi = np.percentile(original, [1, 99])
    shade = np.clip((original - lo) / (hi - lo), 0, 1)
    shade = 0.34 + 0.43 * shade
    rgb = np.stack([shade * 0.93, shade, shade * 0.86], axis=-1)
    rgb[wet] = [0.20, 0.39, 0.54]
    rgb[loss] = [0.88, 0.24, 0.24]
    rgb[union] = [1, 0.05, 0.08]
    # North at top; coordinates above remain native south-first.
    im = Image.fromarray((np.flipud(rgb) * 255).astype("u1")).resize((1081, 1081))
    canvas = Image.new("RGB", (1500, 1250), "#f7f5ee")
    canvas.paste(im, (20, 100))
    draw = ImageDraw.Draw(canvas)

    def font(s):
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", s)

    draw.text(
        (20, 15),
        slug.title() + " — " + LABEL + ": all 13 captures",
        font=font(32),
        fill="#172016",
    )
    draw.text(
        (20, 57),
        "Bright red: flooding. Dark red: lost authored water. Blue: initial water. North ↑",
        font=font(22),
        fill="#333333",
    )
    names = {
        "asheville": [
            "Gashes Creek / tunnel end",
            "French Broad low bank",
            "Swannanoa low bank",
        ],
        "pittsburgh": [
            "Allegheny low bank",
            "Allegheny low bank",
            "Monongahela / road bank",
        ],
    }
    for k, component in enumerate(components[:8], 1):
        x, z = component["center_xz"]
        cx = 20 + round((x + 8640) / 16)
        cy = 100 + 1080 - round((z + 8640) / 16)
        draw.ellipse(
            (cx - 13, cy - 13, cx + 13, cy + 13), fill="white", outline="black", width=2
        )
        draw.text((cx - 6, cy - 10), str(k), font=font(17), fill="black")
        y = 108 + (k - 1) * 102
        draw.text(
            (1120, y),
            f"{k}: {component['union_nodes']} flood cells",
            font=font(21),
            fill="#172016",
        )
        draw.text(
            (1120, y + 29),
            names[slug][k - 1]
            if k <= 3
            else (
                "Road-graded ground"
                if component["raised_terrain_nodes_gt2cm"]
                else "Unraised ground"
            ),
            font=font(19),
            fill="#333333",
        )
        draw.text(
            (1120, y + 55),
            f"Edge ≥{component['minimum_edge_distance_m']} m",
            font=font(19),
            fill="#333333",
        )
    draw.text(
        (20, 1195),
        f"Peak flood {max(result['flood_km2_by_time']):.4f} km² · {len(retained)} losing authored bodies · no new game run",
        font=font(24),
        fill="#172016",
    )
    canvas.save(OUT / (slug + "-overlay.png"))
    np.savez_compressed(
        OUT / (slug + "-masks.npz"),
        flood=flood,
        loss=loss,
        flood_labels=fl,
        initial_labels=labels,
    )
    print(
        slug,
        "flood components",
        nf,
        "union",
        int(union.sum()),
        "source128",
        result["all_flood_nodes_within128m_of_source"],
        "edge128",
        result["all_flood_nodes_within128m_of_edge"],
    )
    print("TOP FLOOD", json.dumps(components[:4]))
    print("TOP LOSS", json.dumps(retained[:5]))


for slug in ["asheville", "pittsburgh"]:
    run(slug)
