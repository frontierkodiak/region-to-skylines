"""Offline bridge: derive the model's inputs from saved `.crp` export bytes.

The model was fitted on native `networks.json` snapshots. This module asks the
question that decides whether it is an export-scoped model or only a
native-snapshot one: can every field the model uses be read out of the saved
package bytes?

It reads each frozen package read-only, never rebuilds, recaptures or repairs
one, and compares the result field by field with the native snapshot of the
same opening. Two things are reused rather than re-derived, and both are
hash-bound to the snapshots and cross-validated leave-one-package-out:

* a prefab -> ordered lane template catalog (lane type, vehicle category,
  direction bits), because the save names the prefab but the lane definitions
  live in the game's prefab asset;
* an observed integer -> flag-name catalog for nodes and segments, because the
  save stores flag bitfields and the snapshot names them.

Fields the game recomputes at load (`OneWayIn`/`OneWayOut` on nodes) are
reported as recomputed, not silently rewritten.

Run:  .venv/bin/python capability-evidence/rail-query-model-v1/bridge.py
"""

from __future__ import annotations

import argparse
import collections
import datetime
import gzip
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAP_FACTORY = HERE.parents[1]
CAPABILITY = HERE.parent
sys.path.insert(0, str(MAP_FACTORY))

import netcodec as nc  # noqa: E402
import network_writer as nw  # noqa: E402
from crp import read_package  # noqa: E402

import model  # noqa: E402
import topology  # noqa: E402

POSITION_TOLERANCE = 0.01
MODEL_FIELDS = (
    "segment_present",
    "start",
    "end",
    "prefab",
    "position",
    "lanes",
    "invert",
    "node_outside",
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    return digest(Path(path).read_bytes())


def load_json(path):
    path = Path(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf8") as stream:
            return json.load(stream)
    return json.loads(path.read_text())


def tokens(value):
    return frozenset(part for part in (value or "").split(", ") if part)


def name_set(value):
    """A flag set whether the record stores a string or an already-split set."""
    if isinstance(value, (set, frozenset)):
        return set(value)
    return set(tokens(value))


def crp_networks(locator):
    """Read the NetManager section of one saved package. Read-only."""
    raw = Path(locator).read_bytes()
    _, assets = read_package(raw)
    payload = next(asset["payload"] for asset in assets if asset["kind"] == 52)
    net = nc.NetSection(payload, nw.section_start(payload, "NetManager"))
    if net.end is None:
        raise ValueError("map network section is not a current-version map section")
    return raw, net


def crp_records(net):
    names = net.prefabs.names
    nodes = {
        node_id: {
            "flags": int(net.node_flags[node_id - 1]),
            "flags2": int(net.node_flags2[node_id - 1]),
            "position": tuple(float(v) for v in record["position"]),
        }
        for node_id, record in net.nodes.items()
    }
    segments = {
        segment_id: {
            "start": int(record["start_node"]),
            "end": int(record["end_node"]),
            "flags": int(net.segment_flags[segment_id - 1]),
            "flags2": int(net.segment_flags2[segment_id - 1]),
            "prefab": names[net.segment_prefab[segment_id]],
        }
        for segment_id, record in net.segments.items()
    }
    return nodes, segments


def template_of(lanes):
    return tuple(
        (
            lane["index"],
            lane["type"],
            lane["vehicle"],
            lane["category"],
            int(lane["direction_bits"]),
        )
        for lane in sorted(lanes, key=lambda lane: lane["index"])
    )


def prefab_catalog(snapshots):
    templates = collections.defaultdict(collections.Counter)
    for networks in snapshots:
        for segment in networks["segments"]:
            templates[segment["prefab"]][template_of(segment["lanes"])] += 1
    return {name: dict(counter) for name, counter in templates.items()}


def single_template(catalog, prefab):
    templates = catalog.get(prefab)
    if not templates or len(templates) != 1:
        return None
    return next(iter(templates))


def decode_lanes(template):
    return [
        {
            "index": int(index),
            "forward": bool(bits & 1),
            "backward": bool(bits & 2),
            "lane_type": lane_type,
            "vehicle": sorted(tokens(vehicle)),
            "category": category,
        }
        for index, lane_type, vehicle, category, bits in template
    ]


def flag_catalog(pairs):
    """integer -> most common name tuple, plus every observed conflict."""
    table = collections.defaultdict(collections.Counter)
    for value, names in pairs:
        table[value][names] += 1
    names = {
        value: sorted(counter.most_common(1)[0][0]) for value, counter in table.items()
    }
    conflicts = {
        value: {", ".join(key): count for key, count in counter.most_common()}
        for value, counter in table.items()
        if len(counter) > 1
    }
    return names, conflicts


def catalogs_for(openings, packages, snapshot_subset=None):
    """Build the two catalogs from the given openings' native snapshots."""
    node_pairs, segment_pairs = [], []
    snapshots = []
    for entry in openings:
        if snapshot_subset is not None and entry["opening"] not in snapshot_subset:
            continue
        raw = CAPABILITY / entry["raw"]
        networks = load_json(raw / "networks.json.gz")
        snapshots.append(networks)
        _, net = crp_networks(packages["packages"][entry["package"]]["locator"])
        nodes, segments = crp_records(net)
        for segment in networks["segments"]:
            for key, flag_key in (("start", "start_flags"), ("end", "end_flags")):
                node_pairs.append(
                    (
                        nodes[segment[key]]["flags"],
                        tuple(sorted(tokens(segment[flag_key]))),
                    )
                )
            reference = segments[segment["id"]]
            segment_pairs.append(
                (reference["flags"], tuple(sorted(tokens(segment["flags"]))))
            )
    node_names, node_conflicts = flag_catalog(node_pairs)
    segment_names, segment_conflicts = flag_catalog(segment_pairs)
    return {
        "prefab_lanes": prefab_catalog(snapshots),
        "node_names": node_names,
        "node_name_conflicts": node_conflicts,
        "segment_names": segment_names,
        "segment_name_conflicts": segment_conflicts,
        "outside_values": {
            value for value, names in node_names.items() if "Outside" in names
        },
    }


def bridge_package(net, catalogs):
    """Model-ready topology built from export bytes plus the observed catalogs."""
    nodes, segments = crp_records(net)
    missing = set()
    built_nodes = {}
    for node_id, record in nodes.items():
        names = catalogs["node_names"].get(record["flags"])
        if names is None:
            missing.add(f"node_flag_value:{record['flags']}")
            names = []
        built_nodes[node_id] = {
            "flags": set(names)
            | ({"Outside"} if record["flags"] in catalogs["outside_values"] else set()),
            "position": record["position"],
        }
    built_segments = {}
    for segment_id, record in segments.items():
        template = single_template(catalogs["prefab_lanes"], record["prefab"])
        if template is None:
            missing.add(f"prefab:{record['prefab']}")
            continue
        names = catalogs["segment_names"].get(record["flags"])
        if names is None:
            missing.add(f"segment_flag_value:{record['flags']}")
            names = []
        if record["start"] not in nodes or record["end"] not in nodes:
            missing.add(f"node_record:{segment_id}")
            continue
        built_segments[segment_id] = {
            "id": segment_id,
            "start": record["start"],
            "end": record["end"],
            "a": nodes[record["start"]]["position"],
            "b": nodes[record["end"]]["position"],
            "flags": set(names),
            "prefab": record["prefab"],
            "lanes": decode_lanes(template),
        }
    return {
        "name": "bridge",
        "segments": built_segments,
        "nodes": built_nodes,
        "missing": sorted(missing),
    }


def compare(built, native, train_only=False):
    """Field-by-field agreement between export-derived and native records.

    `train_only` restricts the comparison to the records the model can actually
    use: segments with a Train-capable lane and the nodes incident to them.
    """
    counts = collections.Counter()
    failures = collections.defaultdict(list)
    train_segments = {
        segment_id
        for segment_id, segment in native["segments"].items()
        if topology.train_lanes(segment)
    }
    train_nodes = set()
    for segment_id in train_segments:
        segment = native["segments"][segment_id]
        train_nodes.update((segment["start"], segment["end"]))

    def wanted(segment_id):
        return not train_only or segment_id in train_segments

    def check(field, ok, subject=None):
        counts[field + ":checked"] += 1
        if ok:
            counts[field + ":agree"] += 1
        else:
            failures[field].append(subject)

    for segment_id, segment in built["segments"].items():
        if not wanted(segment_id):
            continue
        reference = native["segments"].get(segment_id)
        check("segment_present", reference is not None, segment_id)
        if reference is None:
            continue
        check("start", segment["start"] == reference["start"], segment_id)
        check("end", segment["end"] == reference["end"], segment_id)
        check("prefab", segment["prefab"] == reference["prefab"], segment_id)
        check(
            "position",
            math.dist(segment["a"], reference["a"]) <= POSITION_TOLERANCE
            and math.dist(segment["b"], reference["b"]) <= POSITION_TOLERANCE,
            segment_id,
        )
        check(
            "lanes",
            [
                {
                    "index": lane["index"],
                    "forward": lane["forward"],
                    "backward": lane["backward"],
                    "lane_type": lane["lane_type"],
                    "vehicle": lane["vehicle"],
                    "category": lane["category"],
                }
                for lane in segment["lanes"]
            ]
            == [
                {
                    "index": lane["index"],
                    "forward": lane["forward"],
                    "backward": lane["backward"],
                    "lane_type": lane["lane_type"],
                    "vehicle": lane["vehicle"],
                    "category": lane["category"],
                }
                for lane in sorted(reference["lanes"], key=lambda lane: lane["index"])
            ],
            segment_id,
        )
        check(
            "invert",
            ("Invert" in segment["flags"])
            == ("Invert" in name_set(reference["flags"])),
            segment_id,
        )
    for segment_id in native["segments"]:
        if wanted(segment_id) and segment_id not in built["segments"]:
            check("segment_present", False, segment_id)
    for node_id, node in built["nodes"].items():
        if train_only and node_id not in train_nodes:
            continue
        reference = native["nodes"].get(node_id)
        if reference is None:
            continue
        check(
            "node_outside",
            ("Outside" in node["flags"]) == ("Outside" in name_set(reference["flags"])),
            node_id,
        )
    return counts, {key: value for key, value in failures.items()}


def selected_requests(plan):
    return [
        request
        for request in plan["plan"]["requests"]
        if not request["diagnostic"] and request["position_kind"] == "boundary"
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    openings = json.loads((HERE / "openings.json").read_text())
    packages = json.loads((HERE / "packages.json").read_text())["packages"]
    entries = [
        entry
        for entry in openings["openings"]
        if entry["package"] in openings["bridge"]["packages"]
    ]

    for key, entry in packages.items():
        if file_digest(entry["locator"]) != entry["sha256"]:
            raise SystemExit(f"package {key}: bytes differ from the frozen SHA-256")

    catalogs = catalogs_for(entries, {"packages": packages})
    ambiguous = {
        name: values
        for name, values in catalogs["prefab_lanes"].items()
        if len(values) > 1
    }
    if ambiguous:
        raise SystemExit(
            f"prefab lane templates are not stable across packages: {ambiguous}"
        )

    report = {
        "schema": 1,
        "built_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "scope": "read the nine unchanged cohort packages and the two stock controls; never rebuild, recapture or repair",
        "packages": {},
        "catalogs": {
            "prefabs": len(catalogs["prefab_lanes"]),
            "node_flag_values": len(catalogs["node_names"]),
            "segment_flag_values": len(catalogs["segment_names"]),
            "outside_values": sorted(catalogs["outside_values"]),
            "node_name_conflicts": {
                str(k): v for k, v in catalogs["node_name_conflicts"].items()
            },
            "segment_name_conflicts": {
                str(k): v for k, v in catalogs["segment_name_conflicts"].items()
            },
        },
    }
    totals = collections.Counter()
    agreement = {"queries": 0, "identical": 0, "by_package": {}}
    disagreements = {}
    for entry in entries:
        name = entry["package"]
        raw, net = crp_networks(packages[name]["locator"])
        if digest(raw) != packages[name]["sha256"]:
            raise SystemExit(f"{name}: package changed while reading")
        raw_dir = CAPABILITY / entry["raw"]
        networks = load_json(raw_dir / "networks.json.gz")
        native = topology.from_native(networks, entry["opening"])
        built = bridge_package(net, catalogs)
        counts, failures = compare(built, native, train_only=True)
        totals.update(counts)
        requests = selected_requests(load_json(raw_dir / "query-freeze.json.gz"))
        same = 0
        for request in requests:
            left = model.predict(native, request, model.FITTED_RULE)
            right = model.predict(built, request, model.FITTED_RULE)
            if left == right:
                same += 1
            else:
                disagreements.setdefault(name, []).append(
                    {"request": request, "native": left, "bridge": right}
                )
        agreement["queries"] += len(requests)
        agreement["identical"] += same
        agreement["by_package"][name] = {"queries": len(requests), "identical": same}
        report["packages"][name] = {
            "sha256": packages[name]["sha256"],
            "netmanager_version": net.version,
            "networks_sha256": file_digest(raw_dir / "networks.json.gz"),
            "query_freeze_sha256": file_digest(raw_dir / "query-freeze.json.gz"),
            "missing": built["missing"],
            "field_checks": dict(counts),
            "field_failures": failures,
            "all_records": dict(compare(built, native, train_only=False)[0]),
        }

    # Leave-one-package-out: rebuild both catalogs from the other ten packages,
    # decode this package's bytes, and compare the model-used fields.
    loo = {}
    for entry in entries:
        name = entry["package"]
        held = catalogs_for(
            entries,
            {"packages": packages},
            snapshot_subset={
                other["opening"]
                for other in entries
                if other["opening"] != entry["opening"]
            },
        )
        raw, net = crp_networks(packages[name]["locator"])
        built = bridge_package(net, held)
        raw_dir = CAPABILITY / entry["raw"]
        native = topology.from_native(
            load_json(raw_dir / "networks.json.gz"), entry["opening"]
        )
        counts, failures = compare(built, native, train_only=True)
        lane_checked = sum(
            1
            for segment in native["segments"].values()
            if topology.train_lanes(segment)
        )
        loo[name] = {
            "unseen_prefabs": sorted(
                {
                    value.split(":", 1)[1]
                    for value in built["missing"]
                    if value.startswith("prefab:")
                }
            ),
            "lane_checked": lane_checked,
            "lane_agree": counts["lanes:agree"],
            "outside_checked": counts["node_outside:checked"],
            "outside_agree": counts["node_outside:agree"],
            "invert_agree": counts["invert:agree"],
            "invert_checked": counts["invert:checked"],
            "field_failures": failures,
        }

    fields = {}
    for field in MODEL_FIELDS:
        checked = totals[field + ":checked"]
        agree = totals[field + ":agree"]
        fields[field] = {
            "checked": checked,
            "agree": agree,
            "rate": (agree / checked) if checked else None,
        }
    loo_ok = all(
        row["lane_agree"] == row["lane_checked"]
        and row["outside_agree"] == row["outside_checked"]
        and row["invert_agree"] == row["invert_checked"]
        for row in loo.values()
    )
    established = (
        all(fields[field]["rate"] == 1.0 for field in MODEL_FIELDS)
        and agreement["queries"] == agreement["identical"]
        and loo_ok
    )
    report.update(
        {
            "fields": fields,
            "totals": dict(totals),
            "prediction_agreement": agreement,
            "prediction_disagreements": disagreements,
            "leave_one_package_out": loo,
            "status": "bridge_established" if established else "native_snapshot_only",
            "status_note": (
                "Every model-used field is readable from the saved export: segment identity, endpoints, prefab, "
                "node position, lane type/vehicle/category/direction and the Outside and Invert predicates. The "
                "prefab lane template and the flag-name tables are hash-bound observed catalogs rather than export "
                "bytes on their own, and both are cross-validated leave-one-package-out. Node OneWayIn/OneWayOut "
                "names are recomputed by the game at load and are not claimed as export bytes."
            ),
        }
    )
    if args.check:
        frozen = json.loads((HERE / "bridge.json").read_text())
        for key in (
            "fields",
            "prediction_agreement",
            "leave_one_package_out",
            "status",
        ):
            if frozen[key] != report[key]:
                raise SystemExit(f"bridge report is not reproducible: {key}")
        print(
            json.dumps(
                {
                    "checked": True,
                    "status": report["status"],
                    "bridge_sha256": file_digest(HERE / "bridge.json"),
                }
            )
        )
        return
    (HERE / "catalogs.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "prefab_lanes": {
                    prefab: [
                        {
                            "observations": count,
                            "lanes": [
                                {
                                    "index": index,
                                    "lane_type": lane_type,
                                    "vehicle": vehicle,
                                    "category": category,
                                    "direction_bits": bits,
                                }
                                for index, lane_type, vehicle, category, bits in template
                            ],
                        }
                        for template, count in templates.items()
                    ]
                    for prefab, templates in catalogs["prefab_lanes"].items()
                },
                "node_names": {str(k): v for k, v in catalogs["node_names"].items()},
                "segment_names": {
                    str(k): v for k, v in catalogs["segment_names"].items()
                },
                "outside_values": sorted(catalogs["outside_values"]),
                "node_name_conflicts": {
                    str(k): v for k, v in catalogs["node_name_conflicts"].items()
                },
                "segment_name_conflicts": {
                    str(k): v for k, v in catalogs["segment_name_conflicts"].items()
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    (HERE / "bridge.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "fields": {key: value["rate"] for key, value in fields.items()},
                "prediction_agreement": agreement["queries"] - agreement["identical"],
                "bridge_sha256": file_digest(HERE / "bridge.json"),
            }
        )
    )


if __name__ == "__main__":
    main()
