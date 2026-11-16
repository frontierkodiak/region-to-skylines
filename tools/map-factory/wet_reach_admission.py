"""Replay input-bound native dry-reach evidence, never a region-name selector.

Records contain only sparse, monotone terrain restoration and water removal.
No matching record means ordinary, unqualified preparation; an explicit stale
record or corrupt registry fails before either grid is written. Qualification
receipts live in the versioned fixture contract, not this transformation data.
"""

import hashlib
import json
from pathlib import Path

import numpy as np

from crp import read_package
from template import manager_tag

ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / "native-water-admission.json"
SIZE = 1081 * 1081
FEATURE_FIELDS = [
    "rivers",
    "streams",
    "lakes",
    "riverAreas",
    "oceans",
    "undergroundWaterways",
    "labels",
    "sources",
]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def geometry_digest(path):
    geometry = json.loads(path.read_bytes())
    for field in FEATURE_FIELDS:
        if isinstance(geometry.get(field), list):
            geometry[field] = sorted(geometry[field], key=canonical)
    return digest(canonical(geometry))


def bindings(prepared, png, geometry, banks):
    """Bind actual inputs and native forcing independently of resource variants."""
    hydro = json.loads((prepared / "hydrology.json").read_bytes())
    _, assets = read_package((prepared / (hydro["map_id"] + ".crp")).read_bytes())
    simulation = next(a["payload"] for a in assets if a["kind"] == 52)
    water = simulation[
        simulation.index(manager_tag("WaterSimulation")) : simulation.index(
            manager_tag("NetManager")
        )
    ]
    nodes = {
        key: np.asarray(value, dtype="<f4").tobytes().hex()
        for key, value in hydro["node_positions"].items()
    }
    result = {
        "png": digest(png.read_bytes()),
        "geometry": geometry_digest(geometry),
        "banks": digest(banks.read_bytes()) if banks else None,
        "terrain": digest((prepared / "terrain.u16").read_bytes()),
        "water": digest((prepared / "water.u16").read_bytes()),
        "native_water_simulation": digest(water),
        "nodes": digest(canonical(nodes)),
        "start_tile": hydro["start_tile"],
        "template": digest((ROOT / "templates/native-corridors.crp").read_bytes()),
        "layout": digest((ROOT / "templates/native-corridors.json").read_bytes()),
    }
    return result


def build_record(prepared, candidate, png, geometry, banks):
    """Authoring helper; native planning/validation is a separate prerequisite."""
    bound = bindings(prepared, png, geometry, banks)
    old_t, old_w = [
        np.fromfile(prepared / (name + ".u16"), "<u2") for name in ["terrain", "water"]
    ]
    new_t, new_w = [
        np.fromfile(candidate / (name + ".u16"), "<u2") for name in ["terrain", "water"]
    ]
    if not all(a.size == SIZE for a in [old_t, old_w, new_t, new_w]):
        raise ValueError("Admission needs complete native grids")
    if (new_t < old_t).any() or (new_w > old_w).any():
        raise ValueError("Admission cannot deepen floors or add water")
    changed = np.flatnonzero((old_t != new_t) | (old_w != new_w))
    edits = np.stack(
        [changed, old_t[changed], new_t[changed], old_w[changed], new_w[changed]],
        axis=1,
    ).tolist()
    return {
        "format": 1,
        "fingerprint": digest(canonical(bound)),
        "bindings": bound,
        "edits": edits,
        "target": {
            "terrain": digest(new_t.tobytes()),
            "water": digest(new_w.tobytes()),
        },
    }


def replay_arrays(terrain, water, fingerprint, record):
    """Validate an explicit record completely before returning changed arrays."""
    if record.get("format") != 1 or record.get("fingerprint") != fingerprint:
        raise ValueError(
            "Native admission evidence is stale or belongs to different inputs"
        )
    if digest(canonical(record["bindings"])) != fingerprint:
        raise ValueError("Native admission bindings were changed")
    terrain, water = (
        np.asarray(terrain, dtype="<u2").reshape(-1),
        np.asarray(water, dtype="<u2").reshape(-1),
    )
    if terrain.size != SIZE or water.size != SIZE:
        raise ValueError("Incomplete native admission grids")
    if (
        digest(terrain.tobytes()) != record["bindings"]["terrain"]
        or digest(water.tobytes()) != record["bindings"]["water"]
    ):
        raise ValueError("Native admission baseline grids changed")
    edits = np.asarray(record["edits"])
    if edits.size == 0:
        edits = np.empty((0, 5), dtype=np.int64)
    if (
        edits.ndim != 2
        or edits.shape[1] != 5
        or not np.issubdtype(edits.dtype, np.integer)
    ):
        raise ValueError("Invalid native admission edits")
    ids = edits[:, 0]
    if ((ids < 0) | (ids >= SIZE)).any() or (np.diff(ids) <= 0).any():
        raise ValueError(
            "Native admission indices must be unique, ordered and in bounds"
        )
    if ((edits[:, 1:] < 0) | (edits[:, 1:] > 65535)).any():
        raise ValueError("Native admission values exceed ushort bounds")
    if not np.array_equal(terrain[ids], edits[:, 1]) or not np.array_equal(
        water[ids], edits[:, 3]
    ):
        raise ValueError("Native admission old values do not match")
    if (edits[:, 2] < edits[:, 1]).any() or (edits[:, 4] > edits[:, 3]).any():
        raise ValueError("Native admission cannot deepen floors or add water")
    new_t, new_w = terrain.copy(), water.copy()
    new_t[ids], new_w[ids] = edits[:, 2], edits[:, 4]
    if (
        digest(new_t.tobytes()) != record["target"]["terrain"]
        or digest(new_w.tobytes()) != record["target"]["water"]
    ):
        raise ValueError("Native admission target digest mismatch")
    return new_t, new_w


def admit(prepared, png, geometry, banks, registry_path=REGISTRY):
    """Apply only evidence for these inputs; never claim native acceptance here."""
    registry = json.loads(registry_path.read_bytes())
    if (
        registry.get("format") != 1
        or registry.get("policy") != "native-dry-subreach-v1"
    ):
        raise ValueError("Unsupported native admission registry")
    bound = bindings(prepared, png, geometry, banks)
    fingerprint = digest(canonical(bound))
    record = registry["records"].get(fingerprint)
    if record is None:
        return {"applied": False, "fingerprint": fingerprint, "native_qualified": False}
    terrain, water = [
        np.fromfile(prepared / (name + ".u16"), "<u2") for name in ["terrain", "water"]
    ]
    new_t, new_w = replay_arrays(terrain, water, fingerprint, record)
    # Validate both targets first. The caller owns this isolated output directory
    # and does not return a package until both writes and final packing succeed.
    for name, values in [("terrain", new_t), ("water", new_w)]:
        temporary = prepared / (name + ".admission-part")
        values.tofile(temporary)
        temporary.replace(prepared / (name + ".u16"))
    return {
        "applied": True,
        "fingerprint": fingerprint,
        "terrain_raised": int((new_t != terrain).sum()),
        "startup_water_removed": int((new_w != water).sum()),
        "native_qualified": False,
    }
