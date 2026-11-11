"""Opt-in native New Game panel capture and fail-closed offline assessment.

A capture is not a visual review. A separate, hash-bound review records what a
person/agent actually saw; requested checks fail until that review is supplied.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import pathlib
import time

from PIL import Image, ImageStat

RESOURCE_FIELDS = ("maxResourceAmount", "oilAmount", "oreAmount", "forestAmount", "fertileLandAmount", "waterAmount")
CONNECTION_FIELDS = (
    "incomingRoads",
    "outgoingRoads",
    "incomingTrainTracks",
    "outgoingTrainTracks",
    "incomingShipPath",
    "outgoingShipPath",
    "incomingPlanePath",
    "outgoingPlanePath",
)


def expectations(value: dict) -> dict:
    """Require explicit intended values; no guessing what a map should advertise."""
    if not isinstance(value, dict):
        raise ValueError("new_game_panel must be an expectations object")
    for field in ("map_name", "author", "buildableArea", "resources", "connections"):
        if field not in value:
            raise ValueError(f"new_game_panel missing expectation: {field}")
    if not isinstance(value["map_name"], str) or not value["map_name"].strip():
        raise ValueError("new_game_panel map_name must be nonempty")
    if not isinstance(value["author"], str):
        raise ValueError("new_game_panel author must be a string (empty intentionally hides the label)")
    if type(value["buildableArea"]) is not int or not 0 <= value["buildableArea"] <= 100:
        raise ValueError("new_game_panel buildableArea must be an integer percent in [0, 100]")
    for group, fields in (("resources", RESOURCE_FIELDS), ("connections", CONNECTION_FIELDS)):
        if not isinstance(value[group], dict) or set(value[group]) != set(fields):
            raise ValueError(f"new_game_panel {group} requires exactly {', '.join(fields)}")
        for name in fields:
            number = value[group][name]
            if type(number) not in (int, float) or not 0 <= number < float("inf"):
                raise ValueError(f"new_game_panel {name} must be finite and nonnegative")
            if name != "maxResourceAmount" and type(number) is not int:
                raise ValueError(f"new_game_panel {name} must be an integer")
    return value


def request(out: pathlib.Path) -> dict | None:
    """Read only the frozen run inputs, never a mutable source probe file."""
    path = out / "probes.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or "new_game_panel" not in data:
        return None
    return expectations(data["new_game_panel"])


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def object_value(value, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def wait_for_capture(session, shot: pathlib.Path, timeout: float = 30) -> str:
    """Wait for a complete native PNG; hash the exact bytes that were validated."""
    deadline = time.monotonic() + timeout
    while True:
        # Session.alive normally returns None and raises on death/conflict. Also
        # support boolean liveness implementations without ignoring explicit False.
        if session.alive() is False:
            raise RuntimeError("game process ended before native New Game screenshot completed")
        try:
            data = shot.read_bytes()
            with Image.open(io.BytesIO(data)) as image:
                if image.format != "PNG":
                    raise ValueError("native screenshot is not PNG")
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                image.load()
            return hashlib.sha256(data).hexdigest()
        except (OSError, ValueError, SyntaxError) as exc:
            if time.monotonic() >= deadline:
                raise RuntimeError("native New Game screenshot did not become a complete PNG") from exc
        time.sleep(0.25)


def capture(session, out: pathlib.Path, path: str, wanted: dict) -> None:
    """Called only by the mod-enabled map-check driver, before loading a city."""
    expectations(wanted)
    client = session.client
    client.call("new_game_panel", path=path, select=True)
    try:
        # Native progress bars animate on selection. Capture after they settle.
        time.sleep(3)
        shot = session.stage / "new-game-panel.png"
        observed = client.call("new_game_panel", path=path, screenshot=str(shot))
        sha256 = wait_for_capture(session, shot)
        (out / "new-game-panel.json").write_text(
            json.dumps({"observed": observed, "screenshot": shot.name, "sha256": sha256}, indent=2) + "\n"
        )
    finally:
        # Don't wait on a dead bridge just to dismiss a vanished modal.
        if session.alive() is not False:
            client.call("new_game_panel", close=True)


def assess(out: pathlib.Path) -> dict:
    """One verdict row, including metadata mismatches and explicit review state."""
    result = {
        "name": "new_game_panel",
        "status": "skip",
        "value": None,
        "threshold": "native listing + resolvable image refs + hash-bound visual review",
        "detail": "not requested",
    }
    try:
        wanted = request(out)
        if wanted is None:
            return result
        problems = []
        evidence = object_value(json.loads((out / "new-game-panel.json").read_text()), "panel evidence")
        observed = object_value(evidence["observed"], "native observation")
        if observed.get("source") != "native NewGamePanel" or not observed.get("published"):
            problems.append("not a published native New Game listing")
        for key in ("map_name", "author", "buildableArea", "connections"):
            if observed.get(key) != wanted[key]:
                problems.append(f"native {key} differs from expectation")
        resources = object_value(observed.get("resources"), "native resources")
        for key in RESOURCE_FIELDS:
            actual = resources.get(key)
            expected = wanted["resources"][key]
            # Only the native float denominator gets float32 serialization slack;
            # resource amounts, directional counts and buildable percent stay exact.
            matches = actual == expected
            if key == "maxResourceAmount" and type(actual) in (int, float):
                matches = math.isclose(actual, expected, rel_tol=1e-7, abs_tol=1e-6)
            if not matches:
                problems.append(f"native resources.{key} differs from expectation")
        for key in ("imageRef", "steamPreviewRef"):
            ref = object_value(observed.get(key) or {}, key)
            if not ref.get("resolved") or min(ref.get("width", 0), ref.get("height", 0)) <= 0:
                problems.append(f"{key} missing/unresolvable")
        if not observed.get("snapshot_texture_present"):
            problems.append("native selected panel has no snapshot texture")
        if bool(observed.get("author_visible")) != bool(wanted["author"]):
            problems.append("native author label visibility differs")
        filename = evidence["screenshot"]
        if filename != "new-game-panel.png":
            raise ValueError("screenshot must be the run-local new-game-panel.png")
        shot = out / filename
        if digest(shot) != evidence["sha256"]:
            problems.append("screenshot changed since capture")
        with Image.open(shot) as image:
            image.verify()
        with Image.open(shot) as image:
            if ImageStat.Stat(image.convert("L")).stddev[0] < 3:
                problems.append("screenshot is blank (grey std < 3)")
        review_path = out / "new-game-panel-review.json"
        review = object_value(json.loads(review_path.read_text()), "visual review") if review_path.is_file() else {}
        if review.get("sha256") != evidence["sha256"] or not review.get("reviewer") or not review.get("notes"):
            problems.append("screenshot unreviewed (requires hash, reviewer and notes)")
        # Review facts must be transcribed from the rendered selection, not copied
        # automatically from the native listing. Resource/connection facts here are
        # explicit visual assertions (bars/icons), not unreadable numeric counts.
        visual = object_value(review.get("observed") or {}, "visual observations")
        for key in ("map_name", "author", "buildableArea"):
            if visual.get(key) != wanted[key]:
                problems.append(f"rendered {key} unconfirmed/mismatched")
        for key in ("preview_matches_map", "resources_match", "connections_match", "selected_map_visible"):
            if visual.get(key) is not True:
                problems.append(f"rendered {key} unconfirmed/mismatched")
        result.update(
            status="fail" if problems else "pass",
            value={
                "observed": observed,
                "screenshot": filename,
                "reviewer": review.get("reviewer"),
                "problems": problems,
            },
            detail="; ".join(problems) if problems else "native listing and rendered selection reviewed",
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result.update(status="fail", detail=f"requested panel evidence unavailable/invalid: {exc}")
    return result
