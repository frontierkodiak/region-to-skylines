"""Export matched hydraulic diagnostics without changing the default water policy.

First replay the frozen resource plan and require the exact input CRP. Then
change only WaterSimulation and its MapMetaData.assetRef. Other managers,
resource listing values, camera, network and preview assets remain byte-exact.
"""

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import tempfile

import numpy as np

from crp import (
    N,
    decode_u16,
    patch_metadata,
    read_package,
    water_payload,
    write_map,
    write_package,
)
from paint import load_plan
from resources import TREE_NAMES
from soak import (
    geographic_river_probes,
    mapped_water_reference,
    panel_expectations,
    prepared_geometry,
    probes_for,
    world_references,
)
from template import manager_tag

ROOT = Path(__file__).resolve().parent
MODES = ("short-output-off", "sea-only", "portal-intake-original")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def decode_water(simulation):
    """Decode the actual native initial grid, source count/table and trailer."""
    tag = manager_tag("WaterSimulation")
    if simulation.count(tag) != 1:
        raise ValueError("WaterSimulation tag is not unique")
    start = simulation.index(tag)
    offset = start + len(tag)
    depth, offset = decode_u16(simulation, N, offset)
    wet = depth.reshape(1081, 1081) > 0
    vx, vz = wet.copy(), wet.copy()
    vx[:, :-1] |= wet[:, 1:]
    vz[:-1, :] |= wet[1:, :]
    velocities = []
    for count in (wet.sum(), vx.sum(), vz.sum()):
        values, offset = decode_u16(simulation, int(count), offset)
        if np.any(values):
            raise ValueError("Diagnostic input must have zero initial velocity")
        velocities.append(
            {"elements": int(count), "sha256": digest(values.astype("<u2").tobytes())}
        )
    count = struct.unpack_from(">H", simulation, offset)[0]
    offset += 2
    sources = []
    for index in range(count):
        values = struct.unpack_from(">6fHH", simulation, offset)
        offset += 28
        rates = [
            int.from_bytes(simulation[offset + i : offset + i + 3], "big")
            for i in range(0, 15, 3)
        ]
        offset += 15
        if (
            values[:3] != values[3:6]
            or values[6] != 1
            or rates[0]
            or rates[1]
            or rates[4]
        ):
            raise ValueError("Unsupported initial water source encoding")
        sources.append(
            {
                "index": index,
                "position": list(values[:3]),
                "type": values[6],
                "target_fixed": values[7],
                "intake_rate": rates[2],
                "output_rate": rates[3],
            }
        )
    unknown, sea, flag_a, flag_b, frame = struct.unpack_from(
        ">HfbbI", simulation, offset
    )
    offset += 12
    if unknown or flag_a or flag_b:
        raise ValueError("Unsupported initial water trailer")
    # The native writer preserves the final two manager bytes verbatim.
    tail = simulation[offset : offset + 2]
    if len(tail) != 2:
        raise ValueError("Truncated WaterSimulation manager tail")
    return {
        "start": start,
        "end": offset + 2,
        "tag": tag,
        "tail": tail,
        "depth": depth,
        "sources": sources,
        "sea_level_m": sea,
        "frame": frame,
        "velocities": velocities,
    }


def encoded_sources(decoded):
    return [
        {
            "position": s["position"],
            "target": s["target_fixed"] / 64,
            "capacity": s["intake_rate"] / 65535,
            "output_capacity": s["output_rate"] / 65535,
        }
        for s in decoded["sources"]
    ]


def bind_sources(decoded, hydro):
    if len(decoded["sources"]) != len(hydro["sources"]):
        raise ValueError("Source count differs between CRP and hydrology")
    for actual, expected in zip(decoded["sources"], hydro["sources"]):
        native = struct.unpack(">3f", struct.pack(">3f", *expected["position"]))
        if actual["position"][::2] != list(native)[::2]:
            raise ValueError("Source x/z positions differ between CRP and hydrology")
        rates = [
            math.floor(expected[key] * multiplier + 0.5)
            for key, multiplier in [("target", 64), ("capacity", 65535)]
        ]
        rates.append(
            math.floor(
                expected.get("output_capacity", expected["capacity"]) * 65535 + 0.5
            )
        )
        if rates != [
            actual["target_fixed"],
            actual["intake_rate"],
            actual["output_rate"],
        ]:
            raise ValueError("Source target/rates differ between CRP and hydrology")


def transform(source, hydro, terrain, mode):
    """Return a package with exactly one diagnostic factor changed, plus receipts."""
    if mode not in MODES:
        raise ValueError(f"Unknown diagnostic mode: {mode}")
    package, assets = read_package(source)
    original_assets = [(a["name"], a["kind"], digest(a["payload"])) for a in assets]
    simulation = next(a for a in assets if a["kind"] == 52)
    original = simulation["payload"]
    water = decode_water(original)
    bind_sources(water, hydro)
    controls = encoded_sources(water)
    before_controls = copy.deepcopy(water["sources"])
    original_chunk = (
        water["tag"]
        + water_payload(water["depth"], controls, water["frame"], water["sea_level_m"])
        + water["tail"]
    )
    if original_chunk != original[water["start"] : water["end"]]:
        raise ValueError("Native initial-water decoding does not round-trip exactly")
    depth = water["depth"].copy()
    changed_indices = []
    restored_intakes = {}
    new_hydro = copy.deepcopy(hydro)
    if mode == "short-output-off":
        for i, (actual, expected) in enumerate(zip(water["sources"], hydro["sources"])):
            if expected.get("short_surface_river") and actual["output_rate"] > 0:
                controls[i]["output_capacity"] = 0
                new_hydro["sources"][i]["output_capacity"] = 0
                changed_indices.append(i)
    elif mode == "portal-intake-original":
        for i, (actual, expected) in enumerate(zip(water["sources"], hydro["sources"])):
            if (
                expected.get("short_surface_river")
                and expected.get("underground_portal") == "surface_inlet_to_tunnel"
                and actual["output_rate"] == 0
            ):
                footprint = expected.get("short_source_footprint")
                original_rate = (
                    footprint.get("intake_rate_before")
                    if isinstance(footprint, dict)
                    else None
                )
                if type(original_rate) is not int or not 1 <= original_rate <= 65535:
                    raise ValueError(
                        "Missing/invalid frozen original portal intake rate"
                    )
                if original_rate != actual["intake_rate"]:
                    controls[i]["capacity"] = original_rate / 65535
                    new_hydro["sources"][i]["capacity"] = original_rate / 65535
                    restored_intakes[i] = original_rate
    else:
        sea = hydro["sea_level_m"]
        if not math.isfinite(sea):
            raise ValueError("Nonfinite source sea level")
        depth = (
            np.floor(np.maximum(0, sea - terrain.astype(float) / 64) * 64 + 0.5)
            .clip(0, 65535)
            .astype("<u2")
            .ravel()
        )
    replacement = (
        water["tag"]
        + water_payload(depth, controls, water["frame"], water["sea_level_m"])
        + water["tail"]
    )
    updated = original[: water["start"]] + replacement + original[water["end"] :]
    simulation["payload"] = updated
    old_ref, new_ref = (
        hashlib.md5(original).hexdigest(),
        hashlib.md5(updated).hexdigest(),
    )
    for asset in assets:
        if asset["kind"] == 100:
            before = asset["payload"]
            asset["payload"] = patch_metadata(before, new_ref)
            if patch_metadata(asset["payload"], old_ref) != before:
                raise ValueError("Metadata changed beyond the simulation assetRef")
    result = write_package(package, assets)
    _, verified_assets = read_package(result)
    verified_sim = next(a["payload"] for a in verified_assets if a["kind"] == 52)
    after = decode_water(verified_sim)
    if (
        original[: water["start"]] != verified_sim[: after["start"]]
        or original[water["end"] :] != verified_sim[after["end"] :]
    ):
        raise ValueError("Unexpected changes outside WaterSimulation")
    differences = []
    for before, actual in zip(before_controls, after["sources"]):
        difference = {
            k: {"before": before[k], "after": actual[k]}
            for k in before
            if before[k] != actual[k]
        }
        if difference:
            output_change = (
                set(difference) == {"output_rate"}
                and actual["index"] in changed_indices
                and actual["output_rate"] == 0
            )
            intake_change = (
                set(difference) == {"intake_rate"}
                and restored_intakes.get(actual["index"]) == actual["intake_rate"]
            )
            if not (output_change or intake_change):
                raise ValueError("Unexpected encoded water-control difference")
            differences.append({"index": actual["index"], **difference})
    if len(after["sources"]) != len(before_controls) or len(differences) != len(
        changed_indices
    ) + len(restored_intakes):
        raise ValueError("Unexpected encoded source count/differences")
    if not np.array_equal(after["depth"], depth):
        raise ValueError("Encoded diagnostic water differs from requested grid")
    receipt = {
        "mode": mode,
        "source_crp_sha256": digest(source),
        "crp_sha256": digest(result),
        "source_count": len(before_controls),
        "changed_output_indices": changed_indices,
        "changed_intake_indices": list(restored_intakes),
        "frozen_original_intake_rates": restored_intakes,
        "encoded_source_changes": differences,
        "assets": [
            {
                "name": name,
                "kind": kind,
                "before_sha256": before,
                "after_sha256": digest(actual["payload"]),
                "unchanged": before == digest(actual["payload"]),
            }
            for (name, kind, before), actual in zip(original_assets, verified_assets)
        ],
        "source_controls": before_controls,
        "diagnostic_controls": after["sources"],
        "control_classification": [
            {
                "index": i,
                **{
                    key: source.get(key)
                    for key in [
                        "name",
                        "class",
                        "role",
                        "short_surface_river",
                        "underground_portal",
                    ]
                },
            }
            for i, source in enumerate(hydro["sources"])
        ],
        "initial_water_before_sha256": digest(water["depth"].astype("<u2").tobytes()),
        "initial_water_after_sha256": digest(depth.astype("<u2").tobytes()),
        "initial_water_changed_cells": int(np.count_nonzero(depth != water["depth"])),
        "positive_output_controls_before": sum(
            s["output_rate"] > 0 for s in before_controls
        ),
        "positive_output_controls_after": sum(
            s["output_rate"] > 0 for s in after["sources"]
        ),
        "unchanged_simulation_prefix_sha256": digest(original[: water["start"]]),
        "unchanged_simulation_suffix_sha256": digest(original[water["end"] :]),
        "source_velocity_arrays": water["velocities"],
        "diagnostic_velocity_arrays": after["velocities"],
        "sea_level_m": after["sea_level_m"],
        "simulation_frame": after["frame"],
        "preserved": [
            "terrain",
            "network",
            "camera",
            "resources and listing values",
            "previews",
            "source count/positions/targets",
        ]
        + (["intake rates"] if mode != "portal-intake-original" else [])
        + (["bounded output rates"] if mode != "short-output-off" else []),
        "limitations": [
            "matched hydraulic diagnostic, NOT qualification",
            "resource water/listing/preview bytes intentionally frozen, not recomputed for sea-only initial water",
            "initial velocity array lengths follow wet-grid topology; values remain zero",
        ],
    }
    return result, new_hydro, depth, receipt


def export(source, output, modes=MODES):
    source, output = Path(source), Path(output)
    if output.exists():
        raise ValueError("Use a fresh diagnostic output directory")
    if (
        not modes
        or any(mode not in MODES for mode in modes)
        or len(set(modes)) != len(modes)
    ):
        raise ValueError("Select distinct supported diagnostic modes")
    generation = read_json(source / "generation.json")
    declared_inputs = generation.get("source", {}).get("inputs_sha256", {})
    for name in ["terrain.u16", "water.u16", "hydrology.json"]:
        if (
            name in declared_inputs
            and digest((source / name).read_bytes()) != declared_inputs[name]
        ):
            raise ValueError(
                f"Diagnostic source input changed since generation: {name}"
            )
    geometry_raw, geometry_binding = prepared_geometry(source, generation)
    if geometry_raw is None or geometry_binding["binding"] != "generation":
        raise ValueError("Diagnostics require generation-bound geometry")
    plan = source / "plan.npz"
    if generation.get("resource_plan") != {
        "file": "plan.npz",
        "sha256": digest(plan.read_bytes()),
    }:
        raise ValueError("Frozen resource plan binding missing/mismatched")
    hydro = read_json(source / "hydrology.json")
    original_path = source / (hydro["map_id"] + ".crp")
    original = original_path.read_bytes()
    if digest(original) != generation["package"]["sha256"]:
        raise ValueError("Source CRP changed since generation")
    terrain = np.fromfile(source / "terrain.u16", dtype="<u2")
    if terrain.size != N:
        raise ValueError("Expected native terrain grid")
    # Replay resource encoding before touching either independent factor.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="water-diagnostic-replay-", dir=output.parent
    ) as temporary:
        replay = Path(temporary) / original_path.name
        write_map(
            ROOT / "templates/native-corridors.crp",
            ROOT / "templates/native-corridors.json",
            source / "terrain.u16",
            source / "water.u16",
            source / "hydrology.json",
            replay,
            resources=(load_plan(plan), TREE_NAMES),
        )
        if replay.read_bytes() != original:
            raise ValueError(
                "Frozen resource-plan replay does not reproduce exact source CRP"
            )
    water = decode_water(
        next(a["payload"] for a in read_package(original)[1] if a["kind"] == 52)
    )
    if water["depth"].astype("<u2").tobytes() != (source / "water.u16").read_bytes():
        raise ValueError("Source initial grid differs from actual CRP")
    outputs = []
    for mode in modes:
        variant, variant_hydro, depth, receipt = transform(
            original, hydro, terrain, mode
        )
        folder = output / mode / json.loads(geometry_raw)["sq"]["slug"]
        folder.mkdir(parents=True)
        for filename in [
            "terrain.u16",
            "plan.npz",
            "resources.json",
            "resources.png",
            "landmarks.json",
        ]:
            if (source / filename).is_file():
                shutil.copyfile(source / filename, folder / filename)
        (folder / "geometry.json").write_bytes(geometry_raw)
        (folder / "water.u16").write_bytes(depth.astype("<u2").tobytes())
        (folder / "hydrology.json").write_text(
            json.dumps(variant_hydro, indent=2) + "\n"
        )
        crp = folder / original_path.name
        crp.write_bytes(variant)
        receipt.update(
            geometry=geometry_binding,
            resource_plan_sha256=digest(plan.read_bytes()),
            resource_plan_replay_exact=True,
            source_generation_sha256=digest((source / "generation.json").read_bytes()),
            encoder_sources_sha256={
                name: digest((ROOT / name).read_bytes())
                for name in [
                    "water_diagnostics.py",
                    "crp.py",
                    "paint.py",
                    "resources.py",
                    "templates/native-corridors.crp",
                    "templates/native-corridors.json",
                ]
            },
            input_hashes={
                f: digest((source / f).read_bytes())
                for f in [
                    "terrain.u16",
                    "water.u16",
                    "hydrology.json",
                    "geometry.json",
                    "plan.npz",
                ]
            },
        )
        (folder / "diagnostic.json").write_text(json.dumps(receipt, indent=2) + "\n")
        bound = {
            "package": {
                "output": crp.name,
                "sha256": digest(variant),
                "bytes": len(variant),
            },
            "qualification": "matched hydraulic diagnostic; NOT candidate acceptance",
            "in_game_verified": False,
            "prefill": mode != "sea-only",
            "diagnostic": mode,
            "source": {
                "package_sha256": digest(original),
                "inputs_sha256": {"geometry.json": geometry_binding["sha256"]},
            },
            "resource_plan": {"file": "plan.npz", "sha256": digest(plan.read_bytes())},
            "resources": {
                "prepared_geometry_sha256": geometry_binding["sha256"],
                "diagnostic_frozen_listing_values": True,
            },
        }
        (folder / "generation.json").write_text(json.dumps(bound, indent=2) + "\n")
        data = probes_for(
            variant_hydro, read_json(ROOT / "templates/native-corridors.json")
        )
        data["new_game_panel"] = panel_expectations(crp)
        geographic_river_probes(data, json.loads(geometry_raw))
        mapped_water_reference(data, json.loads(geometry_raw), folder)
        data["mapped_water_provenance"]["source_geometry"] = geometry_binding
        world_references(
            data,
            json.loads(geometry_raw),
            read_json(source / "landmarks.json")
            if (source / "landmarks.json").is_file()
            else None,
        )
        (folder / "probes.json").write_text(json.dumps(data, indent=2) + "\n")
        outputs.append(
            {
                "mode": mode,
                "directory": str(folder.relative_to(output)),
                "sha256": digest(variant),
                "water_sha256": receipt["initial_water_after_sha256"],
                "changed_controls": len(receipt["changed_output_indices"])
                + len(receipt["changed_intake_indices"]),
                "changed_intake_controls": len(receipt["changed_intake_indices"]),
                "changed_output_controls": len(receipt["changed_output_indices"]),
            }
        )
    result = {
        "source_crp_sha256": digest(original),
        "resource_replay_exact": True,
        "variants": outputs,
        "native_staging": "Use exact exported CRP + probes.json directly; sea-only intentionally cannot pass normal resource-repainting stage_prepared replay",
    }
    (output / "diagnostics.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--mode",
        choices=MODES,
        action="append",
        help="export only selected mode(s); default: all",
    )
    args = parser.parse_args()
    print(json.dumps(export(args.source, args.output, args.mode or MODES), indent=2))
