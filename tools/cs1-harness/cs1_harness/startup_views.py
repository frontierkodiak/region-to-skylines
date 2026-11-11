"""Opt-in, un-aimed opening and actual GameAreaTool heading evidence.

Native readings establish headings, not screenshot content. Content claims
require a separate visual review bound to both captured PNG hashes.
"""

from __future__ import annotations

import json
import pathlib
import time

from PIL import Image, ImageStat

from .client import HarnessError
from .landmarks import SOURCE, number
from .new_game_panel import digest, object_value, wait_for_capture

PHASE = "startup_before_harness_camera_overrides"
VIEWS = ("opening", "area_zoom")
STABLE_SAMPLES = 3
STABLE_DEGREES = 0.1


def expectations(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) != {*VIEWS, "tolerance_degrees"}:
        raise ValueError("startup_views requires opening, area_zoom and tolerance_degrees")
    tolerance = value["tolerance_degrees"]
    if not number(tolerance) or not 0 < tolerance <= 5:
        raise ValueError("startup_views tolerance_degrees must be in (0, 5]")
    for name in VIEWS:
        view = value[name]
        if not isinstance(view, dict) or set(view) != {"native_yaw_degrees", "render_heading_degrees"}:
            raise ValueError(f"startup_views {name} needs explicit native_yaw_degrees and render_heading_degrees")
        if any(not number(v) or not -360 <= v <= 360 for v in view.values()):
            raise ValueError("startup_views headings must be finite degrees in [-360, 360]")
    return value


def request(out: pathlib.Path) -> dict | None:
    """Use only the frozen probe request, never the original mutable probe file."""
    path = out / "probes.json"
    data = json.loads(path.read_text()) if path.is_file() else {}
    if not isinstance(data, dict) or "startup_views" not in data:
        return None
    return expectations(data["startup_views"])


def angle_error(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


def headings(observation: dict, visible: bool) -> tuple[float, float]:
    observation = object_value(observation, "world observation")
    if observation.get("source") != SOURCE or type(observation.get("frame")) is not int:
        raise ValueError("missing native world provenance/frame")
    camera = object_value(observation.get("camera"), "native camera")
    if camera.get("areas_visible") is not visible:
        raise ValueError(f"native AreasVisible must be {visible}")
    angles = camera.get("current_angle_degrees")
    render = camera.get("render_heading_degrees")
    if not isinstance(angles, list) or len(angles) != 2 or not all(number(v) for v in angles) or not number(render):
        raise ValueError("native/render heading unavailable or nonfinite")
    return angles[0], render


def stable(samples: list[dict], visible: bool) -> bool:
    if len(samples) != STABLE_SAMPLES:
        return False
    values = [headings(sample, visible) for sample in samples]
    return all(angle_error(a, b) <= STABLE_DEGREES for pair in values[1:] for a, b in zip(values[0], pair))


def settle(session, visible: bool, timeout: float) -> list[dict]:
    """Wait for the native mode and three stable native/render heading reads."""
    deadline = time.monotonic() + timeout
    samples = []
    while True:
        if session.alive() is False:
            raise HarnessError("game ended during startup view capture")
        sample = session.client.call("world_observe")
        if sample.get("camera", {}).get("areas_visible") is visible:
            headings(sample, visible)
            samples = (samples + [sample])[-STABLE_SAMPLES:]
            if stable(samples, visible):
                return samples
        else:
            samples = []
        if time.monotonic() >= deadline:
            raise HarnessError(f"startup view did not settle with AreasVisible={visible}")
        time.sleep(0.25)


def capture_view(session, name: str, timeout: float) -> dict:
    visible = name == "area_zoom"
    samples = settle(session, visible, timeout)
    shot = session.stage / f"startup-{name}.png"
    capture = session.client.call("screenshot", path=str(shot))
    sha256 = wait_for_capture(session, shot, timeout=timeout)
    after = session.client.call("world_observe")
    headings(after, visible)
    if not stable(samples[-2:] + [after], visible):
        raise HarnessError(f"{name} heading moved during screenshot capture")
    with Image.open(shot) as image:
        size = list(image.size)
    return {
        "samples": samples,
        "after": after,
        "screenshot": shot.name,
        "sha256": sha256,
        "size": size,
        "capture": capture,
    }


def capture(session, out: pathlib.Path, wanted: dict, timeout: float = 15) -> dict:
    """Run after startup-world, before any harness camera op; always close Areas."""
    expectations(wanted)
    receipt = {"phase": PHASE, "startup_world_sha256": digest(out / "startup-world.json"), "views": {}}
    paused = None
    try:
        initial = json.loads((out / "startup-world.json").read_text())
        if initial.get("phase") != PHASE:
            raise ValueError("not an untouched startup observation")
        headings(initial, False)
        paused = session.client.call("stats")["paused"]
        session.client.call("run", paused=True)
        receipt["views"]["opening"] = capture_view(session, "opening", timeout)
        receipt["open"] = session.client.call("area_zoom", enabled=True)
        receipt["views"]["area_zoom"] = capture_view(session, "area_zoom", timeout)
    except Exception as exc:
        receipt["error"] = str(exc)
        raise
    finally:
        try:
            if session.alive() is False:
                raise HarnessError("game ended before Areas cleanup")
            receipt["close"] = session.client.call("area_zoom", enabled=False)
            receipt["closed_samples"] = settle(session, False, timeout)
        except Exception as exc:
            receipt["cleanup_error"] = str(exc)
            raise
        finally:
            try:
                if paused is not None and session.alive() is not False:
                    session.client.call("run", paused=paused)
            finally:
                (out / "startup-views.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def assess(out: pathlib.Path) -> dict:
    row = {
        "name": "startup_views",
        "status": "skip",
        "value": None,
        "threshold": "untouched opening + native Areas tool; explicit heading tolerance + hash-bound PNG review",
        "detail": "not requested",
    }
    try:
        wanted = request(out)
        if wanted is None:
            return row
        evidence = object_value(json.loads((out / "startup-views.json").read_text()), "startup views")
        if evidence.get("phase") != PHASE or evidence.get("error") or evidence.get("cleanup_error"):
            raise ValueError("wrong startup phase or capture/cleanup failure")
        if evidence.get("startup_world_sha256") != digest(out / "startup-world.json"):
            raise ValueError("startup-world identity changed")
        initial = object_value(json.loads((out / "startup-world.json").read_text()), "startup world")
        if initial.get("phase") != PHASE:
            raise ValueError("startup world was captured after camera overrides")
        initial_headings = headings(initial, False)
        for key, tool, visible in (("open", "GameAreaTool", True), ("close", "DefaultTool", False)):
            control = object_value(evidence.get(key), key)
            if (
                control.get("source") != "native ToolsModifierControl"
                or control.get("tool") != tool
                or control.get("areas_visible") is not visible
            ):
                raise ValueError(f"missing actual native {tool} transition")
        if not stable(evidence["closed_samples"], False):
            raise ValueError("Areas tool was not closed and settled")
        review_path = out / "startup-views-review.json"
        review = object_value(json.loads(review_path.read_text()), "visual review") if review_path.is_file() else {}
        problems, measured = [], {}
        if not review.get("reviewer") or not review.get("notes"):
            problems.append("screenshots unreviewed (requires reviewer and notes)")
        for name in VIEWS:
            view = object_value(evidence["views"][name], name)
            visible = name == "area_zoom"
            samples = view["samples"]
            if not stable(samples, visible) or not stable(samples[-2:] + [view["after"]], visible):
                raise ValueError(f"{name} native/render headings did not settle")
            values = [headings(sample, visible) for sample in samples + [view["after"]]]
            if name == "opening":
                values.append(initial_headings)
            expected = wanted[name]
            for native, render in values:
                if (
                    angle_error(native, expected["native_yaw_degrees"]) > wanted["tolerance_degrees"]
                    or angle_error(render, expected["render_heading_degrees"]) > wanted["tolerance_degrees"]
                ):
                    problems.append(f"{name} native/render heading outside explicit tolerance")
                    break
            filename = f"startup-{name}.png"
            if view["screenshot"] != filename:
                raise ValueError(f"wrong {name} screenshot identity")
            shot = out / filename
            if digest(shot) != view["sha256"]:
                raise ValueError(f"{name} screenshot changed since capture")
            capture = object_value(view["capture"], "native screenshot receipt")
            if pathlib.Path(capture["path"]).name != filename or type(capture.get("frame")) is not int:
                raise ValueError(f"{name} native screenshot metadata missing/mismatched")
            if (
                not initial["frame"]
                <= samples[0]["frame"]
                <= samples[-1]["frame"]
                <= capture["frame"]
                <= view["after"]["frame"]
            ):
                raise ValueError(f"{name} screenshot/world frames out of order")
            with Image.open(shot) as image:
                if image.format != "PNG":
                    raise ValueError(f"{name} screenshot is not PNG")
                image.verify()
            with Image.open(shot) as image:
                image.load()
                if list(image.size) != view["size"] or ImageStat.Stat(image.convert("L")).stddev[0] < 3:
                    raise ValueError(f"{name} screenshot dimensions mismatch or blank")
            visual = object_value(review.get(name, {}), f"{name} visual review")
            if (
                visual.get("sha256") != view["sha256"]
                or visual.get("view_matches") is not True
                or visual.get("areas_ui_visible") is not visible
            ):
                problems.append(f"{name} screenshot content unreviewed/mismatched")
            measured[name] = {
                "native_yaw_degrees": values[0][0],
                "render_heading_degrees": values[0][1],
                "screenshot": filename,
                "sha256": view["sha256"],
            }
        row.update(
            status="fail" if problems else "pass",
            value={"views": measured, "problems": problems},
            detail="; ".join(problems) if problems else "native headings and actual opening/Areas PNGs reviewed",
        )
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        row.update(status="fail", detail=f"requested startup view evidence unavailable/invalid: {exc}")
    return row
