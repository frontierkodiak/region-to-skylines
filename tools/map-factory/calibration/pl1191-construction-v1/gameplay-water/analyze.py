"""Summarize completed runs with existing feature checks; never change a verdict."""

import collections
import hashlib
import json
import math
from pathlib import Path
import sys

sys.path.insert(
    0,
    str(
        Path(
            sys.argv[3] if len(sys.argv) > 3 else "region-to-skylines/tools/map-factory"
        ).resolve()
    ),
)
from maintained_water_inventory import feature_outcome

ROOT = Path(
    sys.argv[2]
    if len(sys.argv) > 2
    else "/home/caleb/experiments/PL-1191-stable-water/gameplay-water"
)
OUTPUT = Path(sys.argv[4]) if len(sys.argv) > 4 else ROOT
OUTPUT.mkdir(parents=True, exist_ok=True)
VERSION = sys.argv[1] if len(sys.argv) > 1 else "v7"
SLUGS = [
    "asheville",
    "innsbruck",
    "rio",
    "pittsburgh",
    "charleston",
    "grand-canyon",
    "hong-kong",
    "yosemite",
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def startup(contracts):
    return sum(c["samples"][0]["status"] == "fail" for c in contracts if c["samples"])


def later_loss(contracts):
    return sum(
        bool(c["samples"])
        and c["samples"][0]["status"] == "pass"
        and any(v["status"] == "fail" for v in c["samples"][1:])
        for c in contracts
    )


rows = []
for slug in SLUGS:
    run = ROOT / ("after-native-" + VERSION) / slug
    staged = ROOT / ("after-native-" + VERSION + "/maps") / slug
    if (
        not (run / "session-receipt.json").exists()
        or not (run / "report.json").exists()
    ):
        continue
    report = json.loads((run / "report.json").read_text())
    verdict = json.loads((run / "verdict.json").read_text())
    samples = [
        r
        for line in (run / "timeline.jsonl").read_text().splitlines()
        if (r := json.loads(line))["kind"] == "sample"
    ]
    inventory = json.loads((staged / "maintained-inventory.json").read_text())
    result = feature_outcome(inventory, report, samples)
    outcome_path = (
        OUTPUT / ("after-native-" + VERSION) / slug / "maintained-feature-outcome.json"
    )
    outcome_path.parent.mkdir(parents=True, exist_ok=True)
    outcome_path.write_text(json.dumps(result, indent=2) + "\n")
    floods = next(c for c in verdict["checks"] if c["name"] == "no_flooding")
    states = collections.Counter(c["status"] for c in result["contracts"])
    natural = [c for c in result["contracts"] if c["kind"] == "natural"]
    engineered = [c for c in result["contracts"] if c["kind"] == "engineered"]
    natural_states = collections.Counter(c["status"] for c in natural)
    engineered_states = collections.Counter(c["status"] for c in engineered)
    unresolved = [
        dict(id=e["id"], reason=e.get("reason"))
        for e in inventory["entries"]
        if e["status"] == "unresolved"
    ]
    binding = json.loads((staged / "staging.json").read_text())
    hydro = json.loads((staged / "hydrology.json").read_text())
    controls_match = True
    for sample in samples:
        observed = sample["water"]["sources"]
        controls_match &= len(observed) == len(hydro["sources"])
        for actual, expected in zip(observed, hydro["sources"]):
            controls_match &= (
                actual["type"] == 1
                and abs(actual["x"] - expected["position"][0]) < 0.001
                and abs(actual["z"] - expected["position"][2]) < 0.001
                and abs(actual["target"] - expected["target"]) <= 1 / 128 + 1e-6
                and actual["input_rate"]
                == math.floor(expected["capacity"] * 65535 + 0.5)
                and actual["output_rate"]
                == math.floor(
                    expected.get("output_capacity", expected["capacity"]) * 65535 + 0.5
                )
            )
    assert verdict["map_sha256"] == binding["sha256"]
    initial_water = run / "grids" / (report["first_dump"] + "-water.u16")
    initial_terrain = run / "grids" / (report["first_dump"] + "-terrain.u16")
    row = {
        "square": slug,
        "game_minutes": report["game_minutes"],
        "sample_count": len(samples),
        "observation_complete": result["observation_complete"],
        "flooded": floods["status"] == "fail",
        "flood_gate": floods,
        "dried": bool(later_loss(natural)),
        "failed_water_contracts": states["fail"] > 0,
        "natural_contract_counts": dict(natural_states),
        "engineered_contract_counts": dict(engineered_states),
        "natural_startup_failures": startup(natural),
        "natural_later_losses": later_loss(natural),
        "engineered_startup_failures": startup(engineered),
        "engineered_later_losses": later_loss(engineered),
        "source_inventory_unresolved": unresolved,
        "source_inventory_coverage_complete": result["coverage_complete"],
        "raw_verdict": verdict["verdict"],
        "raw_failed_checks": verdict["failed"],
        "package_sha256": binding["sha256"],
        "report_sha256": sha(run / "report.json"),
        "verdict_sha256": sha(run / "verdict.json"),
        "inventory_sha256": sha(staged / "maintained-inventory.json"),
        "feature_outcome_sha256": sha(outcome_path),
        "initial_water_exact": initial_water.read_bytes()
        == (staged / "water.u16").read_bytes(),
        "initial_terrain_exact": initial_terrain.read_bytes()
        == (staged / "terrain.u16").read_bytes(),
        "controls": len(samples[0]["water"]["sources"]),
        "all_sampled_configured_source_fields_match": bool(controls_match),
        "sampled_source_fields": [
            "type",
            "x",
            "z",
            "target",
            "input_rate",
            "output_rate",
        ],
        "observed_sea_levels": [s["water"].get("sea_level") for s in samples],
        "gpu": report["gpu"],
        "vram": report["vram"],
        "session": report["session"],
        "wall_seconds": report["wall_seconds"],
        "observed_at": samples[-1]["wall"],
    }
    rows.append(row)
    print(
        slug,
        round(row["game_minutes"], 2),
        "flood",
        row["flooded"],
        "dry",
        row["dried"],
        "natural",
        dict(natural_states),
        "engineered",
        dict(engineered_states),
        "unresolved",
        len(unresolved),
        flush=True,
    )
(OUTPUT / ("native-measurements-" + VERSION + ".json")).write_text(
    json.dumps(rows, indent=2) + "\n"
)
