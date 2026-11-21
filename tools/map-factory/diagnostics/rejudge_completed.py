"""Keep a raw registry-error verdict and separately replay its unchanged judge.

No native file is rewritten. A clearly named derived view links unchanged raw
inputs and contains a new verdict plus exact lineage. This repairs reporting,
not native evidence, thresholds, packages, runtime identity or qualification.
Run using the frozen owned harness project, which supplies cs1_harness.verdict.
"""

import argparse
import hashlib
import json
from pathlib import Path

from cs1_harness import verdict


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def derive(native, log, output, harness_commit):
    if output.exists():
        raise ValueError("Use a fresh derived-reporting view")
    raw = json.loads((native / "verdict.json").read_text())
    report = json.loads((native / "report.json").read_text())
    text = log.read_text()
    if (
        raw.get("verdict") != "error"
        or raw.get("reason")
        != "Traceback: AttributeError: 'int' object has no attribute 'get'"
        or "registry.add(out)" not in text
        or 'flood.get("worst_km2")' not in text
        or report["game_minutes"] < 60
        or report["session"]["cleanup"]
        != {"game": [], "steam_instances": [], "units_active": []}
        or report["harness"] != {"commit": harness_commit, "dirty": False}
        or verdict.harness_commit() != report["harness"]
    ):
        raise ValueError("Not the exact completed-run registry failure; retain unknown")
    before = {
        name: sha(native / name)
        for name in (
            "report.json",
            "verdict.json",
            "timeline.jsonl",
            "harness-source.json",
        )
    }
    judged = verdict.judge(native, write=False)
    if judged["verdict"] != "fail" or judged["thresholds"] != verdict.MAP_SOAK:
        raise ValueError("Unexpected derived judgment; do not manufacture a pass")
    output.mkdir(parents=True)
    for p in native.iterdir():
        if p.name != "verdict.json":
            (output / p.name).symlink_to(p.resolve(), target_is_directory=p.is_dir())
    (output / "verdict.json").write_text(json.dumps(judged, indent=2) + "\n")
    lineage = {
        "schema": "polli.completed-native-derived-judgment/1",
        "raw_native": str(native.resolve()),
        "raw_log_sha256": sha(log),
        "raw_files_sha256": before,
        "raw_verdict": raw,
        "derived_verdict_sha256": sha(output / "verdict.json"),
        "frozen_judge_source_sha256": sha(Path(verdict.__file__)),
        "judged_by": judged["judged_by"],
        "scope": "Separate unchanged-rule replay after completed simulation/clean teardown. Raw verdict error and all raw data retained, no native rerun or historical study rescore. Not runtime health, flood qualification or product adoption.",
    }
    (output / "derived-judgment-lineage.json").write_text(
        json.dumps(lineage, indent=2) + "\n"
    )
    assert before == {name: sha(native / name) for name in before}
    return lineage


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("native", "log", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("harness_commit")
    print(json.dumps(derive(**vars(parser.parse_args())), indent=2))
