"""Provisional surface-intake witness, scored by a fixed native load fixture.

The witness declares one native shore snap at each frozen channel anchor,
not an adaptive search. Power is an explicit controlled auxiliary input. No
first-hour player outcome, region name or historical native label is read.
"""

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

import numpy as np

from real_roads import _tile_of
from start_capabilities import assess, digest, position, sample


@dataclass(frozen=True)
class Load:
    consumer_api: str = "spatial_water_and_sewage"
    settling_has_load: bool = True
    native_units_per_cycle: int = 1000
    cycle_frames: int = 256
    settling_game_minutes: int = 2
    horizon_game_minutes: int = 60
    shore_snap_radius_m: int = 50
    auxiliary_power_rate: int = 1000
    max_pollution_native: int = 0


LOAD = Load()


@dataclass(frozen=True)
class BankParameters:
    search_radius_m: int = 192
    radial_step_m: int = 16
    directions: int = 16
    lateral_sample_spacing_m: int = 8
    minimum_wet_depth_m: float = 1
    minimum_freeboard_m: float = 0.25
    maximum_freeboard_m: float = 8
    maximum_bank_slope: float = 0.15


BANK = BankParameters()


def bank_candidate(ground, depth, anchor, water_height, tile):
    candidates = []
    origin = np.asarray(anchor)[[0, 2]]
    for radius in range(
        BANK.radial_step_m, BANK.search_radius_m + 1, BANK.radial_step_m
    ):
        for angle in np.arange(BANK.directions) * (2 * np.pi / BANK.directions):
            xz = np.asarray(anchor)[[0, 2]] + radius * np.asarray(
                [np.cos(angle), np.sin(angle)]
            )
            p = position(ground, xz)
            if _tile_of(p) != tile or sample(depth, np.asarray([xz]))[0] > 0.1:
                continue
            slopes = sample(
                ground,
                np.asarray([xz + [0, 16], xz - [0, 16], xz + [16, 0], xz - [16, 0]]),
            )
            dz, dx = (slopes[0] - slopes[1]) / 32, (slopes[2] - slopes[3]) / 32
            slope = float(np.hypot(dx, dz))
            if (
                not BANK.minimum_freeboard_m
                <= p[1] - water_height
                <= BANK.maximum_freeboard_m
                or slope > BANK.maximum_bank_slope
            ):
                continue
            lateral = np.linspace(
                origin, xz, int(radius / BANK.lateral_sample_spacing_m) + 1
            )
            wet_depths = sample(depth, lateral)
            dry_at = np.flatnonzero(wet_depths < BANK.minimum_wet_depth_m)
            last = int(dry_at[0] - 1) if len(dry_at) else len(lateral) - 1
            if (
                last < 0
                or np.linalg.norm(xz - lateral[last]) > LOAD.shore_snap_radius_m
            ):
                continue
            wet = lateral[last]
            result = {
                "bank": p,
                "water_anchor": [float(wet[0]), 0.0, float(wet[1])],
                "lateral_offset_m": float(np.linalg.norm(wet - origin)),
                "lateral_min_depth_m": float(wet_depths[: last + 1].min()),
                "lateral_sample_count": last + 1,
            }
            candidates.append((radius, slope, float(angle), result))
    return min(candidates, key=lambda item: item[:3])[3] if candidates else None


def assess_surface(folder):
    folder = Path(folder)
    report = assess(folder)
    candidate = report["capabilities"]["water"].get("witness")
    source = {
        name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        for name in (
            "surface_intake.py",
            "start_capabilities.py",
            "real_roads.py",
            "crp.py",
        )
    }
    model = {
        "id": "surface-intake-load-v1",
        "parameters": {"load": asdict(LOAD), "bank": asdict(BANK)},
        "source_sha256": source,
    }
    model["sha256"] = digest(model)
    report["base_start_model"] = report["model"]
    report["model"] = model
    water = report["capabilities"]["water"]
    water["predicted"] = None
    water["level"] = "unknown"
    water["reason"] = "no_supported_surface_load_witness"
    water["channel_candidate"] = candidate
    water["witness"] = None
    water["witness_sha256"] = None
    if not candidate:
        return report
    ground = (
        np.fromfile(folder / "terrain.u16", dtype="<u2")
        .reshape(1081, 1081)
        .astype(float)
        / 64
    )
    depth = (
        np.fromfile(folder / "water.u16", dtype="<u2").reshape(1081, 1081).astype(float)
        / 64
    )
    hydro = json.loads((folder / "hydrology.json").read_text())
    banks = []
    for key, prefab in [
        ("intake_water_point", "Water Intake"),
        ("outlet_water_point", "Water Outlet"),
    ]:
        anchor = candidate[key]
        xz = np.asarray([anchor])[:, [0, 2]]
        surface = float((sample(ground, xz) + sample(depth, xz))[0])
        bank = bank_candidate(ground, depth, anchor, surface, hydro["start_tile"])
        if bank is None:
            return report
        banks.append(
            {
                "prefab": prefab,
                "anchor": bank["water_anchor"],
                "initial_surface_m": surface,
                "model_bank_candidate": bank["bank"],
                "bank_search": {
                    k: v for k, v in bank.items() if k not in ("bank", "water_anchor")
                },
                "placement": "one_native_shore_snap",
                "shore_snap_radius_m": LOAD.shore_snap_radius_m,
            }
        )
    midpoint = [
        (banks[0]["model_bank_candidate"][i] + banks[1]["model_bank_candidate"][i]) / 2
        for i in (0, 2)
    ]
    consumer = position(ground, midpoint)
    witness = {
        "schema": 1,
        "start_tile": hydro["start_tile"],
        "facilities": banks,
        "consumer_point": consumer,
        "load": asdict(LOAD),
        "channel_route": candidate,
        "auxiliary_power": "fixed native ElectricityManager supply, not a claim about map power generation",
        "pipe_plan": "intake native pipe node -> consumer -> outlet native pipe node; no reroute",
        "scope": "Specified surface intake/outlet anchors, one native shore snap each, controlled power and fixed load/horizon",
    }
    water.update(
        {
            "predicted": True,
            "level": "likely",
            "reason": "initial_wet_downstream_route_with_nearby_bank_candidates",
            "witness": witness,
            "witness_sha256": digest(witness),
            "limits": [
                "Provisional geometric model; native shore snapping/placement may reject the specified anchors",
                "Native demand units per256simulationframes; no m3/s or population conversion",
                "Only a successful fixed-load native run can establish service at that demand/horizon",
                "Power is held available as an explicit auxiliary fixture, not a whole-map gameplay promise",
                "No global or long-horizon guarantee; no promise promotion",
            ],
        }
    )
    water["initial_quality_basis"] = (
        "crp.water_payload initializes native water pollution to zero; not a real-world salinity claim"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    with args.out.open("x") as output:
        output.write(json.dumps(assess_surface(args.prepared), indent=2) + "\n")
