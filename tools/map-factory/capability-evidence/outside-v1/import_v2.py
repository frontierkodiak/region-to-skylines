"""Append diagnostic receipts without replacing any historical attempt or raw file."""

import argparse
import gzip
import json
from pathlib import Path

from annotate import annotations, summary
from assemble import HERE, assemble


def import_attempts(native, reproduction, attempt_id):
    path = HERE / "evidence.json"
    evidence = json.loads(path.read_text())
    versions = json.loads((HERE / "collector-versions.json").read_text())["versions"]
    evidence["collector_versions"] = versions
    if any(
        a["attempt_id"] == attempt_id
        for c in evidence["artifacts"]
        for a in c["attempts"]
    ):
        raise ValueError("attempt identity already imported")
    incoming = assemble(
        json.loads((HERE / "selection.json").read_text()),
        native,
        reproduction,
        attempt_id,
    )
    by_slug = {c["slug"]: c for c in evidence["artifacts"]}
    observed = {c["slug"] for c in incoming["artifacts"] if c["observation_evidence"]}
    for case in incoming["artifacts"]:
        if case["slug"] not in observed:
            continue
        if "queue-cancel.json" in case["native_evidence"]:
            event = json.loads(
                gzip.decompress(
                    (
                        HERE / case["native_evidence"]["queue-cancel.json"]["path"]
                    ).read_bytes()
                )
            )
            if case["completed"] or event["native_observation"] is not False:
                raise ValueError(
                    "queue cancellation cannot replace a completed native observation"
                )
            case["error"] = event["reason"]
        target = by_slug[case["slug"]]
        target["attempts"].append(
            {
                "attempt_id": attempt_id,
                **{
                    key: case[key]
                    for key in [
                        "artifact_sha256",
                        "observation_evidence",
                        "native_evidence",
                        "completed",
                        "error",
                    ]
                },
            }
        )
        target["completed"] = any(a["completed"] for a in target["attempts"])
        target["error"] = None if target["completed"] else case["error"]
    evidence["rows"].extend(
        row
        for row in incoming["rows"]
        if row["slug"] in observed
        and row["oracle_type"] in {"native_path", "native_new_game_panel"}
        and "archive_context" not in row
    )
    evidence = annotations(evidence)
    markdown, cells = summary(evidence)
    path.write_text(json.dumps(evidence, indent=2) + "\n")
    (HERE / "RESULTS.md").write_text(markdown)
    (HERE / "capability-summary.json").write_text(json.dumps(cells, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--reproduction", type=Path, required=True)
    parser.add_argument("--attempt-id", required=True)
    args = parser.parse_args()
    import_attempts(args.native, args.reproduction, args.attempt_id)
