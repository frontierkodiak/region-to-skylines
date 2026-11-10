# Asheville asset bake-off

PL-881: procedural Blender recipes (A), open-weight image-to-3D (B), and the
same procedural geometry with generated material textures (C). This is an
**authoring-input and Blender-preview experiment, not a CS1 import claim**.
PL-880 owns the packaging bridge and the eventual game-renderer gate.

## What is controlled

- Three fixed types: 108 Norwood-informed bungalow, 40 N Lexington-informed
  three-story brick storefront, and a modular Hillcrest-style two-story row.
- Real photograph URLs, bytes' hashes, address coordinates and USGS NAIP
  export URLs are in `results/references.json`. NAIP is neighbourhood/roof-form
  context, not a surveyed footprint. Heights/depths are study assumptions.
- Main budgets: 6,000 / 8,000 / 12,000 triangles. LOD budgets: 180 / 180 / 240.
  These are study budgets, not claimed universal game limits. Lots are
  2×3 / 2×3 / 4×3 cells, with 8-m cells. One Blender unit is one metre.
- A and C use identical geometry. C replaces siding, brick, shingles and
  stone tiles with one archived generated atlas. Trim, windows, doors,
  lighting, camera, baking and lot fit do not change between them.
- B0 reconstructs the real, hand-masked photograph directly. B1 uses a
  separately generated, unobstructed concept view of the same building type.
  B1 is an AI interpretation, not recovered ground truth. Both use official
  TRELLIS.2-4B, seed 881, 512 pipeline, default 12/12/12 sampler steps.
- B is uniformly fitted within the same metre envelope, preserving inferred
  aspect ratios; actual resulting dimensions are recorded. The clean bungalow
  needs `--yaw-deg -90` to make its street facade face -Y. No inferred depth or
  unseen facade is presented as a measurement.

## Reproduce the Blender inputs

Blender 5.2.1 LTS and `uv` were used. Keep all run output outside the repository.
From the repository root (substitute your chosen experiment directory):

```sh
uv run tools/assets/bakeoff/references.py ~/experiments/PL-881-assets/references
uv run tools/assets/bakeoff/prepare_inputs.py ~/experiments/PL-881-assets/references
uv run tools/assets/bakeoff/materials.py ~/experiments/PL-881-assets/materials \
  --hybrid tools/assets/bakeoff/fixtures/material-atlas.png

blender --background --factory-startup --python-exit-code 1 \
  --python tools/assets/bakeoff/build.py -- \
  --materials ~/experiments/PL-881-assets/materials \
  --output ~/experiments/PL-881-assets/outputs --method A
# Repeat with --method C.

blender --background --factory-startup --python-exit-code 1 \
  --python tools/assets/bakeoff/verify.py -- ~/experiments/PL-881-assets/outputs
```

On carbon the executable is `/Applications/Blender.app/Contents/MacOS/Blender`.
Use `--python-exit-code 1`: Blender otherwise exited zero after a Python error.
Reference downloads retry transient network failures. The Census geocoder has
no match for Hillcrest; its owner's embedded-map coordinates are explicit in
the manifest instead of a substituted address.

Each candidate directory contains a single main FBX, a custom `_lod.fbx`,
1024-square main and 256-square LOD `_d`, `_n`, `_s`, `_c`, `_i` PNGs, a packed
Blender scene, four previews and a receipt. The two FBXs are the import inputs;
the scene also contains preview lights/ground and is not itself an import file.
Normal maps are neutral +X/+Y tangent-space maps in every arm.

### Continue through the native bridge

The original Blender experiment is pinned at
`82336461fec711a70e3fbba40987e1805af668d4`. Preserve those previews and judge
receipts. `bridge_inputs.py` opens its saved scenes and changes only the FBX
export convention (baked axis transform, FBX All scale), copies the exact map
bytes, and adds the bridge's named `.bake.json` with measured dimensions,
lot cells and import scale 100. It does not run image generation or rebuild
geometry. Re-import the resulting FBXs with `verify.py` before game use.

```sh
blender --background --factory-startup --python-exit-code 1 \
  --python tools/assets/bakeoff/bridge_inputs.py -- \
  ~/experiments/PL-881-assets ~/experiments/PL-881-assets/game-inputs
blender --background --factory-startup --python-exit-code 1 \
  --python tools/assets/bakeoff/verify.py -- \
  ~/experiments/PL-881-assets/game-inputs
```

Each game build/check must run serially under the harness slot. The bungalow
uses `--template auto`; storefront and apartment need explicit CommercialLow
and ResidentialHigh templates, respectively, discovered with `call templates`
in the Asset Editor. Do not silently give all nine residential-low behavior.
`game_report.py <game-build-and-check-root> <game-inputs> <destination>` audits
the CRP hashes, native dimensions/triangles/lot, save/reload and cleanup
receipts before assembling the native-renderer comparison. Keep that review
distinct from the Blender fallback.

## Reproduce image-to-3D on blade

These are real existing, isolated experiment environments, not persistent
servers. Exact environment snapshots are archived in `environment/`; the
pyproject overrides contain the original host paths and should be regenerated
with `trellis_overrides.py` after moving the adjacent source checkouts.

| Component | Exact source |
| --- | --- |
| TRELLIS.2 | `microsoft/TRELLIS.2@75fbf0183001ed9876c8dbb35de6b68552ee08bd` |
| CuMesh | `JeffreyXiang/CuMesh@12289e1062f0603f2f0d0771b02e1395d247f26f`, with its pinned submodule |
| FlexGEMM | `JeffreyXiang/FlexGEMM@6dd94a859c26ee8246888502eada3dd8ad85532e` |
| nvdiffrast | `NVlabs/nvdiffrast@253ac4fcea7de5f396371124af597e6cc957bfae` (v0.4.0) |
| o-voxel | subdirectory of the pinned TRELLIS.2 checkout |
| TRELLIS.2 weights | `microsoft/TRELLIS.2-4B@af44b45f2e35a493886929c6d786e563ec68364d` |
| Sparse decoder | `microsoft/TRELLIS-image-large@25e0d31ffbebe4b5a97464dd851910efc3002d96` |

The verified environment is `blade:~/experiments/PL-881-assets/trellis-runtime`:
Python 3.11.12, Torch 2.6.0+cu124, Transformers 4.57.3, xformers 0.0.29.post3,
CUDA toolkit 12.4. Native packages were built with `uv add --no-build-isolation`,
`CUDA_HOME=/usr/local/cuda-12.4`, `TORCH_CUDA_ARCH_LIST=8.6`, `MAX_JOBS=8`.
`utils3d` is pinned in the lock. Source checkouts are adjacent to the environment.

After copying the current `run_trellis.py` and the input PNGs there:

```sh
cd ~/experiments/PL-881-assets/trellis-runtime
CUDA_VISIBLE_DEVICES=GPU-61c6b838-a720-4447-5c43-1573ed78947b \
CUDA_HOME=/usr/local/cuda-12.4 ATTN_BACKEND=xformers \
SPARSE_ATTN_BACKEND=xformers SPARSE_CONV_BACKEND=flex_gemm \
PYTHONPATH=../TRELLIS.2 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
uv run --frozen python run_trellis.py .. ../trellis \
  --weights /mango/modelzoo/trellis2/PL-881 \
  --dino /mango/modelzoo/dinov3/dinov3-vitl16-pretrain-lvd1689m
```

Check live GPU placement first. UUID placement matters: CUDA's ordinal order
did not match `nvidia-smi` indices on blade. Do not evict resident workers.
The runner requires nonopaque RGBA before loading weights. Its public pipeline
constructor uses `rembg_model=None`; no RMBG-2 download or access grant is needed.

For B1, copy the three **generated interpretation** inputs from
`fixtures/concepts/` into an isolated input directory and pass that instead.
The committed RGBA bytes are the exact inference inputs; `prepare_clean.py`
documents how they were extracted from white-background concept originals.

Fetch the resulting GLBs to the rendering host, then run `build.py --method B
--generated <glb-dir>`, keeping B0 and B1 in different output directories.
Render B1's bungalow separately with `--target bungalow --yaw-deg -90`; the
other two targets use zero yaw. The converter preserves the inferred shape's
aspect ratios while imposing an explicit maximum metre envelope. It counts
triangles rather than trusting the generator's nominal simplification target.

Hunyuan3D-2mini was also run as an untextured shape-only control, not silently
ranked as a textured asset. `run_hunyuan.py`, its archived environment and result
receipt preserve that measurement. Current model findings and holdings:
[TRELLIS.2](https://github.com/polli-labs/knowledge/blob/main/models/trellis-2.md),
[Hunyuan mini](https://github.com/polli-labs/knowledge/blob/main/models/hunyuan3d-2mini.md),
[SUPRA-Tex survey](https://github.com/polli-labs/knowledge/blob/main/models/supra-tex.md).

## Verify and judge

`verify.py` imports the actual FBX files into clean Blender scenes and checks
one mesh/material, actual triangle/vertex counts, ground-centred pivot, applied
scale, metre bounds after roundtrip, UV 0–1, lot bounds and all five readable
maps at the declared resolutions. Main ground tolerance is 2 mm; LOD tolerance
is 5 cm. LODs must also be closed, outward, positive-volume shells. Direct
decimation of inferred meshes produced torn LODs; B therefore uses a convex
envelope from the actual generated vertices, reduced only if necessary, and
baked from its unchanged main mesh. Its vertices stay within the main AABB.
This explicit procedural retopology is part of B's conversion cost, not an
unreported capability of the image-to-3D model.

`judge.py <outputs> <real-reference-dir>` runs method-blind questions against
the resident `http://127.0.0.1:9120/v1/systemone` on blade. The actual identity
was Clef-Flash FP16 compute with NF4 weights, not an assumed GGUF backend. It
records image/reference/request hashes, model identity, questions, full response
probabilities and HTTP wall time. Scores are uncalibrated advisory ordinal
expectations. No threshold automatically accepts an asset.

`report.py <experiment-dir> <destination-dir>` assembles all 48 previews, source
links, reference context, measurements and four contact sheets. The private
review page includes reference photographs; they are **not** committed here.
Lexington photo: Stilfehler / Wikimedia Commons, CC BY-SA 4.0. Other photographs:
PSABC and Asheville Housing Authority. Aerial: USGS NAIP.

## What these files do not establish

- FBX import checks are not a `.crp` import, game renderer, actual shader,
  LOD-switch, placement, save/reload, service behavior or night validation.
- B deliberately has zero illumination/color-variation masks and low generic
  specularity: PBR outputs do not identify CS1's random night windows. Valid
  channel files do not mean the same night behavior as A/C.
- The study is three types, one seed, one material atlas and two input
  preparations, not proof that all procedural or generative models rank alike.
  No landmark or prop was tested. SUPRA-Tex was surveyed, not run; its published
  3090 measurement exceeds the shared free memory available during this run.
- Reported per-asset seconds separate model/export preparation and preview
  rendering. Image-generation wall time/billing, electricity, subscription
  allocation and human-equivalent authoring effort were not measured.
