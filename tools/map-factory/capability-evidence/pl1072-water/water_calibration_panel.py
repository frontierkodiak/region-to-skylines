"""Freeze a geography-disjoint panel before fetching inputs or observing games."""

import argparse
import hashlib
import json
import math
from pathlib import Path

# The anchors are a purposive panel, not a random sample of the world's land.
# They are written before input capture. Never replace an awkward/failed square.
ANCHORS = {
    "dry_upland": [
        ("north_america", 39.2, -110.3),
        ("south_america", -24.6, -65.7),
        ("europe", 37.2, -2.5),
        ("africa", 30.6, -6.5),
        ("asia", 31.3, 79.8),
        ("oceania", -23.6, 133.8),
    ],
    "mountain_river": [
        ("north_america", 50.7, -121.4),
        ("south_america", -13.3, -72.1),
        ("europe", 46.3, 7.9),
        ("africa", -29.3, 28.2),
        ("asia", 29.4, 103.5),
        ("oceania", -42.8, 171.1),
    ],
    "lowland_river": [
        ("north_america", 38.6, -90.2),
        ("south_america", -3.1, -60.0),
        ("europe", 48.3, 16.4),
        ("africa", 15.6, 32.5),
        ("asia", 30.6, 114.3),
        ("oceania", -34.4, 140.6),
    ],
    "lake_shore": [
        ("north_america", 46.8, -92.1),
        ("south_america", -15.8, -69.4),
        ("europe", 46.5, 6.6),
        ("africa", -2.5, 32.9),
        ("asia", 52.5, 106.0),
        ("oceania", -38.1, 176.1),
    ],
    "low_coast": [
        ("north_america", 29.3, -94.8),
        ("south_america", -34.6, -58.4),
        ("europe", 51.9, 4.4),
        ("africa", 6.4, 3.4),
        ("asia", 31.3, 121.8),
        ("oceania", -27.4, 153.1),
    ],
}


def panel():
    squares = []
    for stratum, anchors in ANCHORS.items():
        for region, lat, lon in anchors:
            slug = f"{stratum}-{region}".replace("_", "-")
            seed = hashlib.sha256(f"PL-1072-panel-v1:{slug}".encode()).digest()
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
                        "name": "Calibration " + slug,
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
        "version": "PL-1072-panel-v1",
        "selection": "Five ex-ante strata x six world regions; SHA256 offsets within +/-3 km of fixed written anchors. All 30 retained, including capture failures and unexpected terrain. No fixture squares.",
        "estimand": "Equal-weight performance on this purposive panel, not global deployment prevalence.",
        "squares": squares,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with args.output.open("x") as stream:
        json.dump(panel(), stream, indent=2)
        stream.write("\n")
