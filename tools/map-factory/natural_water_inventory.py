"""Version-two source inventory; preserves the frozen v1 compiler unchanged."""

import copy

import numpy as np

from maintained_water_inventory import compile_inventory, position
from osm_highways import clip_box
from region import HALF


def compile_natural_inventory(geometry, hydro, plan):
    original = copy.deepcopy(hydro)
    original.pop("maintained_features", None)
    inventory = compile_inventory(geometry, original)
    inventory["schema"] = "polli.maintained-water-inventory/2"
    inventory["algorithm"] += (
        "; proven outside-square pieces accounted separately; passive mapped-lake anchors from authored construction plan"
    )
    outside_lakes = {
        e["feature_id"]
        for e in plan["source_features"]
        if e["status"] == "outside_square"
    }
    for entry in inventory["entries"]:
        field = entry.get("field")
        if entry["id"] in outside_lakes:
            entry.update(
                status="outside_square",
                reason="source polygon bounding box outside square",
            )
        elif (
            field in ("rivers", "streams")
            and entry.get("reason")
            == "no clipped line contract; outside or unsupported geometry"
        ):
            feature = geometry[field][entry["source_index"]]
            pts = np.array([position(geometry["sq"], p) for p in feature["pts"]])
            if (
                pts.ndim == 2
                and len(pts) >= 2
                and np.isfinite(pts).all()
                and not clip_box(pts, [-HALF, -HALF], [HALF, HALF])
            ):
                entry.update(
                    status="outside_square",
                    reason="finite source polyline clips to no in-square segment",
                )
    for body in plan["bodies"]:
        entry = {
            "id": "natural-storage:" + body["id"],
            "feature_ids": body["feature_ids"],
            "status": "unresolved",
        }
        if body["status"] == "constructed":
            name = "maintained:" + entry["id"]
            x, z = body["anchor_xz"]
            entry.update(
                status="compiled",
                contracts=[
                    {
                        "id": entry["id"],
                        "kind": "engineered",
                        "points_xz": [[x, z]],
                        "probe_names": [name],
                    }
                ],
            )
            inventory["points"].append({"name": name, "x": x, "z": z, "required": True})
        else:
            entry["reason"] = body["reason"]
        inventory["entries"].append(entry)
    inventory["coverage_complete"] = not any(
        e["status"] == "unresolved" for e in inventory["entries"]
    )
    return inventory
