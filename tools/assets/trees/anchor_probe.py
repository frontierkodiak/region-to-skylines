"""First BioCLIP check on offline Workshop views and untouched reserved photos."""

import argparse
import importlib.metadata
import json
from pathlib import Path
import time

from biological_judge import GENERA, PROMPTS, WEIGHTS_SHA256, load_model, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("renders", type=Path)
    parser.add_argument(
        "photos", type=Path, help="private Cabinet-resolved path manifest"
    )
    parser.add_argument("out", type=Path)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Do not overwrite a frozen test")
    import torch
    from PIL import Image

    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    samples = []
    for item, genus, title in [
        ("2456536855", "Ulmus", "American Elm"),
        ("2928288862", "Tilia", "Kaiserlinde 16m"),
        ("2402946167", "Tilia", "Bigleaf Linden"),
    ]:
        for view in ("close", "gameplay", "billboard"):
            samples.append(
                {
                    "source": "offline_workshop",
                    "genus": genus,
                    "title": title,
                    "view": view,
                    "path": args.renders / item / (view + ".png"),
                }
            )
    photos = json.loads(args.photos.read_text())
    for p in photos:
        if p["split"] not in ("val", "test"):
            raise ValueError("Training photo entered the held-out check")
        if sha256(Path(p["path"])) != p["media_sha256"]:
            raise ValueError("Changed reserved photo")
        samples.append(
            {
                "source": "reserved_inat",
                "genus": p["genus"],
                "photo_id": p["photo_id"],
                "split": p["split"],
                "path": Path(p["path"]),
            }
        )
    for s in samples:
        if not s["path"].is_file():
            raise FileNotFoundError(s["path"])
    started = time.monotonic()
    model, preprocess, text = load_model(args.weights, args.device)
    rows = []
    with torch.inference_mode():
        for sample in samples:
            with Image.open(sample["path"]) as image:
                tensor = preprocess(image.convert("RGB")).unsqueeze(0).to(args.device)
            embedding = model.encode_image(tensor, normalize=True)
            probabilities = (
                (model.logit_scale.exp() * embedding @ text.T)
                .softmax(-1)[0]
                .cpu()
                .tolist()
            )
            if not all(torch.isfinite(torch.tensor(probabilities))):
                raise ValueError("Nonfinite score")
            prediction = GENERA[max(range(3), key=probabilities.__getitem__)]
            rows.append(
                {
                    **{k: v for k, v in sample.items() if k != "path"},
                    "image_sha256": sha256(sample["path"]),
                    "predicted": prediction,
                    "correct": prediction == sample["genus"],
                    "probabilities": dict(zip(GENERA, probabilities)),
                }
            )
    passed = all(r["correct"] for r in rows)
    report = {
        "rows": rows,
        "passed_first_check": passed,
        "cma_es_started": False,
        "weights_sha256": WEIGHTS_SHA256,
        "scorer_sha256": sha256(Path(__file__)),
        "prompts": PROMPTS,
        "device": args.device,
        "dtype": "fp32",
        "wall_seconds": time.monotonic() - started,
        "versions": {
            n: importlib.metadata.version(n)
            for n in ("open-clip-torch", "torch", "torchvision")
        },
        "limits": "Offline main-mesh projections, not native billboard reconstruction. Full-frame classifier input; no crop/prompt/temperature tuning. Reserved photos are research-grade labels, not guaranteed whole-tree portraits.",
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "correct": sum(r["correct"] for r in rows),
                "total": len(rows),
                "passed_first_check": passed,
            }
        )
    )


if __name__ == "__main__":
    main()
