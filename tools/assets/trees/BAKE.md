# Bake-layer comparison

This extends the native trial; it does not select a generation route. Trees use
`_d/_a/_c/_n` and the native billboard, not an authored LOD mesh or `_s` map.

## Fixed controls

A is the retained input-v4 15 m Sand3D set: 518/628/568 triangles for
Gleditsia/Tilia/Ulmus. B reads those exact `.blend` files, preserving branch
geometry, card topology, UVs, seed, scale and camera. It replaces the atlas
and the leaf corner normals; bark normals stay unchanged.

Our authored budget-first program never had a corresponding 70k–300k Nature
asset. B adds a new high-detail leaf-cluster source and assembles it over the
retained skeleton/card frames. This is not a rerun of an unrelated Nature tree.
It projects individually curved leaf geometry onto an atlas with Cycles
selected-to-active diffuse-colour, emission/coverage and tangent-normal bakes.
The semantic `_c` strip remains black leaves/white bark. Diffuse is capped at
140/255. `high-source.blend` retains the full-tree source for inspection.
The source has 238,288/161,488/138,448 triangles; runtime geometry is unchanged.

The high-detail leaves are simple authored shapes, not specimen scans or
botanically validated leaf/twig arrangements. Adding detail alone is not a pass.

## Reproduce

```sh
blender --background -t 4 --factory-startup --python-exit-code 1 \
  --python tools/assets/trees/bake.py -- "$RUN/inputs-v4" "$RUN/inputs-b"
blender --background -t 2 --factory-startup --python-exit-code 1 \
  --python tools/assets/trees/verify.py -- "$RUN/inputs-b" "$RUN/roundtrip-b.json"
```

For C, `--label c1 --program program-c1.json` and then `--label c2 --program
program-c2.json` execute two bounded declarative program revisions. Gemini
Neon sees genus reference photos and the preceding preview before each edit.
It controls leaf count/scale/width/curvature, colour gain and normal blending.
It does **not** rewrite the branch algorithm or card placement. Thus this trial
tests bounded program tuning, not the ceiling of unrestricted program editing.
Both prompts, provider usage and resulting programs are retained in the run.

`vision.py` makes one foreground Gemini request with image hashes and provider
usage, using the injected `GEMINI_API_KEY`. Run it through `with-polli-secrets`.
It refuses receipt overwrite; no key is written to outputs. A separate Hydrogen
judge receives unlabelled candidate images, including reversed-order pairs.
Identical-image and missing-tree sentinels test basic judge behaviour only.
Agreement with Caleb on the six native blind pairs remains the taste calibration.

## Native comparison

Use `native.py --skip-frames --comparisons plan.json` with A's three CRPs as
`--reference-asset` inputs. Take close/gameplay/billboard shots before choosing
a winner. `--map` accepts an exact installed winter map name for the `_c` snow
witness. A winter map must be observed natively; an offline mask audit is not
a snow pass. Forest p95 measurements run only after a winner is established.

`blind_pairs.py native-b native-c2 phone-page decoder.json` requires six
complete native gameplay comparisons against A. It crops fixed 1920×1080
native pixels without resampling, randomises pair order and horizontal
orientation, and keeps the decoder outside the phone page. Inspect every crop
before sharing. It cannot substitute authoring previews for missing native shots.

## Costs and unresolved controls

Keep provider usage, bake/preview time, native job time, queue-inclusive wall
time, VLM review time and human review time separate. Model list-valued token
cost is not an invoice or full asset cost. Allocate shared three-genus calls
explicitly; do not call emitted prototypes accepted yield. Codex subscription,
hardware, human review and rework remain unknown unless actually measured.

The $10 commercial-control budget is authorised, but no Tripo/Hunyuan credential
was injected on carbon or blade at the initial check. No commercial request was
made. Do not create an account, buy credit or substitute TRELLIS for D. PL-1326
owns the vetted Workshop ceilings; stock trees are not substitutes for them.

## Sources

- [CS1 tree authoring](https://cslmodding.info/asset/tree/): map packing,
  two-sided normals, diffuse ceiling, snow mask and native billboards.
- [Foliage Prep documentation](https://superhivemarket.com/products/foliage-prep/docs):
  crown hull/ellipsoid normals and preserving trunk normals; no addon was bought.
- [Leaf-card discussion](https://forums.unrealengine.com/t/leaves-cards-too-flat/74192)
  and [Hexbreaker workflow](https://cfringerwtcc.itch.io/hexbreaker/devlog/544906/hexbreaker-how-to-create-foliage):
  normal detail does not fix silhouette or macroform; curved source leaves.
- [Gemini API prices](https://aistudio.google.com/docs/pricing), checked
  November 25: Standard Neon $3/$15 and Hydrogen $1.50/$7.50 per million
  input/output tokens, with thinking included. Invoice/credit debit unverified.
