"""Consumed-field equality is a model-function oracle, never native qualification."""

from __future__ import annotations

import math

from protocol import ProtocolError, strict_bool

# Fields read by Prepared -> mode_lanes / _search -> chord / can_travel /
# continues(any_lane), after normalization. Extra raw fields remain in identity.
SEGMENT_FIELDS = frozenset({"id", "start", "end", "a", "b", "flags", "lanes"})
LANE_FIELDS = frozenset(
    {"index", "lane_type", "vehicle", "category", "forward", "backward"}
)


def consumed(package: dict) -> dict:
    if not package.get("segments"):
        raise ProtocolError("empty/absent segment inventory")
    result = {}
    for sid, segment in package["segments"].items():
        if not SEGMENT_FIELDS <= segment.keys() or sid != segment["id"]:
            raise ProtocolError("missing consumed segment field or key/id differs")
        for side in ("a", "b"):
            xyz = segment[side]
            if len(xyz) != 3 or any(
                type(v) not in (int, float) or not math.isfinite(v) for v in xyz
            ):
                raise ProtocolError("missing/nonfinite xyz (height is consumed)")
        lanes = []
        for lane in segment["lanes"]:
            if not LANE_FIELDS <= lane.keys():
                raise ProtocolError("missing consumed lane field")
            strict_bool(lane["forward"])
            strict_bool(lane["backward"])
            lanes.append({k: lane[k] for k in sorted(LANE_FIELDS)})
        result[sid] = {k: segment[k] for k in ("id", "start", "end", "a", "b")}
        result[sid].update(invert="Invert" in segment["flags"], lanes=lanes)
    return result


def compare(export: dict, native: dict) -> dict:
    """No projection-only result ever admits a mismatched exact-identity row."""
    try:
        same = consumed(export) == consumed(native)
        return {
            "normalized_object_identity": export == native,
            "model_consumed_equality": same,
            "native_qualification": "unknown",
            "reason": (
                "same arguments to the pinned pure function only"
                if same
                else "consumed fields differ; decision invariance not established"
            ),
        }
    except (ProtocolError, KeyError, TypeError, ValueError) as error:
        return {
            "normalized_object_identity": False,
            "model_consumed_equality": None,
            "native_qualification": "unknown",
            "reason": str(error),
        }


def exact_raw_identity(left: bytes, right: bytes) -> bool:
    """Literal byte equality only. Does not normalize or alter accepted identity."""
    if type(left) is not bytes or type(right) is not bytes:
        raise ProtocolError("raw byte identities require bytes")
    return left == right
