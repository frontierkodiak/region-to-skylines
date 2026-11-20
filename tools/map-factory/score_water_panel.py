"""Score a complete, frozen geographic holdout once, without fitting anything."""

import argparse
import json
from pathlib import Path

from scipy.stats import beta
import numpy as np

from refresh_water_risk import sha
from water_risk import assess
from water_risk_corpus import native_outcome


def rate(successes, total):
    """Exact two-sided 95% binomial interval; no empty-denominator estimates."""
    if not total:
        return {"n": 0, "events": successes, "rate": None, "ci95": None}
    return {
        "n": total,
        "events": successes,
        "rate": successes / total,
        "ci95": [
            float(beta.ppf(0.025, successes, total - successes + 1))
            if successes
            else 0.0,
            float(beta.ppf(0.975, successes + 1, total - successes))
            if successes < total
            else 1.0,
        ],
    }


def summarize(rows, target):
    known = [r for r in rows if r["labels"][target] is not None]
    counts = {k: 0 for k in ("tp", "fp", "tn", "fn")}
    for row in known:
        positive, predicted = row["labels"][target], row["flags"][target]
        counts[
            ("tp" if positive else "fp") if predicted else ("fn" if positive else "tn")
        ] += 1
    tp, fp, tn, fn = [counts[k] for k in ("tp", "fp", "tn", "fn")]
    cleared = [r for r in known if not r["flags"][target]]
    return {
        **counts,
        "precision": rate(tp, tp + fp),
        "recall": rate(tp, tp + fn),
        "specificity": rate(tn, tn + fp),
        "always_warn_precision": rate(tp + fn, len(known)),
        "always_warn_recall": rate(tp + fn, tp + fn),
        "cleared_risk": rate(sum(r["labels"][target] for r in cleared), len(cleared)),
        "unknown_squares": [r["slug"] for r in rows if r["labels"][target] is None],
        "identical_to_always_warn": bool(known) and not cleared,
        "misses": [
            r["slug"] for r in known if r["labels"][target] and not r["flags"][target]
        ],
        "false_alarms": [
            r["slug"] for r in known if not r["labels"][target] and r["flags"][target]
        ],
    }


def clearance(rows, product=False):
    known = [r for r in rows if all(v is not None for v in r["labels"].values())]
    cleared = (
        [r for r in known if r["product_clear"]]
        if product
        else [r for r in known if not any(r["flags"].values())]
    )
    base = rate(sum(any(r["labels"].values()) for r in known), len(known))
    risk = rate(sum(any(r["labels"].values()) for r in cleared), len(cleared))
    relative = (
        risk["rate"] / base["rate"]
        if risk["rate"] is not None and base["rate"]
        else None
    )
    return {
        "base_risk": base,
        "cleared_risk": risk,
        "cleared_squares": [r["slug"] for r in cleared],
        "absolute_risk_reduction": base["rate"] - risk["rate"]
        if risk["rate"] is not None
        else None,
        "relative_risk": relative,
        "relative_risk_reduction": 1 - relative if relative is not None else None,
        "separated_rate_intervals": bool(
            risk["ci95"] and base["ci95"] and risk["ci95"][1] < base["ci95"][0]
        ),
        "limits": "Intervals are conditional binomial summaries, not design-based global prevalence bounds. Relative reduction is descriptive; it has no confidence interval. Zero observed failures is not zero underlying risk.",
    }


def collect(staging, native, frozen, panel_path):
    manifest = json.loads((staging / "staging.json").read_text())
    freeze = json.loads((frozen / "freeze.json").read_text())
    model = json.loads((frozen / "model.json").read_text())
    panel = json.loads(panel_path.read_text())
    if (
        any(manifest[k] != freeze[k] for k in ("panel_sha256", "model_sha256"))
        or sha(frozen / "freeze.json") != manifest["freeze_sha256"]
    ):
        raise ValueError("Staging is not bound to the frozen experiment")
    if (
        sha(frozen / "model.json") != freeze["model_sha256"]
        or sha(panel_path) != freeze["panel_sha256"]
    ):
        raise ValueError("Frozen model/panel changed")
    planned = {r["sq"]["slug"]: r for r in panel["squares"]}
    if len(manifest["squares"]) != 30 or {
        r["slug"] for r in manifest["squares"]
    } != set(planned):
        raise ValueError("Expected all 30 distinct planned squares")
    rows = []
    for item in manifest["squares"]:
        slug = item["slug"]
        folder, run = staging / slug, native / slug
        if any(item[k] != planned[slug][k] for k in ("stratum", "world_region")):
            raise ValueError(f"Panel strata changed: {slug}")
        if item["status"] == "capture_failed":
            rows.append(
                {
                    **item,
                    "labels": {"flood": None, "drying": None},
                    "flags": {"flood": True, "drying": True},
                    "product_clear": False,
                }
            )
            continue
        if not (run / "report.json").exists():
            failure_path = run / "failure.json"
            if not failure_path.exists():
                raise ValueError(f"Planned native run not yet attempted: {slug}")
            rows.append(
                {
                    **{k: item[k] for k in ("slug", "stratum", "world_region")},
                    "status": "native_failed",
                    "failure_sha256": sha(failure_path),
                    "labels": {"flood": None, "drying": None},
                    "flags": {"flood": True, "drying": True},
                    "product_clear": False,
                }
            )
            continue
        for name, expected in item["files_sha256"].items():
            if sha(folder / name) != expected:
                raise ValueError(f"Frozen prepared input changed: {slug}/{name}")
        report = json.loads((run / "report.json").read_text())
        verdict = json.loads((run / "verdict.json").read_text())
        package_sha = item["files_sha256"][item["package"]]
        if report["session"]["map"]["sha256"] != package_sha:
            raise ValueError(f"Wrong native package: {slug}")
        if any(point.get("population", 0) for point in report.get("curve", [])):
            raise ValueError(f"Populated run is not empty-map ground truth: {slug}")
        if sha(run / "probes.json") != item["files_sha256"]["probes.json"]:
            raise ValueError(f"Native probes changed: {slug}")
        for name in ("terrain.u16", "water.u16"):
            if sha(run / "grids" / ("t000-" + name)) != item["files_sha256"][name]:
                raise ValueError(f"Native initial grid binding failed: {slug}/{name}")
        for name, expected in (
            ("reference-water.u16", item["files_sha256"]["water.u16"]),
            ("mapped-water.u8", item["files_sha256"]["mapped-water.u8"]),
        ):
            if sha(run / name) != expected:
                raise ValueError(
                    f"Native frozen flood reference changed: {slug}/{name}"
                )
        cleanup = report["session"]["cleanup"]
        if any(cleanup.get(k) for k in ("game", "steam_instances", "units_active")):
            raise ValueError(f"Native lifecycle not clean: {slug}")
        prediction = json.loads((folder / "prediction.json").read_text())
        regenerated = assess(
            np.fromfile(folder / "terrain.u16", "<u2").reshape(1081, 1081),
            np.fromfile(folder / "water.u16", "<u2").reshape(1081, 1081),
            json.loads((folder / "hydrology.json").read_text()),
            model,
        )
        if prediction != item["prediction"] or prediction != regenerated:
            raise ValueError(f"Prediction changed: {slug}")
        outcome = native_outcome(report, verdict)
        if report["game_minutes"] < 60:
            # A failed short attempt cannot become either a safe negative or a
            # selectively retained positive in the full-run holdout estimate.
            outcome["labels"] = {"flood": None, "drying": None}
        deployed = json.loads((folder / "deployed-prediction.json").read_text())
        if deployed != item["deployed_prediction"]:
            raise ValueError(f"Deployed prediction changed: {slug}")
        rows.append(
            {
                "slug": slug,
                "stratum": item["stratum"],
                "world_region": item["world_region"],
                "flags": {
                    k: prediction["risks"][k]["level"] == "flagged"
                    for k in ("flood", "drying")
                },
                "candidate_product_clear": prediction["status"] == "lower",
                "product_clear": deployed["status"] == "lower",
                "status": "complete" if report["game_minutes"] >= 60 else "incomplete",
                "package_sha256": package_sha,
                "receipt_hashes": {
                    name: sha(run / name) for name in ("report.json", "verdict.json")
                },
                **outcome,
            }
        )
    return manifest, rows


def score(staging, native, output, frozen, panel):
    if output.resolve() != (staging / "holdout-score.json").resolve():
        raise ValueError("The one-shot result must be staging/holdout-score.json")
    if output.exists():
        raise FileExistsError(
            "This holdout has already been scored; use a new panel for development"
        )
    manifest, rows = collect(staging, native, frozen, panel)
    result = {
        "schema": 1,
        "staging_sha256": sha(staging / "staging.json"),
        "panel_sha256": manifest["panel_sha256"],
        "model_sha256": manifest["model_sha256"],
        "metrics": {target: summarize(rows, target) for target in ("flood", "drying")},
        "rule_clearance": clearance(rows),
        "deployed_product_clearance": clearance(rows, product=True),
        "coverage": {
            "planned": len(rows),
            "complete": sum(r["status"] == "complete" for r in rows),
            "unscored": [r["slug"] for r in rows if r["status"] != "complete"],
        },
        "per_stratum": {
            g: {
                t: summarize([r for r in rows if r["stratum"] == g], t)
                for t in ("flood", "drying")
            }
            for g in sorted({r["stratum"] for r in rows})
        },
        "per_world_region": {
            g: {
                t: summarize([r for r in rows if r["world_region"] == g], t)
                for t in ("flood", "drying")
            }
            for g in sorted({r["world_region"] for r in rows})
        },
        "squares": rows,
    }
    with output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("staging", "native", "output", "frozen", "panel"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    score(args.staging, args.native, args.output, args.frozen, args.panel)
