"""Verify the final artifact, immutable predictions, source maps, and CRP receipts."""

import study
import collect


def main():
    study.check()
    here = study.HERE
    frozen = study.read(here / "freeze.json")
    earlier = study.read(here / "history/pre-query-freeze.json.gz")
    for key in [
        "protocol",
        "selected",
        "inventory",
        "features_sha256",
        "catalog_membership_sha256",
        "request_sha256",
        "predictions_sha256",
        "intervention_sha256",
        "controls",
        "query_ids",
        "old_package_lineage",
        "build_sha256",
    ]:
        if frozen[key] != earlier[key]:
            raise ValueError(f"frozen experiment changed: {key}")
    analysis = study.read(here / "analysis/source-fix.json")
    sources = {
        str(p.relative_to(study.ROOT)): study.sha(p)
        for p in sorted((here / "analysis").glob("*.py"))
    }
    if (
        analysis["analysis_sources"] != sources
        or analysis["source_key_set"] != sorted(sources)
        or analysis["frozen_primary_sources"] != study.source_files()
    ):
        raise ValueError("actual source file key sets or bytes differ")
    for case, kind in collect.cases(frozen):
        obs = study.read(here / "raw" / case["case_id"] / "observation.json.gz")
        if (
            obs["artifact_sha256"] != case["sha256"]
            or obs["session"]["map"]["sha256"] != case["sha256"]
        ):
            raise ValueError("source/installed CRP receipt differs")
        if (
            obs["new_game_protocol"]["update_mode"] != "NewGameFromMap"
            or obs["native_context"]["invert_traffic"] != "False"
        ):
            raise ValueError("native entry/traffic protocol differs")
    audit = study.read(here / "audit.json.gz")
    if (
        audit["source_sha256"] != study.sha(here / "analysis/audit.py")
        or audit["fidelity"]["invalid_requests"]
        or not audit["cleanup"]["all_observed_processes_gone"]
    ):
        raise ValueError("audit source or request/process fidelity failed")
    identities = {}
    for case in audit["cleanup"]["cases"]:
        for row in case["identities"]:
            identities[(row["pid"], row["start_ticks"])] = row
    if any(collect.still_running(row) for row in identities.values()):
        raise ValueError("an observed owned process is still alive")
    manifest = study.read(here / "integrity.json")
    paths = sorted(
        p
        for p in here.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.name != "integrity.json"
    )
    actual = {str(p.relative_to(here)): study.sha(p) for p in paths}
    if manifest["files"] != actual:
        raise ValueError("final artifact file membership or bytes differ")
    print(
        study.encoded(
            {
                "verified": True,
                "artifact_files": len(actual),
                "planned_requests": len(frozen["query_ids"]),
                "observed_requests": sum(
                    r["observed"] is not None for r in audit["rows"]
                ),
                "process_identities_gone": len(identities),
                "installed_crp_receipts": len(collect.cases(frozen)),
            }
        ).decode()
    )


if __name__ == "__main__":
    main()
