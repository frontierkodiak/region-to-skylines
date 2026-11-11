"""Split county outlines that hold several buildings, before reconstruction.

Downtown the county draws a whole block as one outline. This cuts such an outline into
its buildings along someone else's lines, and writes `selection/parts.json`
(`{building id: [ring, ...]}`, local frame). Outlines that are one building keep one part.

Two line sources:

- `osm` (default): OpenStreetMap building polygons (ODbL). An outline is split when two
  or more OSM buildings each overlap it by 40 m2 or more. OSM is drawn from other imagery
  and sits a metre or two off the county's outlines, so the OSM buildings over an outline
  are first shifted together (up to 3 m) to where they overlap it most. Each point of the
  outline then goes to the OSM building it is nearest to (a Voronoi partition of the OSM
  boundaries), so the county outline keeps its own outer edge and only the dividing lines
  come from OSM.
- `parcels`: Buncombe County parcel polygons. The outline is cut along parcel lines;
  stacked condominium parcels are counted once.

Pieces under 30 m2 join the neighbour they share the longest edge with.

    uv run split_outlines.py [--source osm|parcels]
"""

from __future__ import annotations

import argparse
import time

import numpy as np
import requests
import shapely
from pyproj import Transformer
from shapely import STRtree
from shapely.geometry import MultiPoint, Polygon, shape
from shapely.ops import unary_union

from common import EXP, FTUS, WORK_EPSG, read_json, to_local, write_json

OVERPASS = ("https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter")
PARCELS = "https://gis.ashevillenc.gov/server/rest/services/Property/BuncombeCountyProperty/FeatureServer/31"
MIN_OVERLAP = 40.0  # m2 of an OSM building or parcel over the outline for it to count
MIN_PART = 30.0  # m2; smaller pieces join a neighbour
MAX_SHIFT = 3.0  # m, OSM-to-county alignment search


def fetch_osm(aoi, path):
    """OSM building polygons in a lon/lat box, cached; local-frame polygons."""
    if not path.exists():
        lon0, lat0, lon1, lat1 = aoi
        box = f"({lat0 - 0.001},{lon0 - 0.001},{lat1 + 0.001},{lon1 + 0.001})"
        q = f'[out:json][timeout:90];(way["building"]{box};relation["building"]{box};);out geom;'
        for attempt in range(6):  # the public Overpass servers drop requests under load
            r = requests.post(OVERPASS[attempt % len(OVERPASS)], data={"data": q},
                              headers={"User-Agent": "region-to-skylines lod2-pilot"}, timeout=180)
            if r.ok and r.text.lstrip().startswith("{"):
                break
            time.sleep(10 * (attempt + 1))
        else:
            r.raise_for_status()
            raise RuntimeError("Overpass returned no JSON")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(r.text)
    tr = Transformer.from_crs(4326, WORK_EPSG, always_xy=True)

    def poly(geometry):
        e, n = tr.transform([p["lon"] for p in geometry], [p["lat"] for p in geometry])
        return Polygon([to_local(x, y) for x, y in zip(e, n)]).buffer(0)

    out = []
    for el in read_json(path)["elements"]:
        if el["type"] == "way" and len(el.get("geometry", [])) >= 4:
            out.append(poly(el["geometry"]))
        elif el["type"] == "relation":
            out += [poly(m["geometry"]) for m in el.get("members", []) if m.get("role") == "outer" and len(m.get("geometry", [])) >= 4]
    return [p for p in out if p.geom_type == "Polygon" and p.area > 5]


def fetch_parcels(aoi, path):
    """County parcel polygons in a lon/lat box, cached without owner fields; local frame."""
    if not path.exists():
        lon0, lat0, lon1, lat1 = aoi
        r = requests.get(PARCELS + "/query", params={
            "where": "1=1", "geometry": f"{lon0},{lat0},{lon1},{lat1}", "geometryType": "esriGeometryEnvelope", "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects", "outFields": "pinnum", "outSR": 2264, "f": "geojson"}, timeout=180)
        r.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(r.text)
    out, seen = [], set()
    for f in read_json(path)["features"]:
        g = shape(f["geometry"])
        for q in g.geoms if g.geom_type == "MultiPolygon" else [g]:
            p = Polygon([to_local(x * FTUS, y * FTUS) for x, y in q.exterior.coords]).buffer(0)
            key = (round(p.centroid.x), round(p.centroid.y), round(p.area))
            if p.geom_type == "Polygon" and key not in seen:  # condominium units repeat one parcel
                seen.add(key)
                out.append(p)
    return out


def polygons(g):
    if g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g]
    return [p for p in getattr(g, "geoms", []) if p.geom_type == "Polygon"]


def align(outline, hits):
    """Shift that puts a group of OSM buildings best over the outline (grid search, 0.5 m)."""
    u = unary_union(hits)
    best, shift = -1.0, (0.0, 0.0)
    steps = np.arange(-MAX_SHIFT, MAX_SHIFT + 0.01, 0.5)
    for dx in steps:
        for dz in steps:
            m = shapely.affinity.translate(u, dx, dz)
            # overlap, minus what sticks out: both pull the group onto the outline
            s = m.intersection(outline).area - m.difference(outline).area - 0.01 * (abs(dx) + abs(dz))
            if s > best:
                best, shift = s, (float(dx), float(dz))
    return shift


def nearest_partition(outline, owners):
    """Cut the outline so each point goes to the nearest owner polygon."""
    pts, own = [], []
    for k, q in enumerate(owners):
        core = q.buffer(-0.3)
        for ring in polygons(core if not core.is_empty else q):
            xy = np.array(ring.exterior.segmentize(1.0).coords)[:-1]
            pts.append(xy)
            own += [k] * len(xy)
    pts, own = np.round(np.vstack(pts), 2), np.array(own)
    _, first = np.unique(pts, axis=0, return_index=True)  # coincident points make degenerate cells
    pts, own = pts[first], own[first]
    cells = shapely.voronoi_polygons(MultiPoint(pts), extend_to=outline.buffer(10))
    cells = [c for c in shapely.set_precision(np.array(list(cells.geoms)), 0.001) if not c.is_empty and c.area > 0]
    tree = STRtree(shapely.points(pts))
    groups: dict[int, list] = {}
    for c in cells:
        inside = tree.query(c, predicate="intersects")
        if len(inside):
            groups.setdefault(int(own[inside[0]]), []).append(c)
    # snapped to a millimetre grid: Voronoi cells of near-coincident points do not node exactly
    return [shapely.intersection(shapely.union_all(g, grid_size=0.001), outline, grid_size=0.001) for _, g in sorted(groups.items())]


def tidy(pieces):
    """Single polygons only; pieces under MIN_PART join the neighbour with the longest shared edge."""
    parts = [p for g in pieces for p in polygons(g) if p.area > 0.5]
    while True:
        parts.sort(key=lambda p: p.area)
        if len(parts) < 2 or parts[0].area >= MIN_PART:
            break
        small = parts.pop(0)
        shared = [small.buffer(0.05).intersection(p).area for p in parts]
        k = int(np.argmax(shared))
        if shared[k] <= 0:
            continue  # touches nothing: drop it
        merged = unary_union([parts[k], small.buffer(0.02)]).buffer(-0.01)
        parts[k] = max(polygons(merged), key=lambda p: p.area) if polygons(merged) else parts[k]
    # The nearest-owner line zigzags between sampled points; straighten the dividing lines
    # together so neighbours still share them, and leave the county's outer edge alone.
    try:
        parts = [p for g in shapely.coverage_simplify(parts, 1.0, simplify_boundary=False) for p in polygons(g)]
    except shapely.errors.GEOSException:
        pass
    return parts


def split(outline, lines, source):
    hits = [q for q in lines if q.intersects(outline) and q.intersection(outline).area >= MIN_OVERLAP]
    if len(hits) < 2:
        return [outline], None
    if source == "osm":
        dx, dz = align(outline, hits)
        hits = [shapely.affinity.translate(q, dx, dz) for q in hits]
        return tidy(nearest_partition(outline, hits)), (dx, dz)
    # parcels: their own lines, and whatever lies outside every parcel goes to the nearest
    return tidy(nearest_partition(outline, hits)), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="osm", choices=["osm", "parcels"])
    ap.add_argument("--out", default="parts.json")
    args = ap.parse_args()
    sel = read_json(EXP / "selection" / "buildings.json")
    lines = {}
    for hood, aoi in sel["aois"].items():
        cache = EXP / "split" / f"{args.source}-{hood}.json"
        lines[hood] = (fetch_osm if args.source == "osm" else fetch_parcels)(aoi, cache)
    out, n_split = {}, 0
    for b in sel["buildings"]:
        outline = Polygon(b["ring"]).buffer(0)
        if outline.geom_type != "Polygon":
            outline = max(polygons(outline), key=lambda p: p.area)
        parts, shift = split(outline, lines[b["hood"]], args.source)
        out[str(b["id"])] = [[[round(x, 3), round(z, 3)] for x, z in p.exterior.coords] for p in parts]
        if len(parts) > 1:
            n_split += 1
            print(b["id"], b["hood"], b["set"], f"{outline.area:.0f} m2 ->", len(parts), "parts", sorted((round(p.area) for p in parts), reverse=True),
                  "shift", shift, "covered", round(sum(p.area for p in parts) / outline.area, 3))
    write_json(EXP / "selection" / args.out, {"source": args.source, "min_overlap_m2": MIN_OVERLAP, "min_part_m2": MIN_PART, "parts": out})
    print(n_split, "of", len(sel["buildings"]), "outlines split")


if __name__ == "__main__":
    main()
