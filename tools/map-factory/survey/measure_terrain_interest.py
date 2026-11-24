"""Measure the two terrain-shape interest measures on the shipped CS1 maps.

Read-only over the game's Maps folder. Reuses `measure_maps.py` for the CRP
package/terrain decoding and `terrain_interest.py` for the measure itself, so a
stock observation, a prepared report and the live capture share one predicate.
Writes a new artifact; the historical basemaps survey is never overwritten.

    cd tools/map-factory
    uv run python survey/measure_terrain_interest.py \
        /peach/Games/SteamLibrary/steamapps/common/Cities_Skylines/Files/Maps/ \
        survey/terrain-interest.json
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
FACTORY = HERE.parent
ROOT = FACTORY.parents[1]
for entry in (str(FACTORY), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from survey.measure_maps import data_version, parse_terrain, read_any  # noqa: E402
from terrain_interest import TERRAIN_INTEREST_MEASURES, terrain_interest_metrics  # noqa: E402

SCHEMA = 1
VERSION = "pl1228-terrain-interest-v1"
DEFAULT_MAPS = "/peach/Games/SteamLibrary/steamapps/common/Cities_Skylines/Files/Maps/"
EXCLUDED = {"CO.crp": "blank editor terrain system package, not a playable shipped map"}
QUANTILES = (
    "Linear interpolation at (n-1)*p over the included rows; bands are strictly "
    "below p25, inclusive typical, strictly above p75. Descriptive, not quality gates."
)
FIDELITY = (
    "Shipped CRP terrain at the game's 1/64 m unit on the 1081 x 1081, 16 m, "
    "south-first grid, decoded by survey/measure_maps.py (CS1 1.21.1-f9 gates)."
)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def quantile(values, p):
    index = (len(values) - 1) * p
    lo, hi = int(np.floor(index)), int(np.ceil(index))
    return float(values[lo] + (values[hi] - values[lo]) * (index - lo))


def file_entry(path):
    raw = path.read_bytes()
    entry = {
        "file": path.name,
        "sha256": sha256(raw),
        "bytes": len(raw),
        "package_format": None,
        "data_version": None,
        "display": None,
    }
    try:
        package, assets = read_any(raw)
        simulation = next(a for a in assets if a["kind"] == 52)
        entry["package_format"] = package["format"]
        entry["data_version"] = data_version(simulation["payload"])
        entry["display"] = simulation["name"].rsplit("_Data", 1)[0]
    except Exception:
        # Not fatal here: the record keeps the package metadata it could read,
        # and the measure attempt below records a real failure if it has one.
        pass
    return entry


def measure_file(path):
    _, assets = read_any(path.read_bytes())
    simulation = next(a for a in assets if a["kind"] == 52)
    return terrain_interest_metrics(parse_terrain(simulation["payload"]))


def build(maps_dir):
    maps_dir = Path(maps_dir).absolute()
    files = sorted(maps_dir.glob("*.crp"), key=lambda p: p.name)
    rows, excluded, failures = [], [], []
    for path in files:
        if path.name in EXCLUDED:
            excluded.append({"file": path.name, "reason": EXCLUDED[path.name]})
            continue
        try:
            values = measure_file(path)
            rows.append({**file_entry(path), **values})
        except Exception as error:  # keep going; record the failure
            failures.append(
                {"file": path.name, "error": f"{type(error).__name__}: {error}"}
            )
        print(
            f"{path.name}: {'failed' if failures and failures[-1]['file'] == path.name else 'ok'}",
            file=sys.stderr,
            flush=True,
        )
    rows.sort(key=lambda row: row["file"])
    quantiles = {}
    for measure_id, measure in TERRAIN_INTEREST_MEASURES.items():
        values = sorted(row[measure_id] for row in rows)
        quantiles[measure_id] = {
            "name": measure["name"],
            "unit": measure["unit"],
            "kind": measure["kind"],
            "definition": measure["definition"],
            "n": len(values),
            "p25": quantile(values, 0.25),
            "median": quantile(values, 0.5),
            "p75": quantile(values, 0.75),
        }
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scope": "Terrain shape only: no water mask and no buildability screen.",
        "fidelity": FIDELITY,
        "quantiles_policy": QUANTILES,
        "measures": {
            measure_id: {
                "name": measure["name"],
                "unit": measure["unit"],
                "kind": measure["kind"],
                "definition": measure["definition"],
            }
            for measure_id, measure in TERRAIN_INTEREST_MEASURES.items()
        },
        "tool": {
            "reader": {
                "file": "tools/map-factory/survey/measure_maps.py",
                "sha256": sha256((HERE / "measure_maps.py").read_bytes()),
            },
            "measure_tool": {
                "file": "tools/map-factory/survey/measure_terrain_interest.py",
                "sha256": sha256(Path(__file__).read_bytes()),
            },
            "measure_source": {
                "file": "tools/map-factory/terrain_interest.py",
                "sha256": sha256((FACTORY / "terrain_interest.py").read_bytes()),
            },
        },
        "maps": {
            "directory": str(maps_dir) + os.sep,
            "read_only": True,
            "files_seen": len(files),
            "included": len(rows),
            "excluded": excluded,
            "failures": failures,
        },
        "quantiles": quantiles,
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("maps", nargs="?", default=DEFAULT_MAPS)
    parser.add_argument("out", nargs="?", default=str(HERE / "terrain-interest.json"))
    args = parser.parse_args()
    artifact = build(args.maps)
    Path(args.out).write_text(json.dumps(artifact, indent=1) + "\n")
    print(
        f"{artifact['maps']['included']} of {artifact['maps']['files_seen']} maps; "
        f"{len(artifact['quantiles'])} measures -> {args.out}"
    )
    if artifact["maps"]["failures"]:
        # The artifact keeps the failures; a red run keeps them from being lost.
        raise SystemExit(
            "measured with failures: "
            + "; ".join(
                f"{f['file']}: {f['error']}" for f in artifact["maps"]["failures"]
            )
        )


if __name__ == "__main__":
    main()
