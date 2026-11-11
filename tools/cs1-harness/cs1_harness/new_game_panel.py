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

from .client import HarnessError

RESOURCE_FIELDS = ("maxResourceAmount", "oilAmount", "oreAmount", "forestAmount", "fertileLandAmount", "waterAmount")
BAR_FIELDS = {
    "oil": ("oilAmount", "ResourceBarOil"),
    "ore": ("oreAmount", "ResourceBarOre"),
    "forest": ("forestAmount", "ResourceBarForestry"),
    "fertility": ("fertileLandAmount", "ResourceBarFarming"),
    "water": ("waterAmount", "ResourceBarWater"),
}
BAR_SOURCE = "native UIProgressBar.value / NewGamePanel resource targets"
BAR_VALUE_TOLERANCE = 1e-4
BAR_TARGET_TOLERANCE = 1e-5
BAR_STABILITY_TOLERANCE = 1e-5
BAR_SAMPLES = 3
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
    if "require_resource_bars" in value and type(value["require_resource_bars"]) is not bool:
        raise ValueError("new_game_panel require_resource_bars must be a boolean")
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


def bar_reading(observed: dict) -> tuple[dict, list[str]]:
    """Validate provenance/targets independently; report actual animation/value errors."""
    observed = object_value(observed, "panel observation")
    if observed.get("source") != "native NewGamePanel":
        raise ValueError("resource bars lack native panel provenance")
    if (
        not isinstance(observed.get("path"), str)
        or not observed["path"]
        or type(observed.get("selected_index")) is not int
        or observed["selected_index"] < 0
    ):
        raise ValueError("resource bars lack selected map identity")
    resources = object_value(observed.get("resources"), "native resource metadata")
    reading = object_value(observed.get("resource_bars"), "native resource bar readback (updated mod required)")
    if type(reading.get("schema")) is not int or reading["schema"] != 1 or reading.get("source") != BAR_SOURCE:
        raise ValueError("unsupported resource bar provenance/schema")
    if (
        type(reading.get("frame")) is not int
        or reading["frame"] < 0
        or not finite(reading.get("realtime"))
        or reading["realtime"] < 0
    ):
        raise ValueError("resource bars lack native render frame/time")
    bars = object_value(reading.get("bars"), "resource bars")
    if set(bars) != set(BAR_FIELDS):
        raise ValueError("resource bars require all five native controls")
    errors = []
    for name, (field, component) in BAR_FIELDS.items():
        bar = object_value(bars[name], f"{name} bar")
        for key in ["value", "min_value", "max_value", "normalized_target", "target_value", "exponent", "denominator"]:
            if not finite(bar.get(key)):
                raise ValueError(f"{name} bar {key} unavailable/nonfinite")
        amount, denominator = resources.get(field), resources.get("maxResourceAmount")
        if type(amount) is not int or amount < 0 or not finite(denominator) or denominator < 0:
            raise ValueError(f"{name} bar metadata unavailable/invalid")
        if type(bar.get("amount")) is not int or bar["amount"] != amount or bar["denominator"] != denominator:
            raise ValueError(f"{name} bar is bound to different metadata")
        if bar.get("component") != component or bar["max_value"] <= bar["min_value"]:
            raise ValueError(f"{name} bar control/range mismatch")
        try:
            target = math.pow(amount / denominator, bar["exponent"]) if denominator > 0 else 0
        except (ValueError, OverflowError, ZeroDivisionError) as exc:
            raise ValueError(f"{name} bar target is undefined") from exc
        if not finite(target) or not math.isclose(
            target, bar["normalized_target"], rel_tol=1e-5, abs_tol=BAR_TARGET_TOLERANCE
        ):
            raise ValueError(f"{name} native normalized target differs from metadata/exponent")
        clamped = max(bar["min_value"], min(bar["max_value"], target))
        if not math.isclose(clamped, bar["target_value"], rel_tol=1e-5, abs_tol=BAR_TARGET_TOLERANCE):
            raise ValueError(f"{name} native target differs from UIProgressBar clamping")
        for key in ["visible", "animating", "no_resource_visible", "expected_no_resource"]:
            if type(bar.get(key)) is not bool:
                raise ValueError(f"{name} bar {key} must be a native boolean")
        if not bar["visible"] or bar["animating"]:
            errors.append(f"{name} bar hidden/animating")
        if bar["expected_no_resource"] != (amount == 0) or bar["no_resource_visible"] != (amount == 0):
            errors.append(f"{name} no-resource icon mismatch")
        if abs(bar["value"] - bar["target_value"]) > BAR_VALUE_TOLERANCE or (
            bar["target_value"] > 0 and bar["value"] <= 0
        ):
            errors.append(f"{name} bar value {bar['value']:g} has not reached target {bar['target_value']:g}")
    return reading, errors


def finite(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def measurement(observed: dict) -> dict:
    return {k: observed[k] for k in ["source", "path", "selected_index", "map_name", "resources", "resource_bars"]}


def bars_stable(samples: list[dict]) -> bool:
    if len(samples) != BAR_SAMPLES:
        return False
    readings = [bar_reading(sample) for sample in samples]
    if any(errors for _, errors in readings):
        return False
    first = samples[0]
    for sample in samples[1:]:
        if any(sample.get(k) != first.get(k) for k in ["path", "selected_index", "map_name", "resources"]):
            return False
    for (a, _), (b, _) in zip(readings, readings[1:]):
        if b["frame"] <= a["frame"] or b["realtime"] <= a["realtime"]:
            return False
    for name in BAR_FIELDS:
        bars = [r["bars"][name] for r, _ in readings]
        if max(b["value"] for b in bars) - min(b["value"] for b in bars) > BAR_STABILITY_TOLERANCE:
            return False
        if any(
            any(b[k] != bars[0][k] for k in ["target_value", "exponent", "min_value", "max_value"]) for b in bars[1:]
        ):
            return False
    return True


def wait_for_bars(session, path: str, trace: dict, timeout: float = 15) -> list[dict]:
    deadline = time.monotonic() + timeout
    samples = []
    while True:
        if session.alive() is False:
            raise HarnessError("game process ended before native resource bars settled")
        observed = session.client.call("new_game_panel", path=path, bars_only=True)
        trace["last"] = observed
        _, errors = bar_reading(observed)
        trace["last"] = measurement(observed)
        trace["last_errors"] = errors
        samples = (samples + [trace["last"]])[-BAR_SAMPLES:] if not errors else []
        if bars_stable(samples):
            return samples
        if time.monotonic() >= deadline:
            raise HarnessError("native resource bars did not settle: " + "; ".join(errors or ["unstable readings"]))
        time.sleep(0.25)


def check_bar_settlement(evidence: dict) -> None:
    settled = object_value(evidence.get("resource_bar_settlement"), "native resource bar settlement")
    if type(settled.get("schema")) is not int or settled["schema"] != 1:
        raise ValueError("native resource bar settlement schema missing/invalid")
    for sample in settled["samples"]:
        _, errors = bar_reading(sample)
        if errors:
            raise ValueError("before capture: " + "; ".join(errors))
    if not bars_stable(settled["samples"]):
        raise ValueError("resource bars are missing, incorrect or unstable before capture")
    previous = settled["samples"][-1]
    for observed in [evidence["observed"], settled["after"]]:
        reading, errors = bar_reading(observed)
        if errors:
            raise ValueError("; ".join(errors))
        if any(observed.get(k) != previous.get(k) for k in ["path", "selected_index", "map_name", "resources"]):
            raise ValueError("resource bar selection changed during capture")
        before = previous["resource_bars"]
        if reading["frame"] < before["frame"] or reading["realtime"] < before["realtime"]:
            raise ValueError("resource bar capture frames/time out of order")
        for name in BAR_FIELDS:
            a, b = before["bars"][name], reading["bars"][name]
            if (
                abs(a["value"] - b["value"]) > BAR_STABILITY_TOLERANCE
                or a["target_value"] != b["target_value"]
                or a["exponent"] != b["exponent"]
            ):
                raise ValueError(f"{name} resource bar changed during capture")
        previous = observed


def capture(session, out: pathlib.Path, path: str, wanted: dict, bar_timeout: float = 15) -> None:
    """Called only by the mod-enabled map-check driver, before loading a city."""
    expectations(wanted)
    client = session.client
    evidence = {"resource_bar_settlement": {"schema": 1}}
    try:
        if session.alive() is False:
            raise HarnessError("game process ended before native panel selection")
        client.call("new_game_panel", path=path, select=True)
        evidence["resource_bar_settlement"]["samples"] = wait_for_bars(
            session, path, evidence["resource_bar_settlement"], bar_timeout
        )
        shot = session.stage / "new-game-panel.png"
        observed = client.call("new_game_panel", path=path, screenshot=str(shot))
        sha256 = wait_for_capture(session, shot)
        evidence.update(observed=observed, screenshot=shot.name, sha256=sha256)
        evidence["resource_bar_settlement"]["after"] = measurement(
            client.call("new_game_panel", path=path, bars_only=True)
        )
        check_bar_settlement(evidence)
        (out / "new-game-panel.json").write_text(json.dumps(evidence, indent=2) + "\n")
    except Exception as exc:
        evidence["error"] = str(exc)
        (out / "new-game-panel.json").write_text(json.dumps(evidence, indent=2) + "\n")
        raise
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
        if evidence.get("error"):
            raise ValueError(evidence["error"])
        observed = object_value(evidence["observed"], "native observation")
        require_bars = wanted.get("require_resource_bars", False)
        if require_bars:
            result["threshold"] += "; five native bars at target (1e-4) and stable (1e-5) on three distinct frames"
            check_bar_settlement(evidence)
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
                "resource_bars_required": require_bars,
                "resource_bars_verified": require_bars,
            },
            detail="; ".join(problems) if problems else "native listing and rendered selection reviewed",
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result.update(status="fail", detail=f"requested panel evidence unavailable/invalid: {exc}")
    return result
