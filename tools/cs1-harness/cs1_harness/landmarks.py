"""Native world landmark checks against explicit, independently sourced DEM expectations."""

from __future__ import annotations

import json
import math
import pathlib

SOURCE = "TerrainManager.SampleRawHeightSmooth/world camera"


def number(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def request(out: pathlib.Path) -> dict | None:
    path = out / "probes.json"
    data = json.loads(path.read_text()) if path.is_file() else {}
    if not isinstance(data, dict) or "landmark_expectations" not in data:
        return None
    value = data["landmark_expectations"]
    if not isinstance(value, dict) or not isinstance(value.get("reference"), str) or not value["reference"].strip():
        raise ValueError("landmarks requires an independent DEM reference description")
    points = value.get("points")
    if not isinstance(points, list) or len(points) < 2:
        raise ValueError("landmarks requires at least two asymmetric known points")
    names = set()
    for point in points:
        if not isinstance(point, dict) or not isinstance(point.get("name"), str) or not point["name"].strip():
            raise ValueError("each landmark needs a nonempty unique name")
        if point["name"] in names:
            raise ValueError("duplicate landmark name")
        names.add(point["name"])
        if any(not number(point.get(key)) for key in ("x", "z", "expected_height_m", "tolerance_m")):
            raise ValueError("landmark coordinates, expected height and tolerance must be finite numbers")
        if max(abs(point["x"]), abs(point["z"])) > 8640 or not 0 <= point["expected_height_m"] <= 1024:
            raise ValueError("landmark outside native terrain coordinate/height range")
        if point["tolerance_m"] <= 0:
            raise ValueError("landmark tolerance must be positive")
    if not any(
        a["x"] != b["x"]
        and a["z"] != b["z"]
        and abs(a["expected_height_m"] - b["expected_height_m"]) > a["tolerance_m"] + b["tolerance_m"]
        for i, a in enumerate(points)
        for b in points[i + 1 :]
    ):
        raise ValueError("landmarks need separated x/z coordinates and distinguishable expected heights")
    return value


def capture(session, out: pathlib.Path, wanted: dict | None) -> dict:
    points = [{key: point[key] for key in ("name", "x", "z")} for point in (wanted or {}).get("points", [])]
    observed = session.client.call("world_observe", points=points)
    observed["phase"] = "startup_before_harness_camera_overrides"
    (out / "startup-world.json").write_text(json.dumps(observed, indent=2) + "\n")
    return observed


def assess(out: pathlib.Path) -> dict:
    row = {
        "name": "terrain_landmarks",
        "status": "skip",
        "value": None,
        "threshold": "each independently referenced landmark within its declared height tolerance",
        "detail": "not requested",
    }
    try:
        wanted = request(out)
        if wanted is None:
            return row
        observed = json.loads((out / "startup-world.json").read_text())
        if not isinstance(observed, dict) or observed.get("source") != SOURCE:
            raise ValueError("missing native world observation provenance")
        if observed.get("phase") != "startup_before_harness_camera_overrides":
            raise ValueError("landmarks were not observed before camera overrides")
        camera = observed.get("camera")
        if not isinstance(camera, dict):
            raise ValueError("missing native startup camera observation")
        angles = camera.get("current_angle_degrees")
        if not isinstance(angles, list) or len(angles) != 2 or not all(number(v) for v in angles):
            raise ValueError("invalid native startup camera heading/tilt")
        if camera.get("areas_visible") is not False:
            raise ValueError("startup observation was already in Area Zoom")
        samples = observed.get("points")
        if not isinstance(samples, list) or len(samples) != len(wanted["points"]):
            raise ValueError("native landmark sample count differs from request")
        rows = []
        for expected, actual in zip(wanted["points"], samples):
            if not isinstance(actual, dict) or any(actual.get(k) != expected[k] for k in ("name", "x", "z")):
                raise ValueError("native landmark sample identity/coordinates differ from request")
            if not number(actual.get("height_m")):
                raise ValueError("native landmark height unavailable/nonfinite")
            error = actual["height_m"] - expected["expected_height_m"]
            rows.append(
                {
                    **expected,
                    "height_m": actual["height_m"],
                    "error_m": error,
                    "pass": abs(error) <= expected["tolerance_m"],
                }
            )
        failed = [p["name"] for p in rows if not p["pass"]]
        row.update(
            status="fail" if failed else "pass",
            value={"reference": wanted["reference"], "points": rows, "startup_camera": camera},
            detail="outside height tolerance: " + ", ".join(failed)
            if failed
            else "native landmark heights match independent reference",
        )
    except (OSError, ValueError, TypeError, KeyError) as exc:
        row.update(status="fail", detail=f"requested landmark evidence unavailable/invalid: {exc}")
    return row
