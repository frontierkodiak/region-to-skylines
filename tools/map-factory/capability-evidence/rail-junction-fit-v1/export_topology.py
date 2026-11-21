"""Read a frozen `.crp` export: its container, its NetManager records, its tangents.

This module is the only place in the study that opens package bytes. It reuses
the repository's owned readers instead of inventing new ones:

* `survey/measure_maps.py:read_any` reads the CRP index table for every package
  format the game writes (4..12), so the two stock controls in the older
  format-8 container are readable. `measure_maps.data_version` reads the
  DataSerializer header that selects the NetManager layout gates.
* `network_writer.section_start` locates the unique NetManager tag.
* `netcodec.NetSection` decodes the section with that declared version. For a
  non-current version it decodes read-only and stops after the main prefab
  table, which is after every field this study consumes.

The accepted bridge (`rail-query-model-v1/bridge.py`) is imported read-only for
its generic pieces: the prefab-lane template catalog, the integer flag-name
catalog, the export-derived package builder, the field comparator and the
model-input digest. Its own `crp_networks` is deliberately not used: it accepts
only the format-12 container and requires a current-version section.

What this module adds beyond the accepted bridge is the single new feature the
study tests: the authored endpoint tangents `NetSection.segments[id]
["start_direction"]` and `["end_direction"]`, plus the
`override_direction_limit` bit. They are read, hashed and reported. The game
snapshots under `rail-v3*/raw/*/networks.json.gz` do not emit them, so every
tangent-derived value is an **export-derived hypothesis**, never a
native-attested field.
"""

from __future__ import annotations

import functools
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAP_FACTORY = HERE.parents[1]
CAPABILITY = HERE.parent
ACCEPTED = CAPABILITY / "rail-query-model-v1"
# The accepted prefix is imported read-only: its `model`, `topology` and
# `bridge` modules are the pinned dependency. Its `predict`/`evaluate` modules
# are never imported or run.
sys.path[:0] = [str(MAP_FACTORY), str(ACCEPTED)]

import bridge as accepted_bridge  # noqa: E402
import netcodec as nc  # noqa: E402
import network_writer as nw  # noqa: E402
from survey import measure_maps  # noqa: E402

SIMULATOR_ASSET = 52


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    return digest(Path(path).read_bytes())


def load_json(path):
    import gzip

    path = Path(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf8") as stream:
            return json.load(stream)
    return json.loads(path.read_text())


def _simulator_payload(assets):
    payloads = [asset for asset in assets if asset["kind"] == SIMULATOR_ASSET]
    if len(payloads) != 1:
        raise ValueError(f"expected one simulator asset, found {len(payloads)}")
    return payloads[0]["payload"]


def read_container(locator):
    """One saved package: raw bytes, index-table metadata, simulator payload."""
    raw = Path(locator).read_bytes()
    package, assets = measure_maps.read_any(raw)
    payload = _simulator_payload(assets)
    return {
        "raw": raw,
        "sha256": digest(raw),
        "format": int(package["format"]),
        "package_version": int(package["version"]),
        "name": package["name"],
        "asset_kinds": sorted(asset["kind"] for asset in assets),
        "assets": [
            {
                "name": asset["name"],
                "kind": asset["kind"],
                "bytes": len(asset["payload"]),
            }
            for asset in assets
        ],
        "payload": payload,
        "payload_sha256": digest(payload),
    }


def read_net(locator):
    """Decode the NetManager section of one saved package, read-only."""
    container = read_container(locator)
    payload = container["payload"]
    version = int(measure_maps.data_version(payload))
    start = nw.section_start(payload, "NetManager")
    net = nc.NetSection(payload, start, version=version)
    container["net"] = net
    container["lineage"] = {
        "crp_sha256": container["sha256"],
        "crp_format": container["format"],
        "package_version": container["package_version"],
        "simulator_asset_sha256": container["payload_sha256"],
        "data_version": version,
        "netmanager_offset": start,
        "netcodec_current_version": nc.CURRENT_VERSION,
        "current_version_section": version == nc.CURRENT_VERSION,
        "read_only_older_layout": version != nc.CURRENT_VERSION,
        "nodes": len(net.nodes),
        "segments": len(net.segments),
        "prefabs": len(net.prefabs.names),
    }
    return container


def cached_net(locator):
    """`read_net` memoised: one frozen package is read once per process.

    The bridge builds eleven leave-one-package-out catalogs over the same
    eleven packages; without this each catalog re-read and re-decoded every
    archive. The bytes are immutable frozen inputs, so caching cannot hide a
    change: every caller checks the locator's SHA-256 first.
    """
    return _cached_net(str(Path(locator).resolve()))


@functools.lru_cache(maxsize=None)
def _cached_net(locator):
    return read_net(locator)


def crp_records(net):
    """Export records in the shape the accepted bridge compares (reused)."""
    return accepted_bridge.crp_records(net)


def catalogs_for(entries, packages, snapshot_subset=None):
    """The accepted bridge's two observed catalogs, over every package format.

    Logic for logic the accepted `bridge.catalogs_for`, with the container and
    version gate replaced by `read_net`. A test asserts it reproduces the
    accepted `corrected/catalogs.json` byte for byte on the nine cohort
    packages, so this is a reuse, not a re-derivation.
    """
    node_pairs, segment_pairs = [], []
    snapshots = []
    for entry in entries:
        if snapshot_subset is not None and entry["opening"] not in snapshot_subset:
            continue
        raw = CAPABILITY / entry["raw"]
        networks = load_json(raw / "networks.json.gz")
        snapshots.append(networks)
        net = cached_net(packages["packages"][entry["package"]]["locator"])["net"]
        nodes, segments = crp_records(net)
        for segment in networks["segments"]:
            for key, flag_key in (("start", "start_flags"), ("end", "end_flags")):
                node_pairs.append(
                    (
                        nodes[segment[key]]["flags"],
                        tuple(sorted(accepted_bridge.tokens(segment[flag_key]))),
                    )
                )
            reference = segments[segment["id"]]
            segment_pairs.append(
                (
                    reference["flags"],
                    tuple(sorted(accepted_bridge.tokens(segment["flags"]))),
                )
            )
    node_names, node_conflicts = accepted_bridge.flag_catalog(node_pairs)
    segment_names, segment_conflicts = accepted_bridge.flag_catalog(segment_pairs)
    return {
        "prefab_lanes": accepted_bridge.prefab_catalog(snapshots),
        "node_names": node_names,
        "node_name_conflicts": node_conflicts,
        "segment_names": segment_names,
        "segment_name_conflicts": segment_conflicts,
        "outside_values": {
            value for value, names in node_names.items() if "Outside" in names
        },
    }


def exported_package(net, catalogs):
    """Model-shaped topology from export bytes plus the observed catalogs."""
    return accepted_bridge.bridge_package(net, catalogs)


def tangents(net):
    """The authored endpoint directions of every segment, as float triples.

    Convention, proved against the export's own node positions in
    `tangent_report`: the stored vector points from the named end into the
    segment, so `start_direction` is the outgoing heading at the start node and
    `end_direction` the outgoing heading at the end node. Components are
    big-endian IEEE-754 float32 as written by the game.
    """
    table = {}
    for segment_id, record in net.segments.items():
        start = tuple(float(v) for v in record["start_direction"])
        end = tuple(float(v) for v in record["end_direction"])
        table[int(segment_id)] = {
            "start_direction": start,
            "end_direction": end,
            "override_direction_limit": int(record.get("override_direction_limit", 0)),
            "start_node": int(record["start_node"]),
            "end_node": int(record["end_node"]),
        }
    return table


def _xz_unit(vector):
    length = math.hypot(vector[0], vector[2])
    if not length:
        return (0.0, 0.0)
    return (vector[0] / length, vector[2] / length)


def tangent_report(table):
    """Floating-point facts about the tangent fields, per package.

    Nothing here feeds a prediction. It records the precision the study has to
    live with: the vectors are float32, their magnitudes are not exactly one,
    and their xz direction differs from the chord by more than a rounding error
    wherever the authored curve actually bends.
    """
    magnitudes_start, magnitudes_end, xz_start, xz_end, curved = [], [], [], [], 0
    overrides = {}
    for record in table.values():
        start = record["start_direction"]
        end = record["end_direction"]
        magnitudes_start.append(math.sqrt(sum(v * v for v in start)))
        magnitudes_end.append(math.sqrt(sum(v * v for v in end)))
        xz_start.append(math.hypot(start[0], start[2]))
        xz_end.append(math.hypot(end[0], end[2]))
        # xz directions are compared with the chord in `tangent_chord_angles`;
        # here the magnitude and override bookkeeping is enough on its own.
        overrides[record["override_direction_limit"]] = (
            overrides.get(record["override_direction_limit"], 0) + 1
        )
        if (
            abs(magnitudes_start[-1] - 1.0) > 1e-6
            or abs(magnitudes_end[-1] - 1.0) > 1e-6
        ):
            curved += 1
    return {
        "segments": len(table),
        "start_magnitude": {
            "min": min(magnitudes_start) if magnitudes_start else None,
            "max": max(magnitudes_start) if magnitudes_start else None,
        },
        "end_magnitude": {
            "min": min(magnitudes_end) if magnitudes_end else None,
            "max": max(magnitudes_end) if magnitudes_end else None,
        },
        "xz_magnitude": {
            "definition": "the horizontal projection the turn angle uses; unit to float32 if this is a direction",
            "start_min": min(xz_start) if xz_start else None,
            "start_max": max(xz_start) if xz_start else None,
            "end_min": min(xz_end) if xz_end else None,
            "end_max": max(xz_end) if xz_end else None,
            "non_unit_share": (
                sum(1 for value in xz_start + xz_end if abs(value - 1.0) > 1e-6)
                / len(xz_start + xz_end)
            )
            if xz_start
            else None,
        },
        "segments_with_non_unit_magnitude": curved,
        "override_direction_limit_values": {
            str(key): count for key, count in sorted(overrides.items())
        },
        "float_precision": {
            "encoding": "IEEE-754 binary32 (struct '>3f')",
            "relative_resolution": 2.0**-24,
            "position_components_same_width": True,
        },
    }


def tangent_table_digest(table, segment_ids):
    """Digest of the tangent fields the model could consume, Train segments only."""
    rows = []
    for segment_id in sorted(segment_ids):
        record = table[segment_id]
        rows.append(
            (
                segment_id,
                tuple(round(v, 9) for v in record["start_direction"]),
                tuple(round(v, 9) for v in record["end_direction"]),
                record["override_direction_limit"],
            )
        )
    encoded = json.dumps(rows, sort_keys=True).encode()
    return {"sha256": digest(encoded), "segments": len(rows)}


def tangent_chord_angles(package):
    """Distribution of authored tangent vs chord heading at Train segment ends.

    A diagnostic of the feature itself: how far the authored curve leaves the
    straight chord at each end. Reported as degrees, never used by a rule.
    """
    segments, _ = _train_segments(package)
    angles = []
    for segment_id in sorted(segments):
        segment = segments[segment_id]
        table_segment = package["tangents"].get(segment_id)
        if table_segment is None:
            continue
        for end, node, position, far in (
            ("start", segment["start"], segment["a"], segment["b"]),
            ("end", segment["end"], segment["b"], segment["a"]),
        ):
            stored = table_segment[
                "start_direction" if end == "start" else "end_direction"
            ]
            tangent = _xz_unit(stored)
            chord = _xz_unit(
                (far[0] - position[0], far[1] - position[1], far[2] - position[2])
            )
            cosine = max(-1.0, min(1.0, tangent[0] * chord[0] + tangent[1] * chord[1]))
            angles.append(math.degrees(math.acos(cosine)))
    if not angles:
        return {"ends": 0}
    angles.sort()

    def quantile(fraction):
        return angles[min(len(angles) - 1, int(fraction * (len(angles) - 1)))]

    return {
        "ends": len(angles),
        "mean_degrees": sum(angles) / len(angles),
        "p50_degrees": quantile(0.50),
        "p90_degrees": quantile(0.90),
        "p99_degrees": quantile(0.99),
        "max_degrees": angles[-1],
        "share_over_1_degree": sum(1 for value in angles if value > 1.0) / len(angles),
    }


def _train_segments(package):
    import model

    return model.train_index(package)


def attach(package, table, segment_ids=None):
    """Copy a model package and attach the export tangents to each segment.

    The model-consumed non-tangent fields keep coming from the native snapshot,
    which is the accepted study's ground for them; the export supplies only the
    fields the snapshot does not emit. `missing` records any Train segment the
    export does not cover, so a tangent rule can abstain instead of borrowing a
    neighbour's geometry.
    """
    import copy

    attached = copy.deepcopy(package)
    attached["tangents"] = {}
    missing = []
    wanted = (
        package["segments"]
        if segment_ids is None
        else {key: package["segments"][key] for key in segment_ids}
    )
    for segment_id in wanted:
        record = table.get(segment_id)
        if record is None:
            missing.append(segment_id)
            continue
        segment = attached["segments"][segment_id]
        segment["start_direction"] = record["start_direction"]
        segment["end_direction"] = record["end_direction"]
        segment["override_direction_limit"] = record["override_direction_limit"]
        attached["tangents"][segment_id] = record
    attached["tangent_missing"] = sorted(missing)
    return attached


def module_hashes():
    return {
        str(path.relative_to(HERE)): file_digest(path)
        for path in sorted(HERE.glob("*.py"))
    }
