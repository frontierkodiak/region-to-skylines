# Remaining native check

PL-1328 is not complete. The draft PR contains reproducible source and
measured results, but the latest deletion invalidation fix still needs a
native witness. V6 revealed phantom distant stock trees after `ReleaseTree`.
Head marks each group dirty **before** release, then flushes RenderManager.
V6's retarget timing remains separate from that deletion defect.

## Exact source and retained outputs

- Producer branch: `PL-1328-tree-system` in `frontierkodiak/region-to-skylines`.
- Frozen v6 native driver: `2e0897353ca0b8c439d2beaaf47e8ec9513de75f`.
- V6 mod/source hashes: `observations/render-fix-build.json` and
  `observations/native-v6-summary.json`.
- Latest compiled deletion fix: `observations/pair-deletion-build.json`.
- Blade source mirror: `~/scratch/2026-11-24-pl1328/final-source/`.
- Carbon and blade run root: `~/experiments/PL-1328-trees/`.
- Inputs: `inputs-v3/`, 18 packages in `native-v6/build-*/*.crp`.
- No owned native process remains from v6; its teardown is recorded.

## Next run

Verify the draft PR's actual head and preserve the own worktree. Sync its
`tools/cs1-harness/` and `tools/assets/trees/` into the same own blade mirror,
then compile there. Do not modify shared checkouts, services or queued jobs.

Create a new `native-v7/` output, copying only the 18 `native-v6/build-*`
directories (reflink is fine). Do not copy `fresh-city/` or overwrite an
existing run. From the mirror's `tools/cs1-harness/`, run in the foreground:

```sh
uv run python ../assets/trees/native.py \
  ~/experiments/PL-1328-trees/inputs-v3 \
  ~/experiments/PL-1328-trees/native-v7 \
  --check-only --repeats 1 --frames 120 --wait-minutes 45 \
  --candidate KudzuGleditsia15sand3d
```

This still loads all 18 and recaptures all 54 specimen views, but times just
one representative at two zooms. Expect six frame windows, all with explicit
`timing_ui_visible:false`, the unchanged 139,362 forest positions, 18 created
pairs and 60 shots. Inspect the actual pixels: the old forest must disappear
after deletion; native close/gameplay/billboard views must show each pair.
Verify the mod SHA against the new build and the empty owned teardown.
Do not infer correctness from exit status, a pending-group flag or file count.

Use v7 specimen/build data for `summarize.py`, but keep v6 as `--frames-native`
with `--legacy-v6-ui` for the six-route/genus screening. Preserve v7's six
hidden-HUD windows separately, not mixed into the post-hoc v6 B/A2 comparison.
Rebuild the archive/contact sheets, rerun the gallery check and update shelf.

Pull terminal issue usage again: the current run is not available before it
ends, and prior Codex tokens are uncosted. Do not turn zero USD ticks into a
full-cost claim. Quality acceptance, review/rework duration, subscription
allocation and hardware rates remain unestablished. No <$5 assertion.

When the fixture is verified, make the PR ready and hand independent review
to Neon via `peer_review`; confirm automatic dispatch without a duplicate
mention. No self-merge. Keep merge auto-completion disabled: merging tooling
does not accept the unfinished quality/full-cost gates.
