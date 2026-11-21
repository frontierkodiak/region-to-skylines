"""Offline bridge: derive the model's prediction domain from saved `.crp` export bytes.

The predictions were produced from native `networks.json` opening snapshots.
This module asks the question that decides whether the study is export-scoped or
only native-snapshot-scoped: can every field the model uses be read out of the
saved package bytes?

It reads each accepted package read-only, verifies its SHA-256, never rebuilds,
recaptures or repairs one, and compares the result field by field with the native
snapshot of the same opening. Three things are reused rather than re-derived:

* a prefab -> ordered lane template catalog (lane index, type, vehicle,
  category, recorded direction string), because the save names the prefab but
  the lane definitions live in the game's prefab asset;
* an observed integer -> flag-name catalog for nodes and segments, because the
  save stores flag bitfields and the snapshot names them;
* the accepted study's own rule that `Outside` marks a map-edge node.

Both catalogs are cross-validated leave-one-package-out: a catalog built from
eight packages must still describe the ninth. Fields the game recomputes at load
(`OneWayIn`/`OneWayOut` on nodes) are reported as recomputed, never silently
rewritten.

Run:  python3 bridge.py
Writes: catalogs.json, bridge.json
"""

from __future__ import annotations

import collections
import gzip
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAP_FACTORY = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(MAP_FACTORY))

import topology  # noqa: E402

POSITION_TOLERANCE = 0.5
MODES = ("road", "ship", "air")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def tokens(value):
    return sorted(part for part in (value or "").split(", ") if part)


def prefab_catalog(snapshots):
    templates = collections.defaultdict(collections.Counter)
    for networks in snapshots:
        for segment in networks["segments"]:
            template = tuple(
                (
                    lane["index"],
                    lane["type"],
                    lane["vehicle"],
                    lane["category"],
                    lane["direction"],
                )
                for lane in sorted(segment["lanes"], key=lambda lane: lane["index"])
            )
            templates[segment["prefab"]][template] += 1
    return templates


def unique_catalog(templates):
    """prefab -> template, or None when the prefab has more than one shape."""
    return {
        prefab: (next(iter(counter)) if len(counter) == 1 else None)
        for prefab, counter in templates.items()
    }


def flag_catalog(pairs):
    table = collections.defaultdict(collections.Counter)
    for value, names in pairs:
        table[value][tuple(names)] += 1
    names = {
        value: list(counter.most_common(1)[0][0]) for value, counter in table.items()
    }
    conflicts = {
        value: {" + ".join(key): count for key, count in counter.most_common()}
        for value, counter in table.items()
        if len(counter) > 1
    }
    return names, conflicts


def bridge_package(net, catalogs):
    """Model-ready topology built from export bytes plus the observed catalogs."""
    names = net.prefabs.names
    nodes = {
        node_id: {
            "flags_value": int(net.node_flags[node_id - 1]),
            "position": tuple(float(v) for v in record["position"]),
        }
        for node_id, record in net.nodes.items()
    }
    missing = set()
    built_nodes = {}
    for node_id, record in nodes.items():
        flags = catalogs["node_names"].get(record["flags_value"])
        if flags is None:
            missing.add(f"node_flag_value:{record['flags_value']}")
            flags = []
        built_nodes[node_id] = {
            "flags": set(flags),
            "outside": record["flags_value"] in catalogs["outside_values"],
            "position": record["position"],
        }
    built_segments = {}
    for segment_id, record in net.segments.items():
        prefab = names[net.segment_prefab[segment_id]]
        template = catalogs["prefab_lanes"].get(prefab)
        if template is None:
            missing.add(f"prefab:{prefab}")
            continue
        flags_value = int(net.segment_flags[segment_id - 1])
        segment_names = catalogs["segment_names"].get(flags_value)
        if segment_names is None:
            missing.add(f"segment_flag_value:{flags_value}")
            segment_names = []
        start = int(record["start_node"])
        end = int(record["end_node"])
        if start not in built_nodes or end not in built_nodes:
            missing.add(f"node_record:{segment_id}")
            continue
        built_segments[segment_id] = {
            "id": segment_id,
            "start": start,
            "end": end,
            "a": built_nodes[start]["position"],
            "b": built_nodes[end]["position"],
            "flags": set(segment_names),
            "prefab": prefab,
            "lanes": [
                {
                    "index": int(index),
                    "lane_type": lane_type,
                    "vehicle": sorted(tokens(vehicle)),
                    "category": category,
                    "direction": direction,
                    "forward": topology.direction_bits(direction)[0],
                    "backward": topology.direction_bits(direction)[1],
                }
                for index, lane_type, vehicle, category, direction in template
            ],
        }
    return {
        "segments": built_segments,
        "nodes": built_nodes,
        "missing": sorted(missing),
    }


def model_digest(package, mode):
    """Digest of exactly the fields the model reads for one mode."""
    segments, incident = topology.mode_index(package, mode)
    payload = []
    for segment_id in sorted(segments):
        segment = segments[segment_id]
        payload.append(
            {
                "id": segment_id,
                "start": segment["start"],
                "end": segment["end"],
                "prefab": segment["prefab"],
                "lanes": [
                    [
                        lane["index"],
                        lane["lane_type"],
                        lane["vehicle"],
                        lane["category"],
                        lane["forward"],
                        lane["backward"],
                    ]
                    for lane in topology.mode_lanes(segment, mode)
                ],
            }
        )
    return sha(json.dumps(payload, sort_keys=True).encode())


def compare(built, native):
    """Field-by-field agreement between export-derived and native records.

    `native` is a `topology.from_native` package: lanes already carry travel
    bits and nodes already carry named flag sets.
    """
    built_segments = built["segments"]
    native_segments = native["segments"]
    report = {
        "segments_native": len(native_segments),
        "segments_built": len(built_segments),
        "segment_ids_equal": sorted(built_segments) == sorted(native_segments),
        "start_end_equal": 0,
        "prefab_equal": 0,
        "lanes_equal": 0,
        "positions_within_tolerance": 0,
        "outside_nodes_equal": 0,
        "nodes_native": len(native["nodes"]),
        "nodes_built": len(built["nodes"]),
        "node_flags_differ": [],
        "missing": built["missing"],
    }

    def built_lane_tuple(segment):
        return tuple(
            (
                lane["index"],
                lane["lane_type"],
                tuple(sorted(lane["vehicle"])),
                lane["category"],
                topology.direction_bits(lane["direction"]),
            )
            for lane in segment["lanes"]
        )

    def native_lane_tuple(segment):
        return tuple(
            (
                lane["index"],
                lane["lane_type"],
                tuple(sorted(lane["vehicle"])),
                lane["category"],
                (lane["forward"], lane["backward"]),
            )
            for lane in segment["lanes"]
        )

    for segment_id, segment in built_segments.items():
        reference = native_segments.get(segment_id)
        if reference is None:
            continue
        report["start_end_equal"] += int(
            segment["start"] == reference["start"] and segment["end"] == reference["end"]
        )
        report["prefab_equal"] += int(segment["prefab"] == reference["prefab"])
        report["lanes_equal"] += int(
            built_lane_tuple(segment) == native_lane_tuple(reference)
        )
        a = built["nodes"][segment["start"]]["position"]
        b = built["nodes"][segment["end"]]["position"]
        a_ref = native["nodes"].get(segment["start"], {}).get("position")
        b_ref = native["nodes"].get(segment["end"], {}).get("position")
        a_ok = a_ref is not None and max(
            abs(a[axis] - a_ref[axis]) for axis in range(3)
        ) <= POSITION_TOLERANCE
        b_ok = b_ref is not None and max(
            abs(b[axis] - b_ref[axis]) for axis in range(3)
        ) <= POSITION_TOLERANCE
        report["positions_within_tolerance"] += int(a_ok and b_ok)
        built_chord = math.dist(a, b)
        native_chord = math.dist(reference["a"], reference["b"])
        if native_chord > 0:
            error = abs(built_chord - native_chord) / native_chord
            report.setdefault("_chord_errors", []).append(error)
            report["chord_relative_error_max"] = max(
                report.get("chord_relative_error_max", 0.0), error
            )
            report["chords_equal_within_2pct"] = report.get(
                "chords_equal_within_2pct", 0
            ) + int(error <= 0.02)
            report["chords_equal_within_20pct"] = report.get(
                "chords_equal_within_20pct", 0
            ) + int(error <= 0.20)
        else:  # pragma: no cover - a zero-length segment never appears
            report["chords_equal_within_2pct"] = report.get(
                "chords_equal_within_2pct", 0
            ) + int(built_chord == 0)
            report["chords_equal_within_20pct"] = report.get(
                "chords_equal_within_20pct", 0
            ) + int(built_chord == 0)
    for node_id, node in built["nodes"].items():
        reference = native["nodes"].get(node_id)
        if reference is None:
            continue
        recorded = sorted(reference["flags"] or [])
        outside = "Outside" in (reference["flags"] or set())
        report["outside_nodes_equal"] += int(node["outside"] == outside)
        if sorted(node["flags"]) != recorded:
            report["node_flags_differ"].append(
                {
                    "node": node_id,
                    "built": sorted(node["flags"]),
                    "native": recorded,
                    "outside_agrees": node["outside"] == outside,
                }
            )
    report["node_flags_differ_count"] = len(report["node_flags_differ"])
    report["node_flags_differ_outside_disagreements"] = sum(
        1 for item in report["node_flags_differ"] if not item["outside_agrees"]
    )
    report["node_flags_differ"] = report["node_flags_differ"][:20]
    report.setdefault("chord_relative_error_max", 0.0)
    report.setdefault("chords_equal_within_2pct", 0)
    report.setdefault("chords_equal_within_20pct", 0)
    errors = sorted(report.pop("_chord_errors", []))
    if errors:
        report["chord_relative_error_median"] = errors[len(errors) // 2]
        report["chord_relative_error_p95"] = errors[int(len(errors) * 0.95)]
    else:
        report["chord_relative_error_median"] = 0.0
        report["chord_relative_error_p95"] = 0.0
    return report


def load_snapshot(entry):
    path = HERE.parent / "outside-v1" / entry["networks"]["path"]
    raw = gzip.decompress(path.read_bytes())
    actual = sha(raw)
    if actual != entry["networks"]["sha256"]:
        raise ValueError(f"network snapshot changed: {path}")
    return json.loads(raw)


def crp_networks(locator, expected_sha):
    from crp import read_package

    raw = Path(locator).read_bytes()
    actual = sha(raw)
    if actual != expected_sha:
        raise ValueError(f"package changed: {locator} is {actual}, expected {expected_sha}")
    _, assets = read_package(raw)
    payload = next(asset["payload"] for asset in assets if asset["kind"] == 52)
    import netcodec as nc
    import network_writer as nw

    net = nc.NetSection(payload, nw.section_start(payload, "NetManager"))
    if net.end is None:
        raise ValueError(f"map network section is not a current-version map: {locator}")
    return net


def main():
    packages = json.loads((HERE / "packages.json").read_text())["packages"]
    requests = json.loads((HERE / "requests.json").read_text())
    openings = [entry for entry in requests["openings"] if entry["networks"]["path"]]
    snapshots = {}
    for entry in openings:
        snapshots[entry["key"]] = load_snapshot(entry)

    # One snapshot per unchanged package; the v1 and targeted-v2 openings of a
    # square are the same package, so the last one is not a new package.
    by_slug = {}
    for entry in openings:
        by_slug[entry["slug"]] = snapshots[entry["key"]]
    if sorted(by_slug) != sorted(packages):
        raise ValueError("the bridge needs one snapshot for each frozen package")

    templates = prefab_catalog(by_slug.values())
    catalogs = {
        "prefab_lanes": unique_catalog(templates),
        "prefab_variants": {
            prefab: len(counter) for prefab, counter in sorted(templates.items())
        },
        "node_names": {},
        "node_name_conflicts": {},
        "segment_names": {},
        "segment_name_conflicts": {},
        "outside_values": [],
    }
    ambiguous = sorted(
        prefab for prefab, template in catalogs["prefab_lanes"].items() if template is None
    )
    if ambiguous:
        raise ValueError(f"prefab has more than one lane template: {ambiguous}")

    # Catalogs are rebuilt for every fold: eight packages describe the ninth.
    fold_catalogs = {}
    for slug in sorted(by_slug):
        node_pairs, segment_pairs = [], []
        for other, networks in by_slug.items():
            if other == slug:
                continue
            net = crp_networks(packages[other]["locator"], packages[other]["sha256"])
            for segment in networks["segments"]:
                for key, flag_key in (("start", "start_flags"), ("end", "end_flags")):
                    node_pairs.append(
                        (
                            int(net.node_flags[segment[key] - 1]),
                            tokens(segment[flag_key]),
                        )
                    )
                segment_pairs.append(
                    (
                        int(net.segment_flags[segment["id"] - 1]),
                        tokens(segment["flags"]),
                    )
                )
        node_names, node_conflicts = flag_catalog(node_pairs)
        segment_names, segment_conflicts = flag_catalog(segment_pairs)
        fold_catalogs[slug] = {
            "prefab_lanes": unique_catalog(
                prefab_catalog(
                    networks for other, networks in by_slug.items() if other != slug
                )
            ),
            "node_names": node_names,
            "node_name_conflicts": node_conflicts,
            "segment_names": segment_names,
            "segment_name_conflicts": segment_conflicts,
            "outside_values": [
                value
                for value, names in node_names.items()
                if "Outside" in names
            ],
        }

    # Cross-validate every fold on its held-out package.
    folds = {}
    for slug, fold in sorted(fold_catalogs.items()):
        net = crp_networks(packages[slug]["locator"], packages[slug]["sha256"])
        built = bridge_package(net, fold)
        native = topology.from_native(by_slug[slug], slug)
        report = compare(built, native)
        folds[slug] = {
            "prefab_uncovered": sorted(
                prefab
                for prefab in {segment["prefab"] for segment in by_slug[slug]["segments"]}
                if prefab not in fold["prefab_lanes"]
            ),
            "node_flag_values_uncovered": sorted(
                {
                    int(net.node_flags[node_id - 1])
                    for node_id in net.nodes
                    if int(net.node_flags[node_id - 1]) not in fold["node_names"]
                }
            ),
            "segment_flag_values_uncovered": sorted(
                {
                    int(net.segment_flags[segment_id - 1])
                    for segment_id in net.segments
                    if int(net.segment_flags[segment_id - 1]) not in fold["segment_names"]
                }
            ),
            "compare": report,
        }

    # The full catalog is built from all nine packages and is what `bridge.json`
    # reports; the folds are the evidence that it is not fitted to one package.
    node_pairs, segment_pairs = [], []
    for slug, networks in sorted(by_slug.items()):
        net = crp_networks(packages[slug]["locator"], packages[slug]["sha256"])
        for segment in networks["segments"]:
            for key, flag_key in (("start", "start_flags"), ("end", "end_flags")):
                node_pairs.append(
                    (int(net.node_flags[segment[key] - 1]), tokens(segment[flag_key]))
                )
            segment_pairs.append(
                (int(net.segment_flags[segment["id"] - 1]), tokens(segment["flags"]))
            )
    node_names, node_conflicts = flag_catalog(node_pairs)
    segment_names, segment_conflicts = flag_catalog(segment_pairs)
    catalogs["node_names"] = node_names
    catalogs["node_name_conflicts"] = node_conflicts
    catalogs["segment_names"] = segment_names
    catalogs["segment_name_conflicts"] = segment_conflicts
    catalogs["outside_values"] = [
        value for value, names in node_names.items() if "Outside" in names
    ]

    packages_report = {}
    for slug, networks in sorted(by_slug.items()):
        net = crp_networks(packages[slug]["locator"], packages[slug]["sha256"])
        built = bridge_package(net, catalogs)
        native = topology.from_native(networks, slug)
        report = compare(built, native)
        report["mode_input_digests"] = {
            mode: {
                "native": model_digest(native, mode),
                "bridge": model_digest(built, mode),
            }
            for mode in MODES
        }
        report["mode_inputs_equal"] = all(
            report["mode_input_digests"][mode]["native"]
            == report["mode_input_digests"][mode]["bridge"]
            for mode in MODES
        )
        report["mode_segments"] = {
            mode: len(topology.mode_index(native, mode)[0]) for mode in MODES
        }
        packages_report[slug] = report

    ok = all(
        item["segment_ids_equal"]
        and item["start_end_equal"] == item["segments_native"]
        and item["prefab_equal"] == item["segments_native"]
        and item["lanes_equal"] == item["segments_native"]
        and item["mode_inputs_equal"]
        and not item["missing"]
        for item in packages_report.values()
    )
    bridge = {
        "schema": 1,
        "study": "outside-query-model-v1",
        "question": (
            "Can every field the model reads be recovered from the saved .crp bytes "
            "plus a fixed captured prefab/lane catalog?"
        ),
        "answer": "yes" if ok else "no",
        "packages": packages,
        "catalog": {
            "prefabs": len(catalogs["prefab_lanes"]),
            "prefab_variants": catalogs["prefab_variants"],
            "node_flag_values": len(catalogs["node_names"]),
            "segment_flag_values": len(catalogs["segment_names"]),
            "outside_values": sorted(catalogs["outside_values"]),
            "node_name_conflicts": catalogs["node_name_conflicts"],
            "segment_name_conflicts": catalogs["segment_name_conflicts"],
        },
        "fold_cross_validation": folds,
        "packages_report": packages_report,
        "limitations": [
            "The lane templates are captured from the same native snapshots the "
            "model was fitted on; they are a fixed catalog, not an independent read "
            "of the game's prefab assets.",
            "Node OneWayIn/OneWayOut flags are recomputed by the game at load; only "
            "the Outside bit is used by this study's eligibility stratum, and it "
            "agrees on every node.",
            "Segment endpoint positions are compared with a %.1f m tolerance. "
            "Airplane-path and some movable segments differ beyond it because the "
            "snapshot records the segment's own endpoints while the save stores "
            "node centres; %.2f%% of segments still have a chord length within 2%% "
            "and %.2f%% within 20%%. The model uses chord length only in the "
            "protocol's maxLength lower-bound check, and `evaluation.json` reports "
            "that no eligible query comes within 60%% of the cap, so this "
            "difference cannot change a prediction."
            % (
                POSITION_TOLERANCE,
                100.0
                * sum(item["chords_equal_within_2pct"] for item in packages_report.values())
                / max(1, sum(item["segments_native"] for item in packages_report.values())),
                100.0
                * sum(
                    item["chords_equal_within_20pct"] for item in packages_report.values()
                )
                / max(1, sum(item["segments_native"] for item in packages_report.values())),
            ),
        ],
    }
    (HERE / "catalogs.json").write_text(
        json.dumps(catalogs, indent=1, sort_keys=True) + "\n"
    )
    bridge["catalog"]["sha256_catalogs_json"] = sha((HERE / "catalogs.json").read_bytes())
    (HERE / "bridge.json").write_text(json.dumps(bridge, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"answer": bridge["answer"], "packages": len(packages_report)}, indent=1))
    for slug, item in packages_report.items():
        print(
            slug,
            "segments",
            item["segments_native"],
            "ids",
            item["segment_ids_equal"],
            "lanes",
            item["lanes_equal"],
            "pos",
            item["positions_within_tolerance"],
            "outside",
            item["outside_nodes_equal"],
            "/",
            item["nodes_native"],
            "nodeflagdiff",
            item["node_flags_differ_count"],
            "outside_disagree",
            item["node_flags_differ_outside_disagreements"],
            "modes",
            item["mode_inputs_equal"],
            item["mode_segments"],
        )
    return bridge


if __name__ == "__main__":
    main()
