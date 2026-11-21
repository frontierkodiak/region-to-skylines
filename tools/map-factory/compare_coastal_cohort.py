"""Follow the fixed, previously lost development probes through an intervention.

This outcome-selected historical cohort is diagnostic, not a maintained-water
inventory, unbiased panel, native qualification, or new acceptance definition.
"""

import argparse
from collections import Counter
import json
from pathlib import Path

from water_risk_corpus import sha


def compare(audit_path, baseline, intervention, receipt_path):
    audit = json.loads(audit_path.read_text())
    receipt = json.loads(receipt_path.read_text())
    for directory, binding in [
        (baseline, receipt["baseline_files_sha256"]),
        (intervention, receipt["native_files_sha256"]),
    ]:
        if any(
            sha(directory / name) != binding[name]
            for name in ("report.json", "probes.json")
        ):
            raise ValueError("Comparison does not match the validated native receipt")
    if audit["files"]["native_report"]["sha256"] != sha(
        baseline / "report.json"
    ) or audit["files"]["native_probes"]["sha256"] != sha(baseline / "probes.json"):
        raise ValueError("Static cohort belongs to a different native baseline")

    def key(point):
        return point["name"], point["x"], point["z"]

    def points(directory):
        rows = json.loads((directory / "report.json").read_text())["points"]
        indexed = {key(p): p for p in rows}
        if len(rows) != len(indexed):
            raise ValueError("Duplicate native probe identity")
        return indexed

    before, after = points(baseline), points(intervention)
    cohort = audit["static_ocean_connectivity"]["probes"]
    if len(cohort) != audit["static_ocean_connectivity"]["lost_probe_count"]:
        raise ValueError("Static cohort count differs")
    groups = {}
    for old in cohort:
        identity = key(old)
        if identity not in before or identity not in after:
            raise ValueError("A fixed cohort probe is missing from a native report")
        original, current = before[identity], after[identity]
        if (
            not original["wet_start"]
            or original["wet_end"]
            or original["wet_within_64m_end"]
        ):
            raise ValueError("Historical cohort no longer represents its stated loss")
        name = old["name"].removeprefix("geography:").split(" [", 1)[0]
        group = groups.setdefault(name, Counter())
        group["baseline_lost"] += 1
        for neighbours in (4, 8):
            group[f"baseline_static_ocean_connected_{neighbours}"] += int(
                old["ocean_connected"][str(neighbours)]
            )
        endpoint = current["wet_end"] or current["wet_within_64m_end"]
        group["intervention_wet_end"] += int(endpoint)
        group["intervention_dry_end"] += int(not endpoint)
        group["intervention_wet_throughout"] += int(
            current["nearby_samples"] >= 13 and current["dry_within_64m_samples"] == 0
        )
    return {
        "schema": "polli.coastal-development-cohort-comparison/1",
        "cohort": audit["static_ocean_connectivity"]["cohort"],
        "probes": len(cohort),
        "groups": groups,
        "files_sha256": {
            "static_audit": sha(audit_path),
            "validated_intervention": sha(receipt_path),
            "baseline_report": sha(baseline / "report.json"),
            "intervention_report": sha(intervention / "report.json"),
        },
        "qualification": "Previously lost development probes only; not complete maintained-water coverage or a new native qualification. Static ocean connectivity is not a flow observation.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("audit_path", "baseline", "intervention", "receipt_path"):
        parser.add_argument(name, type=Path)
    print(json.dumps(compare(**vars(parser.parse_args())), indent=2))
