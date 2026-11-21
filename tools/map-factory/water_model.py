"""Active PL-1212 Water-only port of the frozen PL-1078 surface witness.

Route/bank/load predicates preserved; explicit input abstentions and source bindings
are new. No native score transfers. This module never reads the archived outcomes.
"""

from dataclasses import asdict, dataclass
import math
import numpy as np
from real_roads import _tile_of
from start_model import PARAMETERS, GRID, position, sample

MODEL = "pl1212-surface-intake-port-v2"


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


def water_witness(ground, depth, hydro, params=PARAMETERS):
    tile = hydro["start_tile"]
    candidates = []
    for name, line in sorted(hydro.get("samples", {}).items()):
        p = np.asarray(line, dtype=float)
        if p.ndim != 2 or p.shape[0] < 2 or p.shape[1] != 3:
            continue
        xz = p[:, [0, 2]]
        depths = sample(depth, xz)
        surfaces = sample(ground, xz) + depths
        arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(xz, axis=0), axis=1))]
        inside = [
            i
            for i, v in enumerate(p)
            if _tile_of(v) == tile and depths[i] >= params.intake_depth_m
        ]
        for i in inside:
            downstream = [
                j
                for j in inside
                if arc[j] - arc[i] >= params.sewage_separation_m
                and np.all(depths[i : j + 1] >= params.intake_depth_m)
                and surfaces[i] > surfaces[j] + 1 / 64
            ]
            if not downstream:
                continue
            j = downstream[0]
            candidates.append(
                (
                    float(arc[j] - arc[i]),
                    name,
                    i,
                    j,
                    p[i].tolist(),
                    p[j].tolist(),
                    float(depths[i]),
                    float(surfaces[i] - surfaces[j]),
                )
            )
            break
    candidate = min(candidates) if candidates else None
    witness = (
        None
        if candidate is None
        else {
            "river": candidate[1],
            "intake_sample_index": candidate[2],
            "outlet_sample_index": candidate[3],
            "intake_water_point": candidate[4],
            "outlet_water_point": candidate[5],
            "along_route_separation_m": candidate[0],
            "initial_intake_depth_m": candidate[6],
            "initial_surface_drop_m": candidate[7],
            "direction_basis": "Prepared upstream-to-downstream channel route and initial surface drop; not simulated velocity",
            "bank_placement": None,
            "demand_native_units": None,
            "horizon_game_minutes": 60,
        }
    )
    return {
        "level": "unknown",
        "reason": "surface_flow_quality_and_sewage_service_unverified",
        "predicted": None,
        "witness": witness,
        "subchecks": {
            "initial_wet_downstream_route": bool(witness),
            "native_intake_placement": None,
            "clean_intake": None,
            "sustained_capacity": None,
            "sewage_downstream_safe": None,
        },
        "limits": [
            "Initial wet channel/nominal source capacity is not sustained intake capacity",
            "No salt/fresh or pollution inference from mapped water; no rate-unit conversion",
            "Groundwater service is separate, never a positive surface-water label",
        ],
    }


def evaluate_water(data):
    """Consume the existing full-grid normalization plus directed route metadata."""
    water = {
        "level": "unknown",
        "predicted": None,
        "witness": None,
        "model": MODEL,
        "native_agreement": "unscored_new_runtime",
        "stock_comparison": "not_comparable",
        "service": "unknown",
        "quality": "unknown",
        "flow": "unknown",
        "hookup": "unknown",
    }
    if data.get("planner_enabled", {}).get("water") is False:
        return {**water, "reason": "planner_disabled"}
    native = data.get("start_input")
    if native is None:
        return {**water, "reason": "missing_complete_water_grids"}
    if native.get("fidelity") != "prepared_16m_south_first":
        return {**water, "reason": "unsupported_water_fidelity"}
    water["fidelity"] = native["fidelity"]
    arrays = [
        np.asarray(native.get(k, []), dtype=float) for k in ("terrain_m", "depth_m")
    ]
    if any(a.size != GRID * GRID or not np.isfinite(a).all() for a in arrays):
        return {**water, "reason": "missing_complete_water_grids"}
    if (arrays[1] < 0).any():
        raise ValueError("Negative water depth")
    tile = native.get("tile")
    if type(tile) is not int or not 0 <= tile < 25:
        return {**water, "reason": "missing_start_tile"}
    plan = data.get("water_plan")
    routes = plan.get("samples") if isinstance(plan, dict) else None
    if not isinstance(routes, dict) or not routes:
        return {**water, "reason": "missing_directed_channel_routes"}
    for line in routes.values():
        try:
            a = np.asarray(line)
        except (TypeError, ValueError):
            return {**water, "reason": "partial_channel_routes"}
        if not np.issubdtype(a.dtype, np.number):
            return {**water, "reason": "partial_channel_routes"}
        if a.ndim != 2 or a.shape[0] < 2 or a.shape[1] != 3 or not np.isfinite(a).all():
            return {**water, "reason": "partial_channel_routes"}
    ground, depth = (a.reshape(GRID, GRID) for a in arrays)
    candidate = water_witness(ground, depth, {"start_tile": tile, "samples": routes})[
        "witness"
    ]
    water.update(
        reason="no_supported_surface_load_witness", channel_candidate=candidate
    )
    if not candidate:
        return water
    banks = []
    for key, prefab in [
        ("intake_water_point", "Water Intake"),
        ("outlet_water_point", "Water Outlet"),
    ]:
        anchor = candidate[key]
        xz = np.asarray([anchor])[:, [0, 2]]
        surface = float((sample(ground, xz) + sample(depth, xz))[0])
        bank = bank_candidate(ground, depth, anchor, surface, tile)
        if bank is None:
            return water
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
        "start_tile": tile,
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
    return water


CAPTURE_WATER_FIDELITY = "capture_16m_bank_minus_bed_or_coastal_depth"
SHORE_SCOPE = "Central 1920m square, 64m wet-anchor lattice, 16m capture and 8m lateral interpolation"


def normalize_water_opportunity(value):
    """Whitelist compact geometry; caller status/proof fields are never evidence.

    Geometry is declared capture evidence, not authenticated raw capture or
    service qualification. This mirrors normalizeWaterOpportunity exactly.
    """
    result = {
        "level": "unknown",
        "predicted": None,
        "witness": None,
        "model": MODEL,
        "native_agreement": "unscored_capture_approximation",
        "stock_comparison": "not_comparable",
        "service": "unknown",
        "quality": "unknown",
        "flow": "unknown",
        "hookup": "unknown",
        "opportunity": "unknown",
        "fidelity": CAPTURE_WATER_FIDELITY,
        "reason": "missing_capture_opportunity",
    }
    if not isinstance(value, dict):
        return result
    if value.get("model") != MODEL:
        return {**result, "reason": "unbound_capture_opportunity"}
    if value.get("fidelity") != CAPTURE_WATER_FIDELITY:
        return {**result, "reason": "unsupported_capture_opportunity"}
    if value.get("opportunity") == "unknown" and value.get("reason") in (
        "incomplete_or_coarse_shore_grid",
        "no_bank_in_finite_capture_search",
    ):
        return {**result, "reason": value["reason"]}
    invalid = {**result, "reason": "invalid_capture_opportunity"}

    def finite(v):
        return type(v) in (int, float) and math.isfinite(v)

    def vector(v, size):
        return isinstance(v, list) and len(v) == size and all(finite(x) for x in v)

    def distance(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def near(a, b):
        return abs(a - b) <= 1e-7

    origin, bank = value.get("wet_point_xz"), value.get("bank")
    if (
        value.get("opportunity") != "candidate"
        or value.get("reason") != "captured_shore_bank_candidate"
        or not vector(origin, 2)
        or not all(-832 <= v <= 832 and (v + 832) % 64 == 0 for v in origin)
        or not isinstance(bank, dict)
        or not vector(bank.get("bank"), 3)
        or not vector(bank.get("water_anchor"), 3)
    ):
        return invalid
    p, wet = bank["bank"], bank["water_anchor"]
    offset, minimum, count = (
        bank.get(k)
        for k in ("lateral_offset_m", "lateral_min_depth_m", "lateral_sample_count")
    )
    if (
        _tile_of(p) != 12
        or _tile_of(wet) != 12
        or wet[1] != 0
        or not finite(minimum)
        or minimum < BANK.minimum_wet_depth_m
        or not finite(offset)
        or offset < 0
        or not finite(count)
        or int(count) != count
        or not 1 <= count <= 25
    ):
        return invalid
    bank_xz, wet_xz = [p[0], p[2]], [wet[0], wet[2]]
    radius = distance(bank_xz, origin)
    if (
        radius < 16 - 1e-7
        or radius > 192 + 1e-7
        or not near(radius / 16, round(radius / 16))
        or not near(offset, (count - 1) * 8)
        or not near(distance(wet_xz, origin), offset)
        or offset > radius + 1e-7
        or distance(bank_xz, wet_xz) > LOAD.shore_snap_radius_m + 1e-7
        or not near(distance(bank_xz, wet_xz), radius - offset)
    ):
        return invalid
    return {
        **result,
        "level": "likely",
        "reason": "captured_shore_bank_candidate",
        "opportunity": "candidate",
        "wet_point_xz": list(origin),
        "scope": SHORE_SCOPE,
        "bank": {
            "bank": list(p),
            "water_anchor": list(wet),
            "lateral_offset_m": offset,
            "lateral_min_depth_m": minimum,
            "lateral_sample_count": count,
        },
    }
