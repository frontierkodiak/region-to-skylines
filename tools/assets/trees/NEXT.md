# Review and remaining acceptance

Native fixture evidence is collected: v6 has36 forest windows and18 specimen
pairs; v7 has six explicitly HUD-hidden windows and18 pairs/60 shots. Both
have empty owned teardown. No game, queue waiter, model or preview remains.

Final C# source matches the natively tested v6 module exactly. The final
driver matches v7 (`4b4cdac`), which had one redundant pre-release group mark.
`FinalizeTree` already invalidates the old group, so that duplicate was removed.
A live catalog after pair placement reports exactly two TreeManager instances.
Low background vegetation was not established as phantom trees. The combined
final head was not rerun after the rollback; source-level provenance is explicit.

## Retained source and outputs

- PR106, branch `PL-1328-tree-system`, `frontierkodiak/region-to-skylines`.
- Frozen v6 driver: `2e0897353ca0b8c439d2beaaf47e8ec9513de75f`.
- V7 driver/source: `4b4cdacfa94e90962bc5ccaeda866711f76a8065`.
- Carbon and blade outputs: `~/experiments/PL-1328-trees/`.
- Inputs: `inputs-v3/`; native evidence: `native-v6/` and `native-v7/`.
- Blade own mirror: `~/scratch/2026-11-24-pl1328/final-source/`.
- `observations/render-fix-build.json`: native-v6 source and mod hash.
- `observations/pair-deletion-build.json`: historical redundant-call variant,
  not final source; it binds the actual v7 mod hash.
- `observations/native-v7-summary.json`: source, HUD state and cleanup.

Gallery uses v7 specimens with v6 common-HUD post-hoc B/A2 screening:

```sh
python3 tools/assets/trees/summarize.py "$RUN/inputs-v3" "$RUN/native-v7" \
  "$RUN/review" --frames-native "$RUN/native-v6" --legacy-v6-ui \
  --trellis "$RUN/trellis/receipt.json"
```

Do not mix v7 hidden-HUD windows into v6's HUD-visible comparison. V5 timing
is invalid: retargeted distant groups were stale. Do not repeat completed
native work just because earlier notes said it was pending.

## Remaining gates

Independent review concerns the tooling and inconclusive experiment, not an
approved regional palette or a <$5 asset claim. Botanical identity, best-supply
comparison, snow/wind and renderer-limited performance remain open. No
Workshop content was redistributed.

Fetch terminal issue usage after the producer run ends; it cannot include
that run before exit. Prior Codex tokens are explicitly uncosted, not $0.
Full dollars require subscription/hardware allocation, review/rework duration
and rate, and quality-accepted yield. Preserve unknowns; do not substitute API
prices for Codex allowance or count emitted prototypes as accepted trees.

The concurrency guard refused a status change because Driver sessions moved
the issue to `in_progress` during the producer run. Do not retry in that same
run. A fresh context should read current steering and route independent peer
review if appropriate. Keep merge auto-completion disabled: merging tooling
does not accept unfinished quality/full-cost gates. No self-merge or done claim.
