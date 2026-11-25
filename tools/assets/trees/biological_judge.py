"""Frozen BioCLIP anchor screen. Missing or unvetted anchors cannot open the gate."""

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time


GENERA = ("Gleditsia", "Tilia", "Ulmus")
VIEWS = {"close": 52, "gameplay": 140, "billboard": 550}
WEIGHTS_SHA256 = "ac2e37c2f89ef8e6b889176a9a3f418970ad9db15a218bd29e3321e95c46ae97"
CONFIG_SHA256 = "4c131846348300c77b5bee06690b0e94ee85ca9ce9a30a853b36084d00dcd25c"
PROMPTS = [
    "a photo of a {genus} tree",
    "a photo of {genus} leaves",
    "a photo of the crown of a {genus} tree",
]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def preflight(manifest, root):
    """Require reviewed exact anchors and hash-bound native single-target views."""
    anchors = manifest.get("anchors", [])
    errors, inputs = [], []
    if len({a["genus"] for a in anchors}) != len(anchors):
        return ["Duplicate genus anchors"], []
    for genus in GENERA:
        found = [a for a in anchors if a["genus"] == genus]
        if not found:
            errors.append(f"{genus}: no vetted Workshop anchor")
            continue
        anchor = found[0]
        if not anchor.get("vetted") or not anchor.get("review_evidence"):
            errors.append(f"{genus}: missing supply review evidence")
        if not anchor.get("prefab") or len(anchor.get("crp_sha256", "")) != 64:
            errors.append(f"{genus}: missing exact prefab/package identity")
        for view, distance in VIEWS.items():
            shot = anchor.get("images", {}).get(view, {})
            path = root / shot.get("path", "")
            if not path.is_file() or sha256(path) != shot.get("sha256"):
                errors.append(f"{genus}/{view}: missing or changed native frame")
                continue
            if (
                shot.get("camera_size") != distance
                or shot.get("single_target") is not True
            ):
                errors.append(
                    f"{genus}/{view}: wrong camera or competing tree in frame"
                )
            inputs.append(
                {"genus": genus, "view": view, "path": path, "sha256": shot["sha256"]}
            )
    return errors, inputs


def calibration(rows):
    expected = {(genus, view) for genus in GENERA for view in VIEWS}
    keys = [(r["genus"], r["view"]) for r in rows]
    if len(keys) != len(expected) or set(keys) != expected:
        raise ValueError(
            "Anchor screen requires exactly three genera at all three distances"
        )
    passed = {
        view: all(r["predicted_genus"] == r["genus"] for r in rows if r["view"] == view)
        for view in VIEWS
    }
    allowed = []
    if passed["close"]:
        allowed.append("close")
        if passed["gameplay"]:
            allowed.append("gameplay")
            if passed["billboard"]:
                allowed.append("billboard")
    return {
        "top1_correct": passed,
        "bioclip_allowed_views": allowed,
        "basis": "One vetted asset per genus: a first screen, not statistical or teacher calibration",
        "probability_scope": "Softmax conditional on these three genera; not calibrated biological confidence",
    }


def load_model(directory, device):
    import open_clip
    import torch

    if importlib.metadata.version("open-clip-torch") != "3.2.0":
        raise ValueError("Frozen judge requires open-clip-torch 3.2.0")
    for filename, expected in (
        ("open_clip_model.safetensors", WEIGHTS_SHA256),
        ("open_clip_config.json", CONFIG_SHA256),
    ):
        if sha256(directory / filename) != expected:
            raise ValueError(f"Frozen judge changed: {filename}")
    torch.set_num_threads(4)
    name = "local-dir:" + str(directory.resolve())
    model, _, preprocess = open_clip.create_model_and_transforms(
        name, device=device, precision="fp32"
    )
    model.eval()
    model.requires_grad_(False)
    tokenizer = open_clip.get_tokenizer(name)
    with torch.inference_mode():
        tokens = tokenizer([p.format(genus=g) for g in GENERA for p in PROMPTS]).to(
            device
        )
        features = (
            model.encode_text(tokens, normalize=True)
            .reshape(3, len(PROMPTS), -1)
            .mean(1)
        )
        features = features / features.norm(dim=-1, keepdim=True)
    return model, preprocess, features


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("anchors", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--weights", type=Path)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Refusing to overwrite a frozen screen")
    manifest = json.loads(args.anchors.read_text())
    errors, inputs = preflight(manifest, args.anchors.parent)
    report = {
        "scorer_sha256": sha256(Path(__file__)),
        "anchor_manifest_sha256": sha256(args.anchors),
        "weights_sha256": WEIGHTS_SHA256,
        "config_sha256": CONFIG_SHA256,
        "prompts": PROMPTS,
        "genera": GENERA,
        "views": VIEWS,
        "blocked": bool(errors),
        "errors": errors,
        "optimisation_started": False,
    }
    if not errors:
        if args.weights is None:
            parser.error("--weights is required after anchor preflight")
        import torch
        from PIL import Image

        started = time.monotonic()
        model, preprocess, text = load_model(args.weights, args.device)
        rows = []
        with torch.inference_mode():
            for sample in inputs:
                with Image.open(sample["path"]) as im:
                    rgb = im.convert("RGB")
                    image = preprocess(rgb).unsqueeze(0).to(args.device)
                feature = model.encode_image(image, normalize=True)
                probabilities = (
                    (model.logit_scale.exp() * feature @ text.T)
                    .softmax(-1)[0]
                    .cpu()
                    .tolist()
                )
                rows.append(
                    {
                        **sample,
                        "probabilities": dict(zip(GENERA, probabilities)),
                        "predicted_genus": GENERA[
                            max(range(3), key=probabilities.__getitem__)
                        ],
                    }
                )
        report.update(
            {
                "rows": rows,
                "calibration": calibration(rows),
                "wall_seconds": time.monotonic() - started,
                "runtime": {
                    name: importlib.metadata.version(name)
                    for name in ("torch", "torchvision", "open-clip-torch")
                },
                "device": args.device,
                "dtype": "fp32",
            }
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(
        json.dumps(
            {
                "blocked": report["blocked"],
                "errors": errors,
                "optimisation_started": False,
            }
        )
    )
    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
