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
                roles.append(
                    [
                        f
                        for f in flags.split(", ")
                        if f in {"Outside", "OneWayIn", "OneWayOut"}
                    ]
                )
            row["endpoint_roles"] = roles
            generic = request["name"] == "outside-to-outside"
            two_edge = all("Outside" in role for role in roles)
            row["probe_kind"] = (
                "generic_pair"
                if generic
                else "legacy_two_edge"
                if two_edge
                else "legacy_access_leg"
            )
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
        "Fresh two-edge positives, access legs, archived player paths and panels are separate below.",
        "Every failed request remains a pair/lane observation, not a native capability negative. Missing or unexhausted coverage is unknown.",
        "All nine water-risk screens remain **warnings**. No native depth, width or grade threshold is fitted.",
        "Ship witnesses are sampled native paths, not terminal service, continuous clearance or sustained water safety.",
        "",
        "| Square / mode | Fresh two-edge | Access positives | Archived positives | Panel observations |",
        "| --- | --- | --- | --- | --- |",
    ]
    cells = []
    for case in evidence["artifacts"]:
        for mode in ["road", "rail", "ship", "air"]:
            rows = [
                r
                for r in evidence["rows"]
                if r["slug"] == case["slug"] and r["capability_id"] == mode
            ]
            fresh = [
                r
                for r in rows
                if r.get("probe_kind") in {"generic_pair", "legacy_two_edge"}
            ]
            positive = any(r["observed"] is True for r in fresh)
            access = sum(
                r["observed"] is True
                for r in rows
                if r.get("probe_kind") == "legacy_access_leg"
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
                    "access_positives": access,
                    "archived_positives": archived,
                }
            )
            lines.append(
                f"| {case['slug']} / {mode} | {'witness' if positive else 'unknown'} ({failed} failed) | {access} | {archived} | {panels} |"
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
