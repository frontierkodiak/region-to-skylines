"""Run the frozen method, untouched, on a small sample in another city.

Boston (Dorchester, a triple-decker district of about the same age as Montford): MassGIS
roofprints and the 2021 USGS QL1 lidar (linear-mode, multi-return, unlike Asheville's
2017 Geiger-mode cloud). Twelve outlines of 60 m2 or more are drawn at random with a fixed
seed, nothing is tuned, and the same scripts then crop, reconstruct, check and render them:

    uv run second_city.py                     # writes ~/experiments/PL-900-lod2-pilot/boston
    export LOD2_EXP=~/experiments/PL-900-lod2-pilot/boston LOD2_FRAME=$(cat $LOD2_EXP/frame.txt)
    uv run crop_points.py && uv run reconstruct.py --set all && uv run evaluate.py --set all
"""

from __future__ import annotations

import json
import random
import subprocess
from pathlib import Path

import requests
from pyproj import Transformer
from shapely.geometry import Polygon, shape

from common import EXP

STRUCTURES = "https://services1.arcgis.com/hGdibHYSPO59RG1h/arcgis/rest/services/Building_Structures/FeatureServer/0"
EPT = "https://usgs-lidar-public.s3.amazonaws.com/MA_CentralEastern_1_2021/ept.json"
AOI = (-71.0700, 42.2990, -71.0640, 42.3030)  # Dorchester, around Melville Avenue
EPSG = 26986  # NAD83 / Massachusetts Mainland, metres
SEED, N = 900, 12


def main():
    out = EXP / "boston"
    (out / "selection").mkdir(parents=True, exist_ok=True)
    (out / "data").mkdir(exist_ok=True)
    r = requests.get(STRUCTURES + "/query", params={
        "where": "1=1", "geometry": ",".join(map(str, AOI)), "geometryType": "esriGeometryEnvelope", "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects", "outFields": "OBJECTID", "outSR": EPSG, "f": "geojson"}, timeout=120)
    r.raise_for_status()
    t = Transformer.from_crs(4326, EPSG, always_xy=True)
    e0, n0 = t.transform((AOI[0] + AOI[2]) / 2, (AOI[1] + AOI[3]) / 2)
    x0, y0 = t.transform(AOI[0], AOI[1])
    x1, y1 = t.transform(AOI[2], AOI[3])
    cands = []
    for f in r.json()["features"]:
        g = shape(f["geometry"])
        if g.geom_type == "MultiPolygon":
            g = max(g.geoms, key=lambda p: p.area)
        c = g.centroid
        if g.area < 60 or not (x0 + 30 < c.x < x1 - 30 and y0 + 30 < c.y < y1 - 30):
            continue
        ring = [[round(x - e0, 3), round(-(y - n0), 3)] for x, y in g.exterior.coords]
        cands.append({"id": f["properties"]["OBJECTID"], "hood": "boston", "set": "locked", "flags": [], "area": round(g.area, 1),
                      "in_2025_tile": False, "ring": ring})
    cands.sort(key=lambda c: c["id"])
    picked = sorted(random.Random(SEED).sample(cands, N), key=lambda c: c["id"])
    (out / "selection" / "buildings.json").write_text(json.dumps({"seed": SEED, "aoi": AOI, "candidates": len(cands), "buildings": picked}, indent=1))
    (out / "frame.txt").write_text(f"{e0},{n0},{EPSG},2021")
    (out / "clouds.json").write_text(json.dumps({"2021": {"boston": "boston.laz"}}))
    m = Transformer.from_crs(EPSG, 3857, always_xy=True)
    a, b = m.transform(x0 - 40, y0 - 40), m.transform(x1 + 40, y1 + 40)
    pipe = [{"type": "readers.ept", "filename": EPT, "bounds": f"([{a[0]},{b[0]}],[{a[1]},{b[1]}])", "threads": 16},
            {"type": "filters.reprojection", "in_srs": "EPSG:3857", "out_srs": f"EPSG:{EPSG}"},
            {"type": "writers.las", "filename": str(out / "data" / "boston.laz"), "a_srs": f"EPSG:{EPSG}", "minor_version": 4, "dataformat_id": 6,
             "scale_x": 0.01, "scale_y": 0.01, "scale_z": 0.01, "offset_x": "auto", "offset_y": "auto", "offset_z": "auto"}]
    (out / "data" / "ept.json").write_text(json.dumps(pipe, indent=1))
    subprocess.run([str(EXP / "tools" / "pdal"), "pipeline", str(out / "data" / "ept.json")], check=True, cwd=out / "data")
    print(len(cands), "candidates;", N, "picked:", [c["id"] for c in picked])


if __name__ == "__main__":
    main()
