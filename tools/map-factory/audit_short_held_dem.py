"""Bind a short native opening diagnostic to its complete frozen point cohort."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "cs1-harness"))
from cs1_harness.verdict import MAP_SOAK, required  # noqa: E402


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cohort(data, metadata):
    samples = data["samples"]
    assert len(samples) == len(metadata)
    selected, dry = [], []
    for actual, expected in zip(samples, metadata):
        assert all(actual[k] == expected[k] for k in ["x", "z"])
        point = {**actual, "name": expected["name"]}
        if required(point, expected, MAP_SOAK):
            selected.append(point)
            if not (point["wet"] or point.get("wet_within_64m")):
                dry.append(point)
    return {
        "observed": len(samples),
        "required": len(selected),
        "wet_or_near": len(selected) - len(dry),
        "fraction": (len(selected) - len(dry)) / len(selected),
        "dry": dry,
    }


def audit(run, prepared, frozen, output):
    diag, receipt = read(run / "diagnostic.json"), read(run / "session-receipt.json")
    metadata = read(frozen)["points"]
    requests = read(run / "measurement-requests.json")
    assert requests["frozen_probe_metadata"] == metadata
    assert requests["frozen_probes_sha256"] == sha(frozen)
    hydro = read(prepared / "hydrology.json")
    assert diag["crp_sha256"] == sha(prepared / (hydro["map_id"] + ".crp"))
    assert diag["elapsed_game_minutes"] >= 5
    for name in ["terrain", "water"]:
        assert (run / f"grids/t000-{name}.u16").read_bytes() == (
            prepared / f"{name}.u16"
        ).read_bytes()
    assert (run / "grids/t005-terrain.u16").read_bytes() == (
        prepared / "terrain.u16"
    ).read_bytes()
    assert not any(receipt["cleanup"].values())
    result = {
        "native_observed": True,
        "full_60_minute_qualification": False,
        "source_head": diag["tested_head"],
        "crp_sha256": diag["crp_sha256"],
        "elapsed_game_minutes": diag["elapsed_game_minutes"],
        "frozen_probes_sha256": sha(frozen),
        "points_unchanged": True,
        "initial_grids_exact": True,
        "final_terrain_exact": True,
        "threshold": MAP_SOAK["wet_end_min_fraction"],
        "samples": {
            label: cohort(read(run / f"{label}-world-water.json"), metadata)
            for label in ["t000", "t005"]
        },
        "cleanup": receipt["cleanup"],
        "receipt_sha256": {
            name: sha(run / name)
            for name in [
                "diagnostic.json",
                "measurement-requests.json",
                "session-receipt.json",
                "t000-world-water.json",
                "t005-world-water.json",
            ]
        },
    }
    result["short_required_gate_passes"] = all(
        s["fraction"] >= result["threshold"] for s in result["samples"].values()
    )
    result["zero_new_dry_from_all_wet_baseline_t000"] = all(
        not s["dry"] for s in result["samples"].values()
    )
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                **result,
                "samples": {
                    k: {p: v for p, v in s.items() if p != "dry"}
                    for k, s in result["samples"].items()
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["run", "prepared", "frozen", "output"]:
        parser.add_argument(name, type=Path)
    audit(**vars(parser.parse_args()))
