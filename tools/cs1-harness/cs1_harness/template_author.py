"""Explicit disposable MapEditor template authoring; never starts a session.

First inspect the loaded editor's actual plane prefab choices. An explicit plan
can be dry-run, then applied/exported only with --apply. Output is an unpublished
experimental template, never automatically adopted by the map writer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import re
import time

from .client import Client, HarnessError


def validate_plan(plan: dict) -> dict:
    if not isinstance(plan, dict) or set(plan) != {"prefab", "endpoints"}:
        raise ValueError("plan requires exactly prefab and endpoints")
    if not isinstance(plan["prefab"], str) or not plan["prefab"].strip():
        raise ValueError("choose an explicit native prefab from template_status")
    points = plan["endpoints"]
    if not isinstance(points, list) or len(points) != 2:
        raise ValueError("two [x,z] endpoints are required")
    for point in points:
        if (
            not isinstance(point, list)
            or len(point) != 2
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in point)
            or not 8600 <= max(map(abs, point)) <= 8640
        ):
            raise ValueError("finite endpoints must be at native +/-8640 map edges")
    a, b = points
    axis = 0 if abs(a[0]) >= abs(a[1]) else 1
    if a[axis] * b[axis] >= 0 or abs(b[axis]) < 8600 or abs(a[1 - axis]) > 8000 or abs(b[1 - axis]) > 8000:
        raise ValueError("use opposite edges, clear of ambiguous map corners")
    return plan


def graph_evidence(before: dict, after: dict, ready: bool = True) -> dict:
    """Validate native IDs and AI/lane types, not a both-ends-outside heuristic."""
    old_nodes = {n["id"]: n for n in before["graph"]["nodes"]}
    old_segments = {s["id"]: s for s in before["graph"]["segments"]}
    nodes = {n["id"]: n for n in after["graph"]["nodes"]}
    segments = {s["id"]: s for s in after["graph"]["segments"]}
    for kind, old, new in [("node", old_nodes, nodes), ("segment", old_segments, segments)]:
        if any(new.get(k) != v for k, v in old.items()):
            raise ValueError(f"original {kind} inventory changed")
    for kind in ["road", "rail", "ship"]:
        if before["graph"]["outside_counts"][kind] != after["graph"]["outside_counts"][kind]:
            raise ValueError(f"original {kind} outside counts changed")
    added_nodes = {k: v for k, v in nodes.items() if k not in old_nodes}
    added_segments = {k: v for k, v in segments.items() if k not in old_segments}
    for item in [*added_nodes.values(), *added_segments.values()]:
        info = item["prefab"]
        if (
            info.get("native_plane") is not True
            or info.get("ai") != "FlightPathAI"
            or info.get("subservice") != "PublicTransportPlane"
        ):
            raise ValueError("new graph contains a non-native-plane prefab")
    for segment in added_segments.values():
        if segment["from"] not in added_nodes or segment["to"] not in added_nodes:
            raise ValueError("air path touches the original graph")
        if not segment["lane_ids"] or not any(
            "Plane" in lane["vehicle_types"].split(", ") for lane in segment["prefab"]["lanes"]
        ):
            raise ValueError("native air segment has no real plane lanes")
    outside = [n for n in added_nodes.values() if n["outside"]]
    air = after["graph"]["outside_counts"]["air"]
    if ready:
        if not added_segments or len(outside) != 2 or any(not n["outside_building_id"] for n in outside):
            raise ValueError("native air graph/outside buildings not ready")
        if min(air["incoming"], air["outgoing"]) < 1:
            raise ValueError("native incoming/outgoing plane counts not ready")
        seen, pending = set(), [outside[0]["id"]]
        while pending:
            node = pending.pop()
            if node in seen:
                continue
            seen.add(node)
            for segment in added_segments.values():
                if segment["from"] == node:
                    pending.append(segment["to"])
                if segment["to"] == node:
                    pending.append(segment["from"])
        if seen != set(added_nodes):
            raise ValueError("native air graph is disconnected")
    return {
        "new_nodes": list(added_nodes.values()),
        "new_segments": list(added_segments.values()),
        "outside_counts": after["graph"]["outside_counts"],
        "original_inventory_preserved": True,
    }


def poll(client, wanted, timeout):
    deadline = time.monotonic() + timeout
    while True:
        status = client.call("template_status")
        if status.get("error") or status.get("state") == "failed_discard_editor":
            raise HarnessError(f"template authoring failed; discard editor without saving: {status.get('error')}")
        if wanted(status):
            return status
        if time.monotonic() >= deadline:
            raise HarnessError("template operation timed out; do not adopt or save partial template")
        time.sleep(0.25)


def author(
    client, source, out, plan=None, apply=False, export_name=None, map_name=None, timeout=60, continue_editor=False
):
    """Caller owns an idle, dedicated harness main-menu session and its teardown."""
    if plan is not None:
        validate_plan(plan)
    if apply and (plan is None or not export_name or not map_name):
        raise ValueError("apply requires an explicit plan and new export/map names")
    if apply and (
        not re.fullmatch(r"air-template-[A-Za-z0-9_-]{1,64}", export_name)
        or not isinstance(map_name, str)
        or not map_name.strip()
    ):
        raise ValueError("apply requires a safe new air-template-... basename and nonempty map name")
    out.mkdir(parents=True, exist_ok=True)
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    opened = (
        client.call("template_status") if continue_editor else client.call("template_open", path=str(source.resolve()))
    )
    if opened["source_sha256"] != expected:
        raise ValueError("native installed source differs from the requested template")
    if not continue_editor:
        client.wait(lambda st: st.get("loading_complete") and not st.get("loading"), timeout, "MapEditor to load")
    before = client.call("template_status")
    (out / "before.json").write_text(json.dumps(before, indent=2) + "\n")
    if plan is None:
        return before
    if plan["prefab"] not in {p["prefab"] for p in before["plane_prefabs"]}:
        raise ValueError("requested prefab is not among native Plane FlightPathAI candidates")
    client.call("run", paused=True)
    client.call("template_air", **plan, apply=False)
    checked = poll(client, lambda st: st.get("state") == "checked", timeout)
    if checked["graph"] != before["graph"]:
        raise ValueError("native dry run changed the graph; discard editor")
    (out / "dry-run.json").write_text(json.dumps(checked, indent=2) + "\n")
    if not apply:
        return checked
    client.call("template_air", **plan, apply=True)
    after = poll(client, lambda st: st.get("state") == "authored", timeout)
    # Building creation/flags are native deferred updates. Never make them up.
    after = poll(
        client, lambda st: all(st["graph"]["outside_counts"]["air"][d] > 0 for d in ["incoming", "outgoing"]), timeout
    )
    evidence = graph_evidence(before, after)
    exported = client.call("template_export", name=export_name, map_name=map_name)
    saved = poll(client, lambda st: not st.get("saving") and bool(st.get("export_sha256")), timeout)
    evidence = graph_evidence(before, saved)
    path = pathlib.Path(exported["path"])
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if sha != saved["export_sha256"]:
        raise ValueError("exported package hash differs from native save receipt")
    receipt = {
        "schema": 1,
        "source_sha256": expected,
        "export_sha256": sha,
        "export_file": path.name,
        "plan": plan,
        "native_graph": evidence,
        "native_before": before,
        "native_after": saved,
        "writer_adopted": False,
        "native_new_game_verified": False,
        "note": "native editor export only; not a descriptor or ready-to-play certificate",
    }
    (out / "air-template.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=pathlib.Path, help="already installed template in the dedicated session")
    parser.add_argument("out", type=pathlib.Path)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--plan", type=pathlib.Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--continue-editor",
        action="store_true",
        help="continue this helper's exact source-bound editor after inspection",
    )
    parser.add_argument("--export-name")
    parser.add_argument("--map-name")
    args = parser.parse_args()
    result = author(
        Client(args.port),
        args.source,
        args.out,
        json.loads(args.plan.read_text()) if args.plan else None,
        args.apply,
        args.export_name,
        args.map_name,
        continue_editor=args.continue_editor,
    )
    print(
        json.dumps(
            {k: result[k] for k in ["source_sha256", "export_sha256", "writer_adopted"] if k in result}, indent=2
        )
    )


if __name__ == "__main__":
    main()
