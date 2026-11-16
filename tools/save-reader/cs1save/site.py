"""Build a timeline page for one or more cities from their saves.

Saves are grouped by the city's game-instance id and ordered by the time they
were saved. Each save gets a top-down map; each consecutive pair gets a map of
what changed. The page itself (page/index.html, page/app.js) reads data.json.
"""

import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from . import city as citymod
from . import render, timeline
from .save import read_save

NEEDED = {
    "GameAreaManager",
    "TerrainManager",
    "WaterSimulation",
    "InstanceManager",
    "NetManager",
    "BuildingManager",
    "ZoneManager",
    "TreeManager",
    "EconomyManager",
    "DistrictManager",
    "TransportManager",
}
PAGE = Path(__file__).parent / "page"


def load(paths, sessions=()):
    """Group saves by city; each (label, paths) session becomes its own series."""
    series = defaultdict(list)
    seen = set()
    tagged = [(None, p) for p in paths] + [(label, p) for label, ps in sessions for p in ps]
    for label, path in tagged:
        save = read_save(path, only=NEEDED)
        group = label or save.simulation_meta["game_instance"]
        key = (group, save.simulation_meta["game_instance"], save.simulation["frame_index"])
        if key in seen:
            continue  # the same moment saved twice
        seen.add(key)
        save.label = label
        series[group].append(save)
    for saves in series.values():
        saves.sort(key=lambda s: s.metadata.get("timeStamp") or "")
    return series


def headline(save):
    out = {}
    d = save.data.get("DistrictManager")
    if d:
        c = d.get("city", {})
        for key in (
            "households",
            "jobs",
            "unemployed",
            "eligible_workers",
            "tourists",
            "happiness",
            "crime_rate",
            "land_value",
            "building_counts",
            "electricity",
            "water",
        ):
            if key in c:
                out[key] = c[key]
        out["districts"] = max(0, len(d.get("districts", [])) - 1)
        out["parks"] = sum(1 for p in d.get("parks", []) if p.get("index", 0) > 0)
        policies = Counter()
        for dist in d.get("districts", []):
            for category, names in (dist.get("policies") or {}).items():
                if not category.endswith("_effect") and isinstance(names, list):
                    policies.update(names)
        out["policies_in_force"] = sorted(policies)
    e = save.data.get("EconomyManager")
    if e:
        out["unlimited_money"] = e.get("last_cash_amount") == 2**63 - 1
        out["tax_rates"] = e.get("tax_rates")
    t = save.data.get("TransportManager")
    if t:
        out["transit_lines"] = dict(Counter(ln["prefab"] for ln in t.get("lines", [])))
    return out


def build(paths, out, width=2000, min_saves=2, only_city=None, notes=None, sessions=()):
    out = Path(out)
    (out / "img").mkdir(parents=True, exist_ok=True)
    data = {"series": []}
    used_slugs = set()
    for gid, saves in load(paths, sessions).items():
        name = saves[-1].label or saves[-1].metadata.get("cityName") or gid[:8]
        if len(saves) < min_saves or (only_city and name not in only_city):
            continue
        slug = base = "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")
        n = 2
        while slug in used_slugs:  # two cities, or a session, with the same name
            slug, n = f"{base}-{n}", n + 1
        used_slugs.add(slug)
        cities = [citymod.extract(s) for s in saves]
        bounds = timeline.bounds_of(cities)
        frame = render.Frame(bounds, width)
        core = timeline.core_bounds(cities[-1], aspect=0.8)
        core_frame = render.Frame(core, int(width * 0.75)) if core else None
        raw_first = saves[0].data["TerrainManager"]["raw_heights"]
        slope_first = timeline.slope_grid(raw_first)
        wdist_first = timeline.water_distance_grid(saves[0].data["WaterSimulation"]["depth"])
        entries = []
        for i, (save, c) in enumerate(zip(saves, cities)):
            raw = save.data["TerrainManager"]["raw_heights"]
            depth = save.data["WaterSimulation"]["depth"]
            image = f"img/{slug}-{i:02d}.webp"
            render.render(c, raw, depth, frame, out / image)
            core_image = None
            if core_frame:
                core_image = f"img/{slug}-{i:02d}-core.webp"
                render.render(c, raw, depth, core_frame, out / core_image)
            entry = {
                "index": i,
                "file": Path(save.path).name,
                "image": image,
                "core_image": core_image,
                **timeline.summary(c),
                **headline(save),
                "unlocked_tiles": save.data["GameAreaManager"]["area_count"],
                "grid": timeline.orientation_share([s for s in c["segments"] if not s["original"]]),
                "curved_share": timeline.curved_share([s for s in c["segments"] if not s["original"]]),
            }
            if i > 0:
                change = timeline.diff(cities[i - 1], c)
                # judge placements on the land as it was before this change
                before = saves[i - 1]
                prev_raw = before.data["TerrainManager"]["raw_heights"]
                slope = timeline.slope_grid(prev_raw)
                wdist = timeline.water_distance_grid(before.data["WaterSimulation"]["depth"])
                diff_image = f"img/{slug}-{i:02d}-diff.webp"
                render.render(c, raw, depth, frame, out / diff_image, previous=cities[i - 1], diff=change)
                entry["diff_image"] = diff_image
                if core_frame:
                    entry["core_diff_image"] = f"img/{slug}-{i:02d}-core-diff.webp"
                    render.render(
                        c, raw, depth, core_frame, out / entry["core_diff_image"], previous=cities[i - 1], diff=change
                    )
                entry["change"] = describe_change(change, slope, wdist, prev_raw)
            entries.append(entry)
        first_player = [s for s in cities[0]["segments"] if not s["original"]]
        data["series"].append(
            {
                "name": name,
                "slug": slug,
                "map": cities[-1]["map"],
                "environment": cities[-1]["environment"],
                "bounds": [round(v, 1) for v in bounds],
                "core_bounds": [round(v, 1) for v in core] if core else None,
                "metres_per_pixel": round(frame.mpp, 3),
                "width": frame.width,
                "height": frame.height,
                "saves": entries,
                "first_build": timeline.placement_stats(
                    timeline.segment_midpoints(first_player), slope_first, wdist_first, raw_first
                ),
                "available_land": available_land(slope_first, wdist_first, raw_first, bounds),
            }
        )
    data["series"].sort(key=lambda s: s["saves"][-1]["saved_at"] or "", reverse=True)
    if notes:
        data.update(json.loads(Path(notes).read_text()))
    (out / "data.json").write_text(json.dumps(data, indent=1, default=_json))
    for f in PAGE.iterdir():
        shutil.copy(f, out / f.name)
    return data


def describe_change(change, slope, wdist, raw):
    seg_km = Counter()
    elev_km = Counter()
    for s in change["segments_added"]:
        name = s["category"] if s["category"] != "road" else f"road ({s['level']})"
        seg_km[name] += s["length"] / 1000
        if s["category"] in ("road", "highway", "rail", "path"):
            elev_km[s["elevation"]] += s["length"] / 1000
    removed_km = sum(s["length"] for s in change["segments_removed"]) / 1000
    zones = Counter(code for _, _, code in change["zones_added"])
    services = Counter(b["service"] for b in change["buildings_added"])
    roads = [s for s in change["segments_added"] if s["category"] == "road"]
    return {
        "road_km_added": {k: round(v, 3) for k, v in seg_km.items()},
        "elevation_km_added": {k: round(v, 3) for k, v in elev_km.items()},
        "road_km_removed": round(removed_km, 3),
        "upgrades": len(change["segments_upgraded"]),
        "zone_cells_added": {str(k): v for k, v in zones.items()},
        "zone_cells_removed": change["zones_removed"],
        "buildings_added": dict(services),
        "buildings_removed": len(change["buildings_removed"]),
        "buildings_replaced": len(change["buildings_replaced"]),
        "new_roads_where": timeline.placement_stats(timeline.segment_midpoints(roads), slope, wdist, raw),
        "new_zones_where": timeline.placement_stats([(x, z) for x, z, _ in change["zones_added"]], slope, wdist, raw),
        "new_roads_grid": timeline.orientation_share(roads),
        "new_roads_curved": timeline.curved_share(roads),
    }


def available_land(slope, wdist, raw, bounds, step=4):
    """The same placement measures over all dry land in the view, for comparison."""
    x0, z0, x1, z1 = bounds
    xs = np.arange(x0, x1, 16 * step)
    zs = np.arange(z0, z1, 16 * step)
    gx, gz = np.meshgrid(xs, zs)
    pts = np.stack([gx.ravel(), gz.ravel()], axis=1)
    dry = timeline.at_grid(wdist, pts[:, 0], pts[:, 1]) > 0
    return timeline.placement_stats(pts[dry], slope, wdist, raw)


def _json(value):
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(type(value))
