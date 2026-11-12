"""Real-world ore and oil evidence for a region, in game metres.

Three keyless US sources; other countries get none and rely on "balanced".

- USGS Mineral Resources Data System (MRDS, public domain): producers and
  past producers count, prospects a little, bare occurrences not at all.
  Processing plants (steel works, coke ovens, cement and brick plants) are
  skipped: they mark industry, not a deposit.
- MSHA Mines (public domain): every coal and metal/non-metal mine under MSHA
  since 1970 that has coordinates (about half of them), weighted by status.
  Plants ("Facility") are skipped. The nationwide file is cached locally.
- NETL WELLS (Integrated Public Wells, CC-BY 4.0, DOE/NETL, DOI
  10.18141/1964068): oil and gas wells from 50+ state and federal sources.
  Each drilled well is a "well" point; resources.py turns their density into
  oil fields. Its ArcGIS service sends CORS headers, so a browser can query it.

Fuel commodities (oil, gas) become oil; everything mined, coal included,
becomes CS1 ore.

    uv run python evidence.py GEOMETRY_JSON OUTPUT_JSON
"""

import argparse
import csv
import gzip
import io
import json
import math
import time
import urllib.parse
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from prepare import pixel

MRDS = "https://mrdata.usgs.gov/mrds/search-bbox.php?xmin={w}&ymin={s}&xmax={e}&ymax={n}&format=xml"
WEIGHT = {"Producer": 1.0, "Past Producer": 0.8, "Prospect": 0.35}
OIL = {"OIL", "GAS", "PETROLEUM", "NATURAL GAS"}


MSHA = "https://arlweb.msha.gov/OpenGovernmentData/DataSets/Mines.zip"
MSHA_CACHE = Path.home() / ".cache/map-factory/msha-mines.txt"
MSHA_WEIGHT = {
    "Active": 1.0,
    "Intermittent": 0.9,
    "Temporarily Idled": 0.8,
    "Abandoned": 0.7,
    "Abandoned and Sealed": 0.7,
    "NonProducing": 0.6,
    "New Mine": 0.5,
}
NETL = (
    "https://arcgis.netl.doe.gov/server/rest/services/Hosted/"
    "Integrated_Public_Wells_AugEY25/FeatureServer/0/query"
)
NOT_A_WELL = {"Not drilled", "Permitted", "Cancelled", "Canceled", "Proposed"}


def bbox(sq):
    reach = 8640 * math.sqrt(2) * sq["scale"]
    dlat = reach / 111_000
    dlon = reach / (111_320 * math.cos(math.radians(sq["lat"])))
    return sq["lat"] - dlat, sq["lon"] - dlon, sq["lat"] + dlat, sq["lon"] + dlon


def game_xz(sq, lon, lat):
    col, row = pixel(sq, (lon, lat))
    return (float(col) - 540) * 16, (540 - float(row)) * 16


def mrds(sq):
    s, w, n, e = bbox(sq)
    request = urllib.request.Request(MRDS.format(s=s, w=w, n=n, e=e), headers={"User-Agent": "map-factory"})
    with urllib.request.urlopen(request, timeout=60) as response:
        root = ET.fromstring(response.read())
    out = []
    for record in root.iter("record"):
        status = record.get("dev_stat", "")
        weight = WEIGHT.get(status)
        deposit = record.find(".//deposits")
        operation = deposit.get("oper_tp", "") if deposit is not None else ""
        if not weight or operation == "Processing Plant":
            continue
        codes = {c.strip().upper() for c in record.get("code_list", "").split() if c.strip()}
        commodities = {c.get("value", "").upper() for c in record.iter("commodity")} | codes
        x, z = game_xz(sq, float(record.get("x")), float(record.get("y")))
        if max(abs(x), abs(z)) > 8640:
            continue
        kind = "oil" if commodities & OIL else "ore"
        out.append(
            {
                "kind": kind,
                "x": round(x, 1),
                "z": round(z, 1),
                "weight": weight,
                "source": f"USGS MRDS {record.get('dep_id')} {record.get('site_name')} ({status}, {operation or 'unknown'})",
            }
        )
    return out


def inside(sq, lon, lat):
    x, z = game_xz(sq, lon, lat)
    return (x, z) if max(abs(x), abs(z)) <= 8640 else None


def msha(sq):
    """MSHA mines with coordinates inside the region (cached nationwide file)."""
    if not MSHA_CACHE.exists() or time.time() - MSHA_CACHE.stat().st_mtime > 30 * 86400:
        MSHA_CACHE.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(MSHA, headers={"User-Agent": "map-factory"})
        with urllib.request.urlopen(request, timeout=300) as response:
            archive = zipfile.ZipFile(io.BytesIO(response.read()))
        MSHA_CACHE.write_bytes(archive.read("Mines.txt"))
    s, w, n, e = bbox(sq)
    csv.field_size_limit(10**7)
    out = []
    with MSHA_CACHE.open(encoding="latin-1", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="|"):
            try:
                lat, lon = float(row["LATITUDE"]), float(row["LONGITUDE"])
            except ValueError:
                continue
            if lon > 0 and row["STATE"] not in ("GU", "MP"):
                lon = -lon  # some US records omit the western sign
            if not (s <= lat <= n and w <= lon <= e) or row["CURRENT_MINE_TYPE"] == "Facility":
                continue
            weight = MSHA_WEIGHT.get(row["CURRENT_MINE_STATUS"])
            point = inside(sq, lon, lat)
            if not weight or point is None:
                continue
            kind = "coal" if row["COAL_METAL_IND"] == "C" else row["PRIMARY_CANVASS"] or "mine"
            out.append(
                {
                    "kind": "ore",
                    "x": round(point[0], 1),
                    "z": round(point[1], 1),
                    "weight": weight,
                    "source": f"MSHA {row['MINE_ID']} {row['CURRENT_MINE_NAME']} ({kind}, {row['CURRENT_MINE_TYPE']}, {row['CURRENT_MINE_STATUS']})",
                }
            )
    return out


def wells(sq):
    """Drilled oil and gas wells from NETL WELLS, one point each."""
    s, w, n, e = bbox(sq)
    query = {
        "where": "1=1",
        "geometry": f"{w},{s},{e},{n}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "outSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "type_category,status_category",
        "orderByFields": "objectid",
        "resultRecordCount": "2000",
        "f": "json",
    }
    out, offset = [], 0
    while True:
        url = NETL + "?" + urllib.parse.urlencode({**query, "resultOffset": str(offset)})
        request = urllib.request.Request(url, headers={"User-Agent": "map-factory"})
        with urllib.request.urlopen(request, timeout=120) as response:
            page = json.load(response)
        if "error" in page:
            raise RuntimeError(f"NETL WELLS query failed: {page['error']}")
        features = page.get("features", [])
        for f in features:
            a, g = f["attributes"], f.get("geometry") or {}
            kind, status = a.get("type_category") or "", a.get("status_category") or ""
            if not any(t in kind for t in ("Oil", "Gas", "Production")) or status in NOT_A_WELL:
                continue
            point = inside(sq, g.get("x"), g.get("y")) if "x" in g else None
            if point is None:
                continue
            out.append({"kind": "well", "x": round(point[0], 1), "z": round(point[1], 1), "type": kind, "status": status})
        if not page.get("exceededTransferLimit") and len(features) < 2000:
            return out
        offset += len(features)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("geometry", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    raw = args.geometry.read_bytes()
    geometry = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    sq = geometry["sq"]
    evidence = mrds(sq) + msha(sq) + wells(sq)
    sources = [
        "USGS MRDS (public domain)",
        "MSHA Mines dataset (public domain)",
        "NETL WELLS / Integrated Public Wells, 2025-08 (CC-BY 4.0, DOI 10.18141/1964068)",
    ]
    args.output.write_text(json.dumps({"evidence": evidence, "sources": sources}, indent=1) + "\n")
    kinds = {k: sum(1 for e in evidence if e["kind"] == k) for k in ["ore", "oil", "well"]}
    print(json.dumps({"output": str(args.output), **kinds, "deposits": [e["source"] for e in evidence if "source" in e]}, indent=2))


if __name__ == "__main__":
    main()
