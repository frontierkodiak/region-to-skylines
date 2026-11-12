"""Pinned Hunyuan3D-2mini geometry-only control; run in the documented blade environment."""

import argparse
import hashlib
import json
from pathlib import Path
import time

from PIL import Image
import torch

from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("references", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--weights", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    before = time.monotonic()
    pipe = Hunyuan3DDiTFlowMatchingPipeline.from_single_file(
        str(args.weights / "hunyuan3d-dit-v2-mini/model.fp16.safetensors"),
        str(args.weights / "hunyuan3d-dit-v2-mini/config.yaml"),
        device="cpu",
        dtype=torch.float16,
        use_safetensors=True,
    )
    pipe.to("cuda")
    setup_seconds = time.monotonic() - before
    records = {}
    for name in ("bungalow", "storefront", "apartment"):
        start = time.monotonic()
        torch.cuda.reset_peak_memory_stats()
        mesh = pipe(
            image=Image.open(args.references / (name + "-input.png")),
            num_inference_steps=30,
            guidance_scale=5.0,
            octree_resolution=256,
            num_chunks=4000,
            generator=torch.Generator("cpu").manual_seed(881),
        )[0]
        torch.cuda.synchronize()
        path = args.output / (name + ".glb")
        mesh.export(path)
        records[name] = {
            "seconds": time.monotonic() - start,
            "triangles": len(mesh.faces),
            "vertices": len(mesh.vertices),
            "bounds": mesh.bounds.tolist(),
            "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "texture": "none; geometry-only control, not eligible for the textured ranking",
        }
        receipt = {
            "model": "tencent/Hunyuan3D-2mini",
            "revision": "f90a0f7df7d5e6f71109cf333f6a95a0ae3194a6",
            "seed": 881,
            "steps": 30,
            "resolution": 256,
            "setup_seconds": setup_seconds,
            "torch": torch.__version__,
            "device": torch.cuda.get_device_name(),
            "source_commit": "f8db63096c8282cb27354314d896feba5ba6ff8a",
            "assets": records,
        }
        (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2))
        print(name, records[name], flush=True)


if __name__ == "__main__":
    main()
