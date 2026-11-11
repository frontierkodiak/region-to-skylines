"""Keep explicit underground waterways out of terrain-surface hydraulics.

OpenMapTiles' waterway.brunnel=tunnel is source evidence, not a native flood
classification. Retain every excluded feature so omitted reaches are auditable.
"""

import hashlib
import json


def surface_geometry(geometry):
    result = dict(geometry)
    underground = list(geometry.get("undergroundWaterways", []))
    for field, kind in [("rivers", "river"), ("streams", "stream")]:
        visible = []
        for feature in geometry.get(field, []):
            tagged = feature.get("brunnel")
            source = feature.get("sourceFeature", {}).get("properties", {})
            if "brunnel" in source and tagged != source["brunnel"]:
                raise ValueError("Waterway visibility disagrees with source properties")
            if tagged == "tunnel":
                underground.append(
                    {
                        **feature,
                        "class": kind,
                        "exclusionReason": "explicit waterway.brunnel=tunnel",
                    }
                )
            else:
                visible.append(feature)
        result[field] = visible
    if any(feature.get("brunnel") != "tunnel" for feature in underground):
        raise ValueError("Underground waterways require explicit tunnel evidence")
    result["undergroundWaterways"] = underground
    receipt = {
        "policy": "explicit brunnel=tunnel only; intermittent and bridge tags retained",
        "surface_river_pieces": len(result["rivers"]),
        "surface_stream_pieces": len(result["streams"]),
        "underground_pieces": len(underground),
        "underground_sha256": hashlib.sha256(
            json.dumps(underground, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    return result, receipt
