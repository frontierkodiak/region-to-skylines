"""Final report from retained facts: controls observed, holdout Unknown.

This non-closure reporting tool measures nothing and opens no game.  It reads
the frozen inputs, the retained control openings and the readiness refusal,
then writes `evaluation.json` and `RESULTS.md`.  It deliberately not run the
holdout: admission was refused, so those cells stay Unknown.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

import stock_v2 as study
from protocol import Request, decide, position


def identity(pid):
    path = Path("/proc") / str(pid)
    try:
        fields = (path / "stat").read_text().rsplit(")", 1)[1].split()
        return {"pid": pid, "start_ticks": int(fields[19]), "state": fields[0]}
    except (FileNotFoundError, IndexError, ValueError):
        return None


def control_rows(opening):
    rows = []
    for row in opening["paths"]:
        plan = row["plan"]
        request = Request(
            plan["mode"],
            position(plan["request"]["from"]),
            position(plan["request"]["to"]),
            plan["max_length"],
            row["pre_build_index"],
        )
        decision = decide(row.get("effective"), row.get("result"), request)
        rows.append(
            {
                "query_id": plan["query_id"],
                "mode": plan["mode"],
                "kind": plan["kind"],
                "label": decision.literal_label.value,
                "reason": decision.reason,
                "pre_build_index": row["pre_build_index"],
                "effective_build_index": row["effective"].get("build_index"),
                "flags": row["result"].get("flags"),
                "complete": row["result"].get("complete"),
                "released": row["result"].get("released"),
                "positions_exact": (
                    len(row["result"].get("positions", [])) >= 1
                    and row["result"]["positions"][0] == plan["request"]["from"]
                    and row["result"]["positions"][-1] == plan["request"]["to"]
                ),
            }
        )
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    args = parser.parse_args()
    freeze = study.read(study.HERE / "freeze.json")
    selection = study.read(study.HERE / "selection.json")
    readiness = study.read(args.raw / "readiness-result.json")
    controls = []
    for case in freeze["controls"]:
        opening = study.read(args.raw / case["case_id"] / "opening.json")
        rows = control_rows(opening)
        counts = Counter((row["mode"], row["kind"]) for row in rows)
        controls.append(
            {
                "case_id": case["case_id"],
                "package": case["locator"],
                "package_sha256": case["sha256"],
                "session_id": opening["session_id"],
                "opening_graph_sha256": opening["opening_graph_sha256"],
                "post_graph_sha256": opening.get("post_graph_sha256"),
                "native_context": opening["native_context"],
                "inventory_files": len(opening["runtime"]["launch"]["files"]),
                "inventory_roots": len(opening["runtime"]["launch"]["roots"]),
                "plugins": sorted(opening["runtime"]["launch"]["plugins"]),
                "assemblies": len(opening["runtime"]["launch"]["assemblies"]),
                "cleanup": opening["cleanup"],
                "rows": rows,
                "mode_kind_counts": {f"{m}/{k}": n for (m, k), n in sorted(counts.items())},
            }
        )
    observed = {row["query_id"] for control in controls for row in control["rows"]}
    holdout = [
        {
            "query_id": row["query_id"],
            "mode": row["mode"],
            "class": row["class"],
            "prediction": row["prediction"],
            "package_sha256": row["package_sha256"],
            "package_locator": row["package_locator"],
            "status": "unobserved_unknown",
            "reason": "readiness admission refused before any holdout request; no substitute or retry",
        }
        for row in freeze["holdout"]
        if row["query_id"] not in observed
    ]
    raw_files = {
        str(path.relative_to(args.raw)): study.sha(path)
        for path in sorted(args.raw.rglob("*"))
        if path.is_file() and "evidence" not in path.parts
    }
    evaluation = {
        "schema": 2,
        "issue": "PL-1313",
        "created_at": study.now(),
        "result": "unknown",
        "freeze_sha256": study.sha(study.HERE / "freeze.json"),
        "bundle_sha256": readiness.get("bundle_sha256"),
        "readiness": readiness,
        "controls": controls,
        "holdout": holdout,
        "holdout_observed": 0,
        "holdout_planned": len(freeze["holdout"]),
        "raw_files": raw_files,
        "limits": [
            "The two corrected controls ran exactly as frozen and returned the required literal labels; that is a control-readiness observation, not a decision law.",
            "No holdout request was issued: the byte-backed gate refused admission, so all six planned cells stay Unknown.",
            "No global accuracy, no pooled old votes, no geographic negative, no service, spawning, sustained-navigation or stable-water claim.",
            "File identity is not memory attestation, compiler trust or strict-no-mods evidence.",
            "No certificate, app adoption, model refit, public merge or Shelf page.",
        ],
    }
    study.write(study.HERE / "evaluation.json", evaluation)
    (study.HERE / "RESULTS.md").write_text(markdown(freeze, selection, evaluation))
    print(
        study.canonical(
            {
                "result": evaluation["result"],
                "controls": [c["case_id"] for c in controls],
                "holdout_unobserved": len(holdout),
            }
        ).decode()
    )
    return 0


def markdown(freeze, selection, evaluation):
    lines = [
        "# Results: corrected outside-query controls on a frozen unseen stock cohort",
        "",
        "**Outcome: Unknown.**  Both corrected controls ran as frozen and returned",
        "the required literal labels.  The byte-backed readiness gate then refused",
        "admission, so no holdout request was issued and all six planned holdout",
        "cells remain Unknown.  No retry or substitute was made.",
        "",
        "## Why the gate refused",
        "",
        "The frozen pre-control `freeze.json` binds an 82-file source manifest (the",
        "whole study tree).  The accepted readiness contract requires",
        "`frozen.source_files` to be exactly the versioned closure (30 files: the",
        "accepted 20-file helper/producer set plus this study's collector, driver,",
        "auditor, build, schema and tooling).  Every closure file is present in the",
        "freeze with the same pre-control hash, and the unchanged version-3 checker",
        "re-accepted the 30-file bytes.",
        "",
        "The contract also requires the runtime phase's `source_sha256` to equal",
        "the declared-closure digest.  The frozen collector recorded the",
        "82-file study-tree digest instead",
        f"(`{evaluation['readiness']['study_source_sha256']}`) rather than the",
        f"closure digest (`{evaluation['readiness']['contract_source_sha256']}`).",
        "Those two values cannot both be true of one measured opening.  Correcting",
        "the recorded binding would rewrite a measured field after the controls,",
        "and changing the closure would change the frozen source digest and require",
        "new controls, which the budget and no-retry rule forbid.  The gate is",
        "therefore left refusing.",
        "",
        "First gate read (frozen bundle builder):",
        f"- `{evaluation['readiness']['reasons'][0].split(':')[0]}`: source manifest was the 82-file study tree, not the 30-file closure.",
        "",
        "For an auditable second read, `assemble_v2.py` rebuilt the bundle from the",
        "frozen facts with the contract-exact 30-file closure and retained the",
        "licensed runtime bytes.  It stopped at the same structural point: the",
        "runtime policy binding is the study-tree digest.  That bundle is published",
        "(hashes only) as the record of the refusal.",
        "",
        "## Frozen selection",
        "",
        f"- rule: `{selection['rule']}`",
        f"- selected: {', '.join(row['file'] for row in selection['selected'])}",
        f"- covered cells: {', '.join(selection['covered_cells'])}",
        f"- holdout requests frozen: {len(freeze['holdout'])}",
        "- every planned holdout cell: unobserved, Unknown",
        "",
        "## Controls",
        "",
    ]
    for control in evaluation["controls"]:
        lines += [
            f"### {control['case_id']} — {Path(control['package']).name}",
            "",
            f"- session: `{control['session_id']}`",
            f"- package sha256: `{control['package_sha256']}`",
            f"- opening = post graph: {control['opening_graph_sha256'] == control['post_graph_sha256']}",
            f"- entry context: `{study.canonical(control['native_context']).decode()}`",
            f"- inventory: {control['inventory_files']} files, {control['inventory_roots']} roots, "
            f"{len(control['plugins'])} plugins, {control['assemblies']} assemblies",
            f"- cleanup: {', '.join(f'{role}:gone' for role, row in sorted(control['cleanup'].items()) if row['gone'])}",
            "",
            "| request | label | flags | complete | released | build index (independent = effective) |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for row in control["rows"]:
            lines.append(
                f"| {row['query_id']} | {row['label']} | {row['flags']} | "
                f"{row['complete']} | {row['released']} | "
                f"{row['pre_build_index']} = {row['effective_build_index']} |"
            )
        lines.append("")
    lines += [
        "## Holdout",
        "",
        "No holdout request was issued.  Every frozen cell stays Unknown:",
        "",
        "| query | mode | class | prediction | status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in evaluation["holdout"]:
        lines.append(
            f"| {row['query_id']} | {row['mode']} | {row['class']} | "
            f"{row['prediction']} | {row['status']} |"
        )
    lines += [
        "",
        "## Verification",
        "",
        "- 84 accepted old facts unchanged; 142 old publication files and 24 accepted",
        "  readiness files unchanged (preflight).",
        "- Frozen source, build (DLL sha256 and MVID), catalog, inputs, selection,",
        "  requests, predictions, controls, protocol, structural expectations and stop",
        "  policy were committed before the first control request.",
        "- Both controls: independent pre-request build index equals the request's",
        "  effective argument on every row; three identical phase inventories;",
        "  opening equals post graph; five owned PID/start identities gone after the",
        "  driver exited (verified post-exit, not by a self-attestation).",
        "",
        "## Replay",
        "",
        "A replay of the retained checks needs the exact installed game bytes and",
        "CRPs whose hashes are in `bundle.json`, plus the built `Cs1Harness.dll`",
        f"(`{freeze['build']['dll']['sha256']}`, MVID",
        f"`{freeze['build']['dll']['mvid']}`).  Those licensed bytes are retained by",
        "hash in the same-owner private blade experiment holding",
        "(`~/experiments/PL-1313-stock-v2/evidence`); they are not in this repository",
        "and not attached to the issue.  The harness mod was removed from the game's",
        "user Mods directory by normal session teardown; its exact bytes are the",
        "built DLL above.",
        "",
        "## Limits",
        "",
        *[f"- {item}" for item in evaluation["limits"]],
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
