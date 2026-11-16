"""Replay a c7 observational source trace, not the forward water simulation.

Run with ``uv run python -m cs1_harness.watertrace trace.jsonl --out audit.json``.
No map qualification probes or acceptance thresholds are used here.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

ENGINE = "c7f0e723dfe867d10aef73f14268bcf9f5ea4bab1c5ce4987897ed27f46511a1"


def intake(floor, depth, target, rate):
    """Natural type1 intake: signed availability and int32, cellwise rounding."""
    contribution = depth - np.maximum(target - floor, 0)
    total = int(contribution.sum())
    nominal = min(rate, total >> 1)
    removed = np.zeros_like(depth)
    if nominal > 0:
        numerator = contribution * nominal + total - 1
        numerator = ((numerator + 2**31) % 2**32) - 2**31
        removed = np.maximum(np.where(numerator < 0, -((-numerator) // total), numerator // total), 0)
    return total, nominal, removed


def footprint(nodes, position, rate):
    if not rate:
        return np.zeros(len(nodes), dtype=bool)
    radius = np.float32(np.sqrt(np.float32(rate)) * np.float32(0.4) + 10)
    delta = (nodes.astype(np.float32) - np.asarray(position, np.float32)[[0, 2]]).astype(np.float32)
    return (delta[:, 0] ** 2 + delta[:, 1] ** 2) < radius * radius


def audit(path: Path, receipt: Path | None = None):
    payload = path.read_bytes()
    raw = gzip.decompress(payload) if path.suffix == ".gz" else payload
    header, *records = [json.loads(line) for line in raw.decode().splitlines()]
    nodes = np.asarray(header["nodes"], dtype=np.int64)
    errors = []
    comparisons = {"intake_cells": 0, "source_phase_cells": 0, "publication_cells": 0}
    steps = []

    def require(test, reason):
        if not bool(test):
            errors.append(reason)

    def grid(value):
        a = np.asarray(value, dtype=np.int64)
        if len(a) < len(nodes) * 4:
            raise ValueError("truncated cell snapshot")
        require(not a[len(nodes) * 4 :].any(), "nonzero snapshot padding")
        require(np.all((a >= 0) & (a <= 65535)), "invalid unsigned primitive")
        return a[: len(nodes) * 4].reshape(len(nodes), 4)

    require(header["engine"] == ENGINE, "unsupported engine")
    require(
        header["error"] is None and not header["hit_bound"] and header.get("capture_stopped"), "incomplete trace header"
    )
    proof = header.get("proof") or {}
    require(
        proof.get("inverse_exact") and proof.get("canonical_original") == proof.get("canonical_stripped"),
        "missing inverse IL proof",
    )
    require(len(records) == header["steps"] and len(records) > 0, "record count mismatch")
    require(len(nodes) > 0 and len({tuple(p) for p in nodes}) == len(nodes), "empty or duplicate node set")
    if receipt is None:
        candidate = path.parent.parent / "session-receipt.json"
        receipt = candidate if candidate.exists() else None
    if receipt is None:
        require(False, "missing disposable-process cleanup receipt")
    else:
        session = json.loads(receipt.read_text())
        require(
            session["cleanup"] == {"game": [], "steam_instances": [], "units_active": []},
            "disposable process was not cleaned up",
        )
        binding = header["configuration"]["binding"]
        require(
            session["mod_sha256"] == binding.get("observer_sha256"), "cleanup receipt belongs to a different observer"
        )
        require(session["disposable_trace"]["engine_sha256"] == ENGINE, "cleanup receipt engine mismatch")
    previous = None
    ids = [source["id"] for source in header["sources"]]
    for record in records:
        index = record["index"]
        require(record["complete"], f"{index}: incomplete transaction")
        require([s["id"] for s in record["sources"]] == ids, f"{index}: source order mismatch")
        published, transport, end, published_end = [
            grid(record[k]) for k in ("published", "transport", "end", "published_end")
        ]
        if previous is not None:
            require(record["step"] == previous["step"] + 1, f"{index}: native step gap")
            require(
                np.array_equal(published, grid(previous["published_end"])),
                f"{index}: between-step publication mismatch",
            )
        previous = record
        prior = transport
        for source in record["sources"]:
            sid, control = source["id"], source["before"]
            require(control["type"] == 1, f"{index}/{sid}: unsupported source type")
            pre, after_input, post = [grid(source[k]) for k in ("pre_cells", "input_cells", "post_cells")]
            require(np.array_equal(prior, pre), f"{index}/{sid}: unobserved source delta")
            require(
                np.array_equal(pre[:, 1:], after_input[:, 1:]) and np.array_equal(pre[:, 1:], post[:, 1:]),
                f"{index}/{sid}: source changed floor or velocity",
            )
            comparisons["source_phase_cells"] += len(nodes)
            input_mask = footprint(nodes, control["input"], control["input_rate"])
            output_mask = footprint(nodes, control["output"], control["output_rate"])
            removed = pre[:, 0] - after_input[:, 0]
            added = post[:, 0] - after_input[:, 0]
            require(not removed[~input_mask].any(), f"{index}/{sid}: removal outside source footprint")
            require(not added[~output_mask].any(), f"{index}/{sid}: output outside source footprint")
            if sid in header["targets"]:
                available, nominal, model = intake(
                    pre[input_mask, 1], pre[input_mask, 0], control["target"], control["input_rate"]
                )
                if control["input_rate"]:
                    require(
                        available == source["availability"] and nominal == source["nominal"],
                        f"{index}/{sid}: native intake arithmetic mismatch",
                    )
                    require(np.array_equal(removed[input_mask], model), f"{index}/{sid}: per-cell removal mismatch")
                    require(
                        int(model.sum()) == source["input"]["water"], f"{index}/{sid}: native input buffer mismatch"
                    )
                require(int(added.sum()) == source["after"]["flow"], f"{index}/{sid}: native output flow mismatch")
                comparisons["intake_cells"] += int(input_mask.sum())
                steps.append(
                    {
                        "transaction": index,
                        "native_step": record["step"],
                        "source": sid,
                        "water_frame": record["water_frame"],
                        "published_water_frame": record["published_water_frame"],
                        "pre_water": int(pre[input_mask, 0].sum()),
                        "capacity": int(np.maximum(control["target"] - pre[input_mask, 1], 0).sum()),
                        "availability": available,
                        "nominal": nominal,
                        "removed": int(model.sum()),
                        "output": int(added.sum()),
                        "committed_buffer": source["committed"]["water"],
                        "commit_matches_local": source["after"] == source["committed"],
                    }
                )
            prior = post
        require(np.array_equal(prior, end), f"{index}: source-end closure mismatch")
        expected = end if record["published_buffer"] == record["working_buffer"] else published
        require(np.array_equal(expected, published_end), f"{index}: publication mismatch")
        comparisons["publication_cells"] += len(nodes)
    checkpoint = header.get("checkpoint", {})
    require(
        checkpoint.get("available") and header.get("endpoint_matches_completed_prefix"),
        "published endpoint is not covered by completed updates",
    )
    if records and checkpoint.get("available"):
        require(
            np.array_equal(grid(records[-1]["published_end"]), grid(checkpoint["cells"])),
            "paused published grid differs from completed prefix",
        )
        require(
            records[-1]["published_water_frame"] >> 6 == checkpoint["water_frame"] >> 6,
            "completed prefix does not reach paused publication cycle",
        )
    return {
        "path_sha256": hashlib.sha256(payload).hexdigest(),
        "engine": header["engine"],
        "transactions": len(records),
        "nodes": len(nodes),
        "touched_sources": len(ids),
        "unfinished_unpublished_tail_records": header.get("unfinished_tail_records", 0),
        "comparisons": comparisons,
        "errors": errors,
        "passes": not errors,
        "source_steps": steps,
        "scope": "Observed natural-source arithmetic and sampled-node source/publication closure; not a forward solver, transport-flux derivation or map qualification.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--receipt", type=Path, help="disposable Session cleanup receipt; otherwise found beside the trace directory"
    )
    args = parser.parse_args()
    result = audit(args.trace, args.receipt)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "source_steps"}, indent=2))
    raise SystemExit(0 if result["passes"] else 1)


if __name__ == "__main__":
    main()
