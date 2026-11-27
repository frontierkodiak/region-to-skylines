"""Frozen BioCLIP probability ranking on native single-tree frames."""

import argparse
import json
from pathlib import Path
import time

from biological_judge import (
    CONFIG_SHA256,
    GENERA,
    PROMPTS,
    WEIGHTS_SHA256,
    load_model,
    sha256,
)


def conservative_rank(score, controls):
    """Equal-scoring controls count against an anchor at the quartile boundary."""
    return 1 + sum(other >= score for other in controls)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("native", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("--weights", type=Path, required=True)
    p.add_argument("--device", default="cpu")
    a = p.parse_args()
    if a.out.exists():
        p.error("Do not overwrite a frozen result")
    import torch
    from PIL import Image

    plan = json.loads((a.native / "plan.json").read_text())
    frames = json.loads((a.native / "frames.json").read_text())
    expected = {(t["name"], v) for t in plan["trees"] for v in ("close", "gameplay")}
    samples = [f for f in frames if f["view"] != "billboard"]
    if (
        len(samples) != len(expected)
        or {(f["name"], f["view"]) for f in samples} != expected
    ):
        raise ValueError("Incomplete native ranking pool")
    for f in samples:
        if f["instances"] != 1 or sha256(a.native / f["file"]) != f["sha256"]:
            raise ValueError("Changed or non-single native input")
    if json.loads((a.native / "cleanup.json").read_text())["game_pids"]:
        raise ValueError("Native game has not been released")
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    started = time.monotonic()
    model, preprocess, text = load_model(a.weights, a.device)
    rows = []
    with torch.inference_mode():
        for f in samples:
            with Image.open(a.native / f["file"]) as im:
                tensor = preprocess(im.convert("RGB")).unsqueeze(0).to(a.device)
            emb = model.encode_image(tensor, normalize=True)
            probs = (
                (model.logit_scale.exp() * emb @ text.T).softmax(-1)[0].cpu().tolist()
            )
            rows.append({**f, "probabilities": dict(zip(GENERA, probs))})
    ranks = []
    for name in plan["anchors"]:
        genus = next(t["genus"] for t in plan["trees"] if t["name"] == name)
        for view in ("close", "gameplay"):
            pool = [
                r
                for r in rows
                if r["view"] == view and r["name"] in [name, *plan["controls"]]
            ]
            score = next(r["probabilities"][genus] for r in pool if r["name"] == name)
            # Ties count against the anchor; never let source order decide a pass.
            rank = conservative_rank(
                score, [r["probabilities"][genus] for r in pool if r["name"] != name]
            )
            ranks.append(
                {
                    "name": name,
                    "genus": genus,
                    "view": view,
                    "score": score,
                    "rank": rank,
                    "pool": len(pool),
                    "pass": rank <= plan["pass_rank_max"],
                }
            )
    a.out.write_text(
        json.dumps(
            {
                "rows": rows,
                "ranks": ranks,
                "passed_available_anchors": all(r["pass"] for r in ranks),
                "missing_native_anchor_genera": ["Gleditsia"],
                "cma_es_started": False,
                "prompts": PROMPTS,
                "weights_sha256": WEIGHTS_SHA256,
                "config_sha256": CONFIG_SHA256,
                "scorer_sha256": sha256(Path(__file__)),
                "loader_sha256": sha256(
                    Path(__file__).with_name("biological_judge.py")
                ),
                "wall_seconds": time.monotonic() - started,
                "input_policy": "full frame, standard pinned preprocessing; no crop or prompt tuning; distant frames excluded",
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps(ranks), flush=True)


if __name__ == "__main__":
    main()
