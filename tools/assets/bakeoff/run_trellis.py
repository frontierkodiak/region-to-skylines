"""TRELLIS.2 official 512 pipeline, hand-masked photos, CPU staging, textured GLB export."""

import argparse
import hashlib
import json
from pathlib import Path
import time

from PIL import Image
from huggingface_hub import model_info, snapshot_download
import torch

import o_voxel
from trellis2 import models
from trellis2.modules.image_feature_extractor import DinoV3FeatureExtractor
from trellis2.pipelines import Trellis2ImageTo3DPipeline, samplers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("references", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--dino", type=Path, required=True)
    args = parser.parse_args()
    for name in ("bungalow", "storefront", "apartment"):
        with Image.open(args.references / (name + "-input.png")) as image:
            if image.mode != "RGBA" or image.getextrema()[3][0] == 255:
                raise ValueError(
                    f"{name}: explicit nonopaque RGBA input is required before loading models"
                )
    args.output.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    config = json.loads((args.weights / "pipeline.json").read_text())["args"]
    info = model_info(
        "microsoft/TRELLIS-image-large",
        revision="25e0d31ffbebe4b5a97464dd851910efc3002d96",
    )
    decoder = snapshot_download(
        info.id,
        revision=info.sha,
        allow_patterns=[
            "ckpts/ss_dec_conv3d_16l8_fp16.json",
            "ckpts/ss_dec_conv3d_16l8_fp16.safetensors",
        ],
        local_dir=str(args.weights.parent / "ss-decoder"),
    )
    loaded = {}
    for name, prefix in config["models"].items():
        if "1024" in name:
            continue
        path = (
            str(args.weights / prefix)
            if prefix.startswith("ckpts/")
            else (str(Path(decoder) / "ckpts/ss_dec_conv3d_16l8_fp16"))
        )
        loaded[name] = models.from_pretrained(path)
        print("loaded", name, flush=True)
    sampler_args = {}
    for key in ("sparse_structure_sampler", "shape_slat_sampler", "tex_slat_sampler"):
        spec = config[key]
        sampler_args[key] = getattr(samplers, spec["name"])(**spec["args"])
        sampler_args[key + "_params"] = spec["params"]
    pipe = Trellis2ImageTo3DPipeline(
        models=loaded,
        **sampler_args,
        image_cond_model=DinoV3FeatureExtractor(str(args.dino)),
        rembg_model=None,
        low_vram=True,
        default_pipeline_type="512",
        shape_slat_normalization=config["shape_slat_normalization"],
        tex_slat_normalization=config["tex_slat_normalization"],
    )
    pipe.cuda()
    setup = time.monotonic() - start
    records = {}
    for name, budget in (
        ("bungalow", 6000),
        ("storefront", 8000),
        ("apartment", 12000),
    ):
        start = time.monotonic()
        torch.cuda.reset_peak_memory_stats()
        mesh = pipe.run(
            Image.open(args.references / (name + "-input.png")),
            seed=881,
            pipeline_type="512",
        )[0]
        torch.cuda.synchronize()
        inference = time.monotonic() - start
        raw_faces = len(mesh.faces)
        glb = o_voxel.postprocess.to_glb(
            vertices=mesh.vertices,
            faces=mesh.faces,
            attr_volume=mesh.attrs,
            coords=mesh.coords,
            attr_layout=mesh.layout,
            voxel_size=mesh.voxel_size,
            aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
            decimation_target=budget,
            texture_size=1024,
            remesh=False,
            verbose=True,
        )
        path = args.output / (name + ".glb")
        glb.export(path)
        records[name] = {
            "inference_seconds": inference,
            "total_seconds": time.monotonic() - start,
            "raw_triangles": raw_faces,
            "triangles": len(glb.faces),
            "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        receipt = {
            "model": "microsoft/TRELLIS.2-4B",
            "weights_revision": "af44b45f2e35a493886929c6d786e563ec68364d",
            "source_commit": "75fbf0183001ed9876c8dbb35de6b68552ee08bd",
            "ss_decoder_revision": info.sha,
            "setup_seconds": setup,
            "seed": 881,
            "pipeline_type": "512",
            "steps": {
                k: config[k]["params"]["steps"]
                for k in (
                    "sparse_structure_sampler",
                    "shape_slat_sampler",
                    "tex_slat_sampler",
                )
            },
            "torch": torch.__version__,
            "device": torch.cuda.get_device_name(),
            "background_removal": "explicit frozen input alpha, no synthesized cleanup",
            "assets": records,
        }
        (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2))
        print("ASSET_COMPLETE", name, records[name], flush=True)
        del mesh, glb
        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
