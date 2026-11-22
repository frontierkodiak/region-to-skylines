"""Post-observation reporting adapter; original frozen source/raw data untouched."""

import argparse
import inspect
import json
from pathlib import Path

import coastal_rate_zero_study as frozen

OLD = 'sum(r["missed_slots"] for r in rows)'
NEW = "_count_missed_slots(rows)"


def count_missed_slots(rows):
    if any(not isinstance(r.get("missed_slots"), list) for r in rows):
        raise ValueError("Missing/malformed missed-slot lists remain unknown")
    return sum(len(r["missed_slots"]) for r in rows)


def derive(folder, native, harness, failed, output):
    # The untouched old preflight still binds all original source/runtime/data.
    frozen.preflight(folder, harness)
    plan = frozen.load(folder / "native-plan.json")
    original = Path(frozen.__file__)
    expected = plan["source_files_sha256"]["diagnostics/coastal_rate_zero_study.py"]
    if frozen.sha(original) != expected:
        raise ValueError("Exact frozen collector bytes required")
    source = inspect.getsource(frozen.collect)
    if source.count(OLD) != 1:
        raise ValueError("Expected exactly the documented reporting expression")
    if not (failed / "dense-api.f64").is_file() or (failed / "result.json").exists():
        raise ValueError("Expected retained partial-array reporting failure")
    # Compile one explicit, guarded expression substitution into an isolated
    # namespace. Never mutate the original module, physical plan or native files.
    namespace = dict(vars(frozen), _count_missed_slots=count_missed_slots)
    exec(
        compile(
            source.replace(OLD, NEW),
            "<documented-missed-slot-reporting-derivation>",
            "exec",
        ),
        namespace,
    )
    namespace["collect"](folder, native, harness, output)
    if frozen.sha(failed / "dense-api.f64") != frozen.sha(output / "dense-api.f64"):
        raise ValueError("Corrected reporting changed captured dense values")
    result = frozen.load(output / "result.json")
    result["schema"] = "polli.coastal-remaining-output-zero-derived-result/1"
    result["reporting_derivation"] = (
        "Original frozen collector TypeError after partial array; only missed-slot list-length aggregation repaired. No native rerun/raw/source/threshold changes."
    )
    frozen.write(output / "result.json", result)
    receipt = frozen.load(output / "receipt.json")
    receipt["result_sha256"] = frozen.sha(output / "result.json")
    frozen.write(output / "receipt.json", receipt)
    lineage = {
        "schema": "polli.rate-zero-reporting-derivation/1",
        "native_plan_sha256": frozen.sha(folder / "native-plan.json"),
        "exact_frozen_collector_sha256": expected,
        "adapter_sha256": frozen.sha(Path(__file__)),
        "expression_before": OLD,
        "expression_after": NEW,
        "retained_failed_partial_array_sha256": frozen.sha(failed / "dense-api.f64"),
        "derived_array_byte_identical": True,
        "result_sha256": frozen.sha(output / "result.json"),
        "raw_verdict_sha256": frozen.sha(native / "verdict.json"),
        "raw_native_files_or_bound_source_changed": False,
        "native_retry": False,
        "scope": "Post-observation reporting only, not prospective physical/threshold modification or acceptance",
    }
    frozen.write(output / "lineage.json", lineage)
    return {
        "result_sha256": lineage["result_sha256"],
        "snapshots": result["snapshots"],
        "partial_array_identical": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["folder", "native", "harness", "failed", "output"]:
        parser.add_argument(name, type=Path)
    print(json.dumps(derive(**vars(parser.parse_args())), indent=2))
