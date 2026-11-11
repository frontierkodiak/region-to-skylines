# Experimental compound resources · PL-857

**Offline qualification only, 2026-11-11. No native acceptance.** This integrates
writer `fb77e74cb3c64801044c8b231d1265205d006cab` and resource branch
`0d3b873a903bca0275fcc90e110fc222e41e5e0f` with both histories preserved.
It does not adopt or close PL-902, whose native resource judgment stays with
its owner. Rio R4 still fails the flood gate and needs parent-owned retuning.

Generation ran at merge commit `1fbea04436d8b611958359d78056fc6cf30f66a8`.
The follow-up commit changes documentation only. Artifact roots (on blade):

- Inputs: `/home/caleb/experiments/PL-857-sustained-water/resources-inputs`.
- Base preparation: `/home/caleb/experiments/PL-857-sustained-water/north-candidates`.
- Compound packages: `/home/caleb/experiments/PL-857-sustained-water/resources-candidates`.
- Exact replay staging: `/home/caleb/experiments/PL-857-sustained-water/resources-staging/maps`.

Each candidate directory has `generation.json`, `resources.json`, `plan.npz`,
`resources.png`, the exact `.crp`, copied prepared grids/geometry and any supplied landmarks,
land-cover input/provenance and optional original evidence. The generation
receipt binds package, plan, resource-report, source-package and input hashes.
Top-level `qualification.json` contains independent decoded checks;
`contracts.json` binds staged probe hashes and harness contract revision
`dee361a172c8acafe6fab2e9556411d160748652`. Staged `staging.json` links back
to the source generation receipt and its hash. These are filesystem artifacts,
not public URLs or evidence of native execution.

## Packages

| Region | Compound SHA-256 | Trees | Buildable panel % |
| --- | --- | ---: | ---: |
| Asheville | `be8b24824972463b7724ff8788c61d6fc93e5d011e343ed2190ddfa7ad0f3cc3` | 179,776 | 73 |
| Innsbruck | `5859e371c1a0a7d3df66d264a5dd1f28f46676a51aeeaeed535e35b28b52495b` | 179,765 | 75 |
| Rio | `ab9340df1afa485dfe7ffff90f7408a8201bca4e2c925bcea16409b2e069b097` | 179,788 | 77 |
| Pittsburgh | `1acdfbb94ae5daf55d278f5c0382f7c39315158a6fdc5f3c77e8d1f741832f8d` | 179,505 | 79 |
| Charleston | `3e87eecd7f1208f35c787a0ca7623435ebdd1fb14cee00b60d7cb54fe93336a0` | 179,540 | 13 |

The unchanged balanced defaults target ore 5.2%, oil 2.7%, fertile 3.4%,
with a 180,000-tree budget. They are targets, not achieved-share guarantees:
Charleston reached ore 1.72%, oil 1.69%, fertile 2.95%; Pittsburgh fertile
2.45%; Rio fertile 2.40% and ore 5.06%. Charleston's decoded water share is
85.89%. No defaults were retuned to hide those results. Native panel and
resource usability remain to be checked.

## Checks performed

- Every candidate was planned twice with identical package and plan hashes;
  loading its frozen plan and re-encoding also reproduced its exact package.
- All five were staged without launching, reproducing the generation hash.
  Missing plans, changed bound plans and changed source packages were rejected
  in isolated scratch copies; results are in
  `/home/caleb/scratch/2026-11-10-pl857/resource-stage-negative-checks/results.json`.
- Survey decoder checks passed: manager tails, grown/compatible tree prefabs,
  exclusive ore/oil, no invented start-tile ore/oil, cell-to-tile totals and
  metadata sums. Forest matches independently decoded tree positions on
  **100%** of cells for all five, not just the resource verifier's 99.5% floor.
- All painted grids equal the frozen plans; terrain, water and complete
  network bytes remain unchanged from each base north-facing package.
- Both PNG asset references resolve to complete, nonblank images at 400×224
  and 1800×1008. Author is blank, camera bytes retain mode 2 / yaw 0 /
  centre tile, and buildable metadata uses the regenerated resource water sum.
- Frozen panel and startup-view expectations passed the harness's request
  validators for all five. Supplied absolute landmark expectations are present
  and validated only for Asheville; the other four have none and no reference
  heights were invented. Independent `ground_truth` covers all five and retains
  the opposite sign of browser rotation, with `landmark_expectations` separate.
- Existing `verify_regions.py` passed without updating any unpainted golden.
  All five old CRP hashes, terrain/water preparation and descriptors reproduce.
  All five also stage unchanged with no resource plan; exact hashes are in
  `resources-candidates/unpainted-stage-control.json`.
- Full map-factory Ruff lint and format checks passed. Minor imported-source
  lint fixes and formatting preserve the resource research and default knobs.

The original resource expected hashes in `fixtures/resources.json` remain
byte-identical to pinned PR24. `verify_resources.py --freeze` was **not** run;
its old package hashes necessarily differ from this compound writer. Its
independent manager checks were reused without blessing new golden values.

## Integration decisions

`patch_metadata(fields=...)` remains typed and append-capable. Resource amounts
become `System.UInt32` fields, and `water_amount = amounts["waterAmount"]`
feeds the existing buildable calculation. Full resource-manager replacements
and legacy water-subarray replacement are mutually exclusive. Existing preview
argument, saved-camera validation, image references, unconditional blank
author, simulation hash and regenerated/preserved diagnostics remain intact.

The resource inputs are ESA WorldCover 2021 samples bound to the original
pinned sampler. Asheville/Pittsburgh use byte-exact pinned USGS MRDS fixtures;
the other three have no MRDS evidence supplied. Balanced additions are
explicitly labelled convention top-ups, not deposit or crop evidence.

No Steam, game, doctor, GPU/display/session service, remote GitHub or Multica
operation was performed. No shared worktree/cache was changed. All five maps
remain experimental and unverified in game; resource overlays and deterministic
bytes do not establish native visual correctness, hydrology or playability.

### Integration-review cleanup

Dependency-only resource and survey modules are kept byte-for-byte at pinned
PR24, rather than carrying unrelated formatter/unused-variable churn in this
integration. The shared encoders, planner defaults and independent decoder are
therefore the producer's original source. Lint/format claims for this cleanup
are scoped to the integration's changed Python files; unchanged dependency
files retain their pre-existing lint/format findings. Replanning, plan replay
and package identity are rechecked against the earlier experimental packages.
