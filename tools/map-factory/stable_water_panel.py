"""Reproduce the ex-ante PL-1191 panel, without fetching inputs or game labels."""

import argparse
import hashlib
import json
import math
from pathlib import Path

# Purposive coverage, not a random-world prevalence sample. These anchors are
# fixed before exporter changes; capture failures and awkward squares stay in.
ANCHORS = [
    ("dry_upland", "north_america", 40.5, -116.6),
    ("mountain_river", "south_america", -32.8, -70.2),
    ("lowland_river", "europe", 44.4, 26.1),
    ("lake_shore", "africa", -14.0, 34.9),
    ("dry_upland", "asia", 46.5, 103.5),
    ("mountain_river", "oceania", -45.0, 168.8),
    ("low_coast", "north_america", 45.5, -123.95),
    ("low_coast", "south_america", -33.0, -71.6),
    ("low_coast", "europe", 43.5, 16.4),
    ("low_coast", "africa", -33.95, 25.6),
    ("low_coast", "asia", 18.5, 109.0),
    ("low_coast", "oceania", -35.0, 117.9),
]


def distance_km(left, right):
    """Great-circle centre distance; also handles the date line."""
    lat1, lat2 = map(math.radians, (left["lat"], right["lat"]))
    dlat = lat2 - lat1
    dlon = math.radians(right["lon"] - left["lon"])
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1, a)))


def panel():
    squares = []
    for stratum, region, lat, lon in ANCHORS:
        slug = f"stable-{stratum}-{region}".replace("_", "-")
        seed = hashlib.sha256(f"PL-1191-panel-v1:{slug}".encode()).digest()
        east, north = [
            (int.from_bytes(seed[i : i + 4], "big") / (2**32 - 1) * 2 - 1) * 3000
            for i in (0, 4)
        ]
        squares.append(
            {
                "stratum": stratum,
                "world_region": region,
                "anchor_lat": lat,
                "anchor_lon": lon,
                "expected_drying_negative": stratum == "dry_upland",
                "sq": {
                    "slug": slug,
                    "name": "Stable water " + slug,
                    "lat": round(lat + north / 111320, 8),
                    "lon": round(
                        lon + east / (111320 * math.cos(math.radians(lat))), 8
                    ),
                    "rotation": 0,
                    "scale": 1,
                    "vscale": "auto",
                    "rivers": True,
                },
            }
        )
    return {
        "schema": 1,
        "version": "PL-1191-panel-v1",
        "selection": "Twelve fixed anchors: one inland setting and one coast per world region; SHA256 offsets within +/-3 km. Frozen before any exporter change or input fetch. No replacement, per-square repair, or outcome-based exclusion.",
        "estimand": "Gross construction failures on this purposive panel, not global safety or rare-failure prevalence. Six coasts, two dry uplands, two mountain rivers, one lowland river and one lake.",
        "squares": squares,
    }


def separation(selected, excluded):
    """Fail if either panel overlaps or is within 100 km of development data."""
    distances = []
    for index, item in enumerate(selected["squares"]):
        for other in excluded + selected["squares"][:index]:
            distance = distance_km(item["sq"], other["sq"])
            if distance < 100:
                raise ValueError(
                    f"Insufficient separation: {item['sq']['slug']} / {other['sq']['slug']}"
                )
            distances.append(distance)
    return min(distances)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with args.output.open("x") as stream:
        json.dump(panel(), stream, indent=2)
        stream.write("\n")
