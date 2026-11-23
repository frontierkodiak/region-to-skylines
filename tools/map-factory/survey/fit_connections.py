"""Fit mapped-water width to stock-map connection labels. No game or writer calls."""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE)]
from connection_rules import DEFAULTS, edge_connection, water_width  # noqa: E402
from survey.measure_maps import read_any, data_version, parse_water, parse_metadata  # noqa: E402
from survey.craft_anatomy import parse_network, check_network, net_class  # noqa: E402


def measure(path):
    _, assets = read_any(path.read_bytes())
    payload = next(a["payload"] for a in assets if a["kind"] == 52)
    meta = parse_metadata(next(a["payload"] for a in assets if a["kind"] == 100))
    row = {
        "file": path.name,
        "labels": {
            k: meta[f] > 0
            for k, f in zip(
                ("road", "rail", "ship", "air"),
                (
                    "incomingRoads",
                    "incomingTrainTracks",
                    "incomingShipPath",
                    "incomingPlanePath",
                ),
            )
        },
    }
    wet = (parse_water(payload)[::4, ::4] > 0.5).astype(int)
    row["width_m"] = water_width(
        dict(size=271, spacing_m=64, water=wet.ravel().tolist())
    )
    try:
        version = data_version(payload)
        net = parse_network(payload, version)
        if check_network(net) and 221 <= version < 115000:
            net = parse_network(payload, version, "uint")
        if check_network(net):
            raise ValueError("network layout consistency")
        by = {node["id"]: node for node in net["nodes"]}
        lines = []
        for segment in net["segments"]:
            cls = net_class(net["names"][segment["info"]])
            if cls not in ("road", "rail") or (
                cls == "road" and "highway" not in net["names"][segment["info"]].lower()
            ):
                continue
            points = [by[segment[key]]["pos"] for key in ("a", "b")]
            lines.append(
                dict(
                    class_="motorway" if cls == "road" else "rail",
                    pts=[[p[0], p[2]] for p in points],
                )
            )
        lines = [{"class": r["class_"], "pts": r["pts"]} for r in lines]
        for kind in ("road", "rail"):
            result = edge_connection(lines, kind, 8640, DEFAULTS["edge_margin_m"])
            row[kind] = result["level"] == "yes"
    except (ValueError, KeyError, IndexError, OverflowError) as error:
        row["network_unavailable"] = str(error)
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("maps", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows = []
    for path in sorted(args.maps.glob("*.crp")):
        if path.name == "CO.crp":
            continue
        rows.append(measure(path))
        print(path.name, rows[-1]["width_m"], file=sys.stderr, flush=True)
    # Four cells is the minimum resolved corridor; fit balanced accuracy above it.
    # Tie = smaller threshold. Geography is not a model feature.
    positives = sum(r["labels"]["ship"] for r in rows)
    negatives = len(rows) - positives
    candidates = []
    for threshold in range(64, 2049, 64):
        tp = sum(r["labels"]["ship"] and r["width_m"] >= threshold for r in rows)
        tn = sum(not r["labels"]["ship"] and r["width_m"] < threshold for r in rows)
        candidates.append((tp / positives + tn / negatives, -threshold))
    unconstrained = -max(candidates)[1]
    threshold = -max(c for c in candidates if -c[1] >= 256)[1]
    rules = {**DEFAULTS, "ship_width_m": threshold}
    agreement = {}
    for kind in ("road", "rail", "ship", "air"):
        eligible = [r for r in rows if kind not in ("road", "rail") or kind in r]

        def predicted(r):
            if kind in ("road", "rail"):
                return r[kind]
            return r["width_m"] >= threshold if kind == "ship" else True

        correct = sum(predicted(r) == r["labels"][kind] for r in eligible)
        agreement[kind] = {
            "agree": correct,
            "total": len(eligible),
            "fraction": correct / len(eligible),
            "basis": "stock geometry fit (in-sample)",
        }
    result = dict(
        rules=rules,
        unconstrained_threshold_m=unconstrained,
        resolution_floor_cells=4,
        stock_agreement=agreement,
        rows=rows,
        fit="Maximum balanced ship-label accuracy over 256..2048m in 64m steps; four-cell resolution floor; ties use smaller threshold. 104 stock maps; blank CO excluded. Road/rail same edge-crossing predicate where network geometry decodes. Air is the all-yes baseline.",
        fidelity="271x271 point lattice at 64m; stock saved depth >0.5m, live mapped water polygons. Chebyshev bank clearance, 4-connected water, edge points separated >=512m or mapped open sea. No depth or simulation claim.",
    )
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"rules": rules, "agreement": agreement}))


if __name__ == "__main__":
    main()
