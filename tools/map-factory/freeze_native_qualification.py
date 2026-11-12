"""Record native identities for fixtures from completed native evidence.

This authoring command reads the actual map, first native grids and reviewed
strict-vanilla images. It does not turn failed checks into passes.
"""

import argparse
import hashlib
import json
from pathlib import Path

from audit_soak import audit

REGIONS = ["asheville", "innsbruck", "rio", "pittsburgh", "charleston"]
EMPTY = {"game": [], "steam_instances": [], "units_active": []}


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value_digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def freeze(root, output, issue="PL-918"):
    cases = []
    for slug in REGIONS:
        run, captured = root / "soaks" / slug, root / "captures" / slug
        prepared = captured / "out"
        report, capture = read(run / "report.json"), read(captured / "capture.json")
        native = report["session"]["map"]
        if (
            digest(Path(native["source"])) != native["sha256"]
            or native["sha256"] != capture["cli_sha256"]
        ):
            raise ValueError(f"Native map is not the captured CLI map: {slug}")
        if report["game_minutes"] < 60 or report["session"]["cleanup"] != EMPTY:
            raise ValueError(f"Native soak incomplete or not cleaned up: {slug}")
        measured = audit(run, prepared, captured / "geometry.json")
        if not all(
            measured[k]
            for k in ["terrain_exact", "initial_water_exact", "source_controls_match"]
        ):
            raise ValueError(
                f"Native initial state differs from prepared state: {slug}"
            )
        grids = {}
        for name in ["terrain.u16", "water.u16"]:
            native_grid = run / "grids" / (report["first_dump"] + "-" + name)
            grids[name] = digest(native_grid)
            if grids[name] != digest(prepared / name):
                raise ValueError(f"Native grid mismatch: {slug}/{name}")
        prefix = root / (issue + "-vanilla-" + slug)
        validation_file = prefix.with_name(prefix.name + "-validation.json")
        review_file = prefix.with_name(prefix.name + "-review.json")
        validation, review = read(validation_file), read(review_file)
        if validation["map_sha256"] != native["sha256"] or not all(
            validation[k]
            for k in [
                "strict_disableMods",
                "noWorkshop",
                "control_socket_absent",
                "ordinary_new_game_loaded",
                "city_toolbar_observed",
            ]
        ):
            raise ValueError(f"Strict vanilla proof is not this map: {slug}")
        if not review.get("reviewer") or not review.get("notes"):
            raise ValueError(f"Missing strict visual review: {slug}")
        for phase in ["selected", "city"]:
            image = prefix.with_name(prefix.name + "-" + phase + ".png")
            if (
                review[phase].get("sha256") != digest(image)
                or review[phase].get("content_matches") is not True
            ):
                raise ValueError(f"Unreviewed strict image: {slug}/{phase}")
        cleanup = read(
            prefix.with_name(prefix.name + "-session") / "session-receipt.json"
        )
        if cleanup["cleanup"] != EMPTY:
            raise ValueError(f"Strict vanilla session not cleaned up: {slug}")
        hydro = read(prepared / "hydrology.json")
        samples = (
            json.loads(line)
            for line in (run / "timeline.jsonl").read_text().splitlines()
        )
        initial = next(row for row in samples if row["kind"] == "sample")
        if abs(initial["water"]["sea_level"] - hydro["sea_level_m"]) > 1 / 64:
            raise ValueError(f"Native sea level differs: {slug}")
        verdict = read(run / "verdict.json")
        cases.append(
            {
                "slug": slug,
                "native_crp_sha256": native["sha256"],
                "harness_commit": report["harness"]["commit"],
                "game_minutes": report["game_minutes"],
                "verdict": verdict["verdict"],
                "failed_checks": verdict["failed"],
                "prepared_sha256": grids,
                "water_sources_sha256": value_digest(hydro["sources"]),
                "node_positions_sha256": value_digest(hydro["node_positions"]),
                "start_tile": hydro["start_tile"],
                "sea_level_m": hydro["sea_level_m"],
                "template_sha256": capture["source_files_sha256"][
                    "tools/map-factory/templates/native-corridors.crp"
                ],
                "layout_sha256": capture["source_files_sha256"][
                    "tools/map-factory/templates/native-corridors.json"
                ],
                "report_sha256": digest(run / "report.json"),
                "verdict_sha256": digest(run / "verdict.json"),
                "strict_validation_sha256": digest(validation_file),
                "strict_review_sha256": digest(review_file),
            }
        )
    output.write_text(
        json.dumps(
            {
                "format": 1,
                "issue": issue,
                "scope": "exact native maps; terrain/water/controls identity required for resource-only carryover",
                "cases": cases,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--issue",
        default="PL-918",
        help="issue key and vanilla evidence prefix (default: PL-918)",
    )
    args = parser.parse_args()
    freeze(args.root.resolve(), args.output, args.issue)
