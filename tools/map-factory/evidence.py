"""Real-world ore and oil evidence for a region, in game metres.

USGS Mineral Resources Data System (MRDS, public domain; mostly US) records
inside the region become ore or oil evidence, weighted by development status:
producers and past producers count, prospects count a little, bare
occurrences don't. Processing plants (steel works, coke ovens, cement and
brick plants) are skipped: they mark industry, not a deposit. Fuel commodities (oil, gas) become
oil; everything mined, coal included, becomes CS1 ore.

    uv run python evidence.py GEOMETRY_JSON OUTPUT_JSON
"""

import argparse
import gzip
import json
import math
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from prepare import pixel

MRDS = "https://mrdata.usgs.gov/mrds/search-bbox.php?xmin={w}&ymin={s}&xmax={e}&ymax={n}&format=xml"
WEIGHT = {"Producer": 1.0, "Past Producer": 0.8, "Prospect": 0.35}
OIL = {"OIL", "GAS", "PETROLEUM", "NATURAL GAS"}


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("geometry", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    raw = args.geometry.read_bytes()
    geometry = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    evidence = mrds(geometry["sq"])
    args.output.write_text(
        json.dumps({"evidence": evidence, "sources": ["USGS MRDS (public domain)"]}, indent=2) + "\n"
    )
    kinds = {k: sum(1 for e in evidence if e["kind"] == k) for k in ["ore", "oil"]}
    print(json.dumps({"output": str(args.output), **kinds, "records": [e["source"] for e in evidence]}, indent=2))


if __name__ == "__main__":
    main()
