"""Frozen DINOv3 genus-contrast ranking on the retained native pool."""

import argparse
import importlib.metadata
import json
from pathlib import Path
import time

from biological_judge import GENERA, sha256
from rank_native import conservative_rank

WEIGHTS_SHA256 = "dcb2e45127cccbf1601e5f42fef165eea275c8e5213197e8dcf3f48822718179"
REVISION = "ea8dc2863c51be0a264bab82070e3e8836b02d51"


def contrast(means, genus):
    """Give each other genus equal weight, regardless of reference counts."""
    others = [v for k, v in means.items() if k != genus]
    if len(others) != 2:
        raise ValueError("Exactly three genus means required")
    return means[genus] - sum(others) / 2


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("native", type=Path)
    p.add_argument("photos", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("--weights", type=Path, required=True)
    p.add_argument("--device", default="cpu")
    a = p.parse_args()
    if a.out.exists():
        p.error("Do not overwrite a frozen result")
    if sha256(a.weights / "model.safetensors") != WEIGHTS_SHA256:
        raise ValueError("DINO weights differ from held revision")
    plan = json.loads((a.native / "plan.json").read_text())
    frames = json.loads((a.native / "frames.json").read_text())
    samples = [f for f in frames if f["view"] in ("close", "gameplay")]
    expected = {(t["name"], v) for t in plan["trees"] for v in ("close", "gameplay")}
    if (
        len(samples) != len(expected)
        or {(f["name"], f["view"]) for f in samples} != expected
    ):
        raise ValueError("Incomplete native pool")
    for f in samples:
        if f["instances"] != 1 or sha256(a.native / f["file"]) != f["sha256"]:
            raise ValueError("Native frame changed")
    photos = json.loads(a.photos.read_text())
    if len({r["media_sha256"] for r in photos}) != len(photos):
        raise ValueError("Duplicate photo bytes")
    for r in photos:
        if (
            r["split"] not in ("val", "test")
            or sha256(Path(r["path"])) != r["media_sha256"]
        ):
            raise ValueError("Reference is changed or not reserved")
    if not all(any(r["genus"] == g for r in photos) for g in GENERA):
        raise ValueError("Missing reference genus")

    import torch
    from PIL import Image
    from transformers import AutoImageProcessor, AutoModel

    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    started = time.monotonic()
    processor = AutoImageProcessor.from_pretrained(a.weights, local_files_only=True)
    model = (
        AutoModel.from_pretrained(
            a.weights, local_files_only=True, torch_dtype=torch.float32
        )
        .to(a.device)
        .eval()
    )
    model.requires_grad_(False)

    def encode(path):
        with Image.open(path) as im:
            tensor = processor(images=im.convert("RGB"), return_tensors="pt").to(
                a.device
            )
        vector = model(**tensor).pooler_output.float()
        if not torch.isfinite(vector).all():
            raise ValueError("Nonfinite DINO embedding")
        return torch.nn.functional.normalize(vector, dim=-1)[0]

    rows = []
    with torch.inference_mode():
        refs = torch.stack([encode(Path(r["path"])) for r in photos])
        for f in samples:
            cosine = (refs @ encode(a.native / f["file"])).cpu().tolist()
            means = {
                g: sum(s for s, r in zip(cosine, photos) if r["genus"] == g)
                / sum(r["genus"] == g for r in photos)
                for g in GENERA
            }
            rows.append(
                {
                    **f,
                    "mean_cosine": means,
                    "scores": {g: contrast(means, g) for g in GENERA},
                }
            )
    ranks = []
    for name in plan["anchors"]:
        genus = next(t["genus"] for t in plan["trees"] if t["name"] == name)
        for view in ("close", "gameplay"):
            anchor = next(r for r in rows if r["name"] == name and r["view"] == view)
            controls = [
                r
                for r in rows
                if r["name"] in plan["controls"]
                and r["genus"] != genus
                and r["view"] == view
            ]
            score = anchor["scores"][genus]
            rank = conservative_rank(score, [r["scores"][genus] for r in controls])
            n = len(controls) + 1
            ranks.append(
                {
                    "name": name,
                    "genus": genus,
                    "view": view,
                    "score": score,
                    "rank": rank,
                    "pool": n,
                    "cutoff": n // 4,
                    "pass": rank <= n // 4,
                }
            )
    report = {
        "model": "facebook/dinov3-vitl16-pretrain-lvd1689m",
        "revision": REVISION,
        "weights_sha256": WEIGHTS_SHA256,
        "config_sha256": sha256(a.weights / "config.json"),
        "processor_sha256": sha256(a.weights / "preprocessor_config.json"),
        "scorer_sha256": sha256(Path(__file__)),
        "processor": processor.to_dict(),
        "dtype": "fp32",
        "device": a.device,
        "versions": {
            k: importlib.metadata.version(k)
            for k in ("torch", "transformers", "torchvision")
        },
        "photo_manifest_sha256": sha256(a.photos),
        "reference_photos": [
            {k: r[k] for k in ("photo_id", "genus", "split", "media_sha256")}
            for r in photos
        ],
        "rows": rows,
        "ranks": ranks,
        "passed_available_anchors": all(r["pass"] for r in ranks),
        "wall_seconds": time.monotonic() - started,
        "cma_es_started": False,
        "policy": "Full frames; official 224x224 processor; normalized pooled CLS vectors; mean own-genus cosine minus equally weighted means of two other genera. No tuning, training or distant score.",
    }
    a.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(ranks), flush=True)


if __name__ == "__main__":
    main()
