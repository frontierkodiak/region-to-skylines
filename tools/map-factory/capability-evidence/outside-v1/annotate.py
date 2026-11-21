"""Re-derive fresh rows and annotate historical requests without changing raw files."""

import functools
import gzip
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def raw(ref):
    return raw_path(ref["path"])


@functools.cache
def raw_path(path):
    return json.loads(gzip.decompress((HERE / path).read_bytes()))


def path_endpoints(request, result, segments):
    boundary_nodes = []
    for endpoint in [request["from"], request["to"]]:
        segment, _, offset = endpoint
        key = "start" if offset == 0 else "end" if offset == 255 else None
        item = segments.get(segment, {})
        boundary_nodes.append(
            item.get(key)
            if key and "Outside" in item.get(key + "_flags", "").split(", ")
            else None
        )
    positions = result.get("positions", [])
    returned_match = bool(
        len(positions) >= 2
        and positions[0] == request["from"]
        and positions[-1] == request["to"]
    )
    boundary = (
        None not in boundary_nodes
        and boundary_nodes[0] != boundary_nodes[1]
        and request["from"][0] != request["to"][0]
    )
    return boundary, returned_match


def annotations(evidence):
    versions = {
        v["collector_sha256"]: v["protocol"] for v in evidence["collector_versions"]
    }
    attempts = {}
    for case in evidence["artifacts"]:
        for attempt in case["attempts"]:
            attempts[attempt["observation_evidence"]["path"]] = attempt
    for row in evidence["rows"]:
        if row["oracle_type"] in {"generated_connection", "native_new_game_panel"}:
            if row.get("counts") is not None:
                row["observed"] = all(row["counts"])
            if row.get("expected_counts") is not None:
                row["prediction"] = all(row["expected_counts"])
            if (
                row["capability_id"] == "rail"
                and row["oracle_type"] == "native_new_game_panel"
            ):
                row["counts_match"] = None
                row["counts_limitation"] = (
                    "Authored train_tracks is not independent directional panel counts."
                )
        if row["oracle_type"] != "native_path":
            continue
        row["capability_observed"] = (
            True if row["observed"] is True and "archive_context" not in row else None
        )
        row["capability_reason"] = (
            "sampled_positive" if row["capability_observed"] else "probe_limited"
        )
        if "archive_context" in row:
            row.update(
                probe_kind="archived_player_path",
                collector_sha256=None,
                protocol="Archived first-hour player run; not a fresh unchanged-map witness",
                reason=None if row["observed"] is not None else "not_run",
            )
            continue
        ref = row.get("raw_evidence")
        observation = raw(ref) if ref else {}
        row["native_context"] = observation.get("native_context")
        row["protocol_basis"] = (
            "observed_native_context"
            if row["native_context"]
            else "collector_recipe_only_not_observed_entry_state"
        )
        row["runtime_bound"] = bool(
            observation.get("runtime_identity", {}).get("build_matches")
        )
        row["collector_sha256"] = observation.get("collector_sha256")
        row["protocol"] = observation.get("protocol") or versions.get(
            row["collector_sha256"], "not_run"
        )
        attempt = attempts.get(ref["path"]) if ref else None
        netref = attempt["native_evidence"].get("networks.json") if attempt else None
        networks = raw(netref) if netref else {"segments": []}
        segments = {s["id"]: s for s in networks["segments"]}
        request = row.get("request")
        roles = []
        edges = []
        if request:
            for endpoint in [request["from"], request["to"]]:
                segment = segments.get(endpoint[0], {})
                flags = segment.get(
                    "start_flags"
                    if endpoint[2] == 0
                    else "end_flags"
                    if endpoint[2] == 255
                    else "",
                    "",
                )
                # Midpoints retain the outside node role of their segment.
                if endpoint[2] == 128:
                    flags = next(
                        (
                            segment[k]
                            for k in ["start_flags", "end_flags"]
                            if "Outside" in segment.get(k, "").split(", ")
                        ),
                        "",
                    )
                edge = None
                for key, position in [("start_flags", "a"), ("end_flags", "b")]:
                    if "Outside" in segment.get(key, "").split(", "):
                        x, _, z = segment[position]
                        edge = (
                            ("east" if x > 0 else "west")
                            if abs(x) > abs(z)
                            else ("north" if z > 0 else "south")
                        )
                        break
                edges.append(edge)
                roles.append(
                    [
                        f
                        for f in flags.split(", ")
                        if f in {"Outside", "OneWayIn", "OneWayOut"}
                    ]
                )
            row["endpoint_roles"] = roles
            row["endpoint_edges"] = edges
            generic = request["name"] == "outside-to-outside"
            two_edge = all("Outside" in role for role in roles)
            row["probe_kind"] = (
                "generic_pair"
                if generic
                else "legacy_two_edge"
                if two_edge
                else "legacy_access_leg"
            )
            if two_edge and edges[0] == edges[1]:
                row["probe_kind"] = "outside_same_edge"
                row["capability_observed"] = None
                row["capability_reason"] = "same_edge_only"
            if not two_edge:
                row["capability_observed"] = None
                row["capability_reason"] = "access_leg_only"
            row["reason"] = None if row["observed"] is not None else "not_run"
            row["pair_status"] = (
                "same_role_probe_limited"
                if row["capability_id"] == "road" and roles[0] == roles[1]
                else "candidate_only"
            )
        else:
            row["endpoint_roles"] = None
            row["endpoint_edges"] = None
            row["probe_kind"] = "not_requested"
            vehicle = {"road": "Car", "rail": "Train", "ship": "Ship", "air": "Plane"}[
                row["capability_id"]
            ]
            lanes = [
                lane
                for s in segments.values()
                for lane in s["lanes"]
                if vehicle in lane["vehicle"].split(", ")
            ]
            row["reason"] = (
                "not_run"
                if not observation.get("completed")
                else "no_pair"
                if lanes
                else "no_lane"
            )
        row["literal_boundary_request"] = False
        row["literal_boundary_witness"] = False
        row["returned_endpoints_match_request"] = None
        row["midpoint_segment_witness"] = False
        if request:
            boundary, returned_match = path_endpoints(
                request, row.get("path_result") or {}, segments
            )
            row["literal_boundary_request"] = boundary and edges[0] != edges[1]
            row["returned_endpoints_match_request"] = returned_match
            row["literal_boundary_witness"] = (
                row["literal_boundary_request"]
                and returned_match
                and row["observed"] is True
            )
            row["midpoint_segment_witness"] = (
                two_edge
                and edges[0] != edges[1]
                and returned_match
                and all(p[2] == 128 for p in [request["from"], request["to"]])
                and row["observed"] is True
            )
        row["capability_observed"] = True if row["literal_boundary_witness"] else None
        if row["literal_boundary_witness"]:
            row["capability_reason"] = "sampled_literal_boundary_positive"
        elif row["midpoint_segment_witness"]:
            row["capability_reason"] = "midpoint_segment_diagnostic_only"
        if (
            not request
            and observation.get("schema", 1) >= 2
            and row["capability_id"]
            not in observation.get("requested_capabilities", [])
        ):
            row["reason"] = "not_run"
    return evidence


def summary(evidence):
    lines = [
        "# Outside-connection evidence",
        "",
        "Literal boundary witnesses require requested outside offsets and identical returned first/last path positions. Segment-midpoint successes are separate, unscored diagnostics.",
        "Every failed request remains a pair/lane observation, not a native capability negative. Missing or unexhausted coverage is unknown.",
        "All nine water-risk screens remain **warnings**. No native depth, width or grade threshold is fitted.",
        "Ship witnesses are sampled native paths, not terminal service, continuous clearance or sustained water safety.",
        "",
        "| Square / mode | Literal boundary | Runtime-bound boundary | Midpoint positives | Same-edge positives | Access positives | Archived positives | Panel observations |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    cells = []
    for case in evidence["artifacts"]:
        for mode in ["road", "rail", "ship", "air"]:
            rows = [
                r
                for r in evidence["rows"]
                if r["slug"] == case["slug"] and r["capability_id"] == mode
            ]
            fresh = [r for r in rows if r.get("literal_boundary_request")]
            positive = any(r["literal_boundary_witness"] for r in fresh)
            bound = any(
                r["literal_boundary_witness"] and r.get("runtime_bound") for r in fresh
            )
            midpoint = sum(r.get("midpoint_segment_witness", False) for r in rows)
            access = sum(
                r["observed"] is True
                for r in rows
                if r.get("probe_kind") == "legacy_access_leg"
            )
            same_edge = sum(
                r["observed"] is True
                for r in rows
                if r.get("probe_kind") == "outside_same_edge"
            )
            archived = sum(
                r["observed"] is True
                for r in rows
                if r.get("probe_kind") == "archived_player_path"
            )
            panels = sum(
                r["observed"] is not None
                for r in rows
                if r["oracle_type"] == "native_new_game_panel"
            )
            failed = sum(r["observed"] is False for r in fresh)
            cells.append(
                {
                    "slug": case["slug"],
                    "capability": mode,
                    "observed": True if positive else None,
                    "reason": "sampled_two_edge_positive"
                    if positive
                    else "probe_limited"
                    if fresh
                    else "not_run",
                    "fresh_failed_requests": failed,
                    "runtime_bound_two_edge": bound,
                    "same_edge_positives": same_edge,
                    "midpoint_positives": midpoint,
                    "access_positives": access,
                    "archived_positives": archived,
                }
            )
            lines.append(
                f"| {case['slug']} / {mode} | {'witness' if positive else 'unknown'} ({failed} failed) | {'witness' if bound else 'unknown'} | {midpoint} | {same_edge} | {access} | {archived} | {panels} |"
            )
    lines += ["", "## Retained attempt errors", ""]
    lines += [
        f"- {c['slug']} {a['attempt_id']}: {a['error']}"
        for c in evidence["artifacts"]
        for a in c["attempts"]
        if a["error"]
    ]
    return "\n".join(lines) + "\n", cells


if __name__ == "__main__":
    path = HERE / "evidence.json"
    evidence = annotations(json.loads(path.read_text()))
    path.write_text(json.dumps(evidence, indent=2) + "\n")
    markdown, cells = summary(evidence)
    (HERE / "RESULTS.md").write_text(markdown)
    (HERE / "capability-summary.json").write_text(json.dumps(cells, indent=2) + "\n")
