# Terrain drama by region: the per-square vertical transform (PL-1329)

**Opt-in, not a shipping default.** The engine and its evidence are here; the
shipping writer, the page and the CLI are unchanged. Why that is forced, and
what promoting it would take, is under [The export gate](#the-export-gate).

The shipped fit is one affine factor per square: `game = (real - base) * scale
+ 50`. Flat squares (Boston, Charleston) come out below the shipped maps' own
relief and central height range, so their drumlins and harbour hills never
read. Very steep squares (Innsbruck, Yosemite) have to be squeezed whole,
which flattens the cliffs that made them worth exporting. One global scale is
the wrong tool, so this splits the vertical scale into two gains on each
square's own ground:

| Component | What it is | What the gain does |
| --- | --- | --- |
| Regional trend | the ground blurred at 1,200 m (a 3-pass box blur) | shapes the square's overall rise and fall |
| Local relief | what is left after the blur | carries ridgelines, bluffs, valleys, islands, and the river carve |

Both gains stay positive, so the ground keeps its order and a river still runs
downhill. The gains are fitted per square, from the square's own ground:

1. Local relief first, because it sets slope and so what can be built: bisect
   the local gain until mean 16 m roughness reaches the shipped maps' band.
2. Then the regional gain, until the central 25 tiles' 10-90 height range
   reaches that band.
3. Both are squeezed together if the highest point would break the game's
   1,024 m ceiling (target 1,000 m). The transform never clips.

The band is the shipped maps' own p25-p75, from the 104-map survey
(`survey/terrain-interest.json`, PL-1151/PL-1228):

| Measure | p25 | median | p75 | definition |
| --- | ---: | ---: | ---: | --- |
| Terrain roughness | 11.26 % | 15.50 % | 21.19 % | mean gradient magnitude at 16 m spacing, all 1081² nodes |
| Central height range | 114.6 m | 182.2 m | 300.7 m | 90th minus 10th percentile over the central 25 tiles' nodes |
| Terrain relief | 595.9 m | 761.6 m | 989.9 m | highest minus lowest, all nodes |
| Buildable area | 57 | — | — | the game's own New Game panel score |

The "very flat" and "very steep" squares were chosen by rule from six candidates
declared before measuring: the lowest and highest relief of ground above sea
level. Source relief of that dry ground: New Orleans 11.9 m, Amsterdam 21.0 m,
Chicago 32.5 m, Hong Kong 593.9 m, Grand Canyon 1,602.8 m, Yosemite Valley
1,839.2 m. Flat = New Orleans, steep = Yosemite Valley.

Bands, not gates: a square already inside the roughness and central-range band
is left alone (Pittsburgh and Rio come out at ×1.00); one outside is brought to
the nearest edge, and a square that cannot reach the band within the gain caps
is reported as `gain_cap` or `headroom` rather than pushed to a fake result.

## What the fit does to the eight evidence squares

Before is the shipping affine fit. After is the per-square transform. Bands are
the shipped maps' p25-p75; `·` is inside the band, `↓` below p25, `↑` above p75.
Buildable is the game's own panel score (`survey/measure_maps.py` on the built
`.crp`): pairs where a package was built in both arms, otherwise the after value.

| Square | Before: relief / roughness / central | Gains (regional × local) | After: relief / roughness / central | Limited by | Buildable before → after |
| --- | --- | --- | --- | --- | --- |
| Asheville | 649 · / 18.4 · / 93 ↓ | ×1.33 / ×0.99 | 724 · / 18.4 · / 117 · | — | 73 → 74 |
| Charleston | 78 ↓ / 2.4 ↓ / 14 ↓ | ×12 / ×7.84 | 362 ↓ / 12.9 · / 48 ↓ | gain cap | 58 → **55** ↓ |
| Innsbruck | 954 · / 20.1 · / 466 ↑ | ×0.24 / ×0.49 | 705 · / 20.1 · / 290 · | — | 76 → 77 |
| Pittsburgh | 211 ↓ / 16.2 · / 130 · | ×1.00 / ×1.00 | 201 ↓ / 16.0 · / 130 · | — | not built |
| Rio | 950 · / 14.9 · / 289 · | ×0.92 / ×0.92 | 950 · / 14.9 · / 289 · | headroom | not built |
| Boston | 128 ↓ / 3.6 ↓ / 27 ↓ | ×4.88 / ×3.49 | 490 ↓ / 11.8 · / 118 · | — | 73 → 69 |
| New Orleans (flat by rule) | 22 ↓ / 0.9 ↓ / 4 ↓ | ×12 / ×12 | 187 ↓ / 5.7 ↓ / 33 ↓ | gain cap | — → 85 |
| Yosemite (steep by rule) | 954 · / 19.6 · / 582 ↑ | ×0.10 / ×0.56 | 731 · / 19.6 · / 407 ↑ | gain cap | — → 74 |

Read together:

- **Boston is the case the issue was written for, and the honest answer is
  partial.** Its roughness and central height range move from far below the
  band to inside it (×3.3 and ×4.3) and the map reads as a real harbour region
  instead of a pancake; relief rises ×3.8 but stays below the band's p25
  (490 m against 596 m). Pushing relief to p25 would drive roughness and central
  range past p75: on a harbour plain the three bands cannot all be met at once,
  and the fit keeps the two that set slope and variety. Buildable falls 73 → 69
  because the stretched land is steeper than before; it stays well above the
  shipped p25 of 57.
- **Innsbruck keeps its cliffs and loses its absurd total height.** Central
  range 466 → 290 m (into the band) while roughness stays 20.1 %, so the valley
  walls are as steep as before and the map no longer spends 1,000 m on the
  valley floor-to-summit axis.
- **Asheville** needed only a 33 % regional stretch to bring its central range
  into the band. **Pittsburgh and Rio** are already inside the shape band and
  are unchanged.
- **Charleston and New Orleans cannot reach the band.** Both are marsh/lowland
  with relief under 80 m; at the 12× gain cap Charleston reaches roughness p25
  but only 48 m of central range, and New Orleans 5.7 % / 33 m. Reaching the
  band would need 25× or more, which would make the map far steeper than the
  band's roughness allows. The cap is doing its job; these squares stay
  reported as below the band.
- **Yosemite's regional gain is at its 0.10 floor** and its central range is
  still 407 m against the band's 300.7 m p75. Its relief is local (cliffs), not
  regional, so compressing the trend cannot remove it without flattening the
  cliffs themselves. Reported, not hidden.
- **Charleston's buildable score falls 58 → 55**, two points under the shipped
  p25 of 57. The constraint in the issue ("buildable share no worse than stock
  p25") is **not met on that square**, and a buildable floor inside the gain
  search is the next change before this could be a default. The flatness score
  is very sensitive on a marsh.

### Order, terracing and the carve

- **Order is preserved to sub-metre accuracy.** East-west neighbour pairs whose
  height difference reverses under the transform: 0 % (Asheville, Innsbruck,
  Pittsburgh, Rio, Yosemite), 0.03 % over 1 m on Boston (max reversal 1.23 m),
  0.12 % over 1 m on Charleston (max 5.91 m on a 362 m map). Rank agreement over a 128²
  sample is 0.98-1.00 except where clamping dominates (New Orleans 0.74,
  Yosemite 0.74, which are the two capped fits). No pair in any square reverses
  by more than 2 m except Charleston's 5.9 m outlier.
- **Terracing stays under the harness's 0.08 threshold** on every square, and
  the two coastal fixtures improve most: Charleston 0.075 → 0.048 and Boston
  0.068 → 0.023, because the stretched ground puts more of their flat shore into
  the "sloped" denominator. Pittsburgh goes from 0.003 to 0.009, still
  negligible.
- **The carve is drawn in game metres on the shaped ground**: river depth 10 m
  and lake depth 4 m are now game metres, so stretching a square cannot turn a
  river into a gorge. In real metres the cut is `depth / local gain`. This is
  the order PL-1191 asked for: the writer's water construction reads the final
  transformed heights. PL-1191's `admission.py` replays the browser cut at
  `10 * verticalScale`; with a drama fit `verticalScale` is the local gain, so
  that replay would over-cut on squares with a local gain above 1. It applied
  to none of the packages built here, but the two should be reconciled before
  promotion.

## Not claimed

- No native water, drainage, flood or first-hour result. The transform changes
  the terrain every water result is measured on, and PL-1191 owns that
  qualification.
- No acceptance, no promotion to the shipping default, no change to any
  threshold, evidence mask or frozen contract.
- Buildable scores exist for four of the eight squares only (the packages that
  were built in both arms); the other four are measured terrain-shape only.

## The export gate

The shipping export path is byte-frozen by `fixtures/contracts/pl912-water-risk-v1`:
`source_files_sha256` binds `terrain.js`, `inputs.js`, `mapgen.js` and the writer,
and `export_gate_files_sha256` binds `app.js`, `cli.mjs`, `index.html`,
`build.mjs`, `package.json` and the rest of the page. Any edit to those files
fails `npm test` by design; the contract's hashes chain through the runway,
transient-storage and sea-neighbour contracts, so refreshing one means
re-authoring the chain.

That is why this lands as a new module and new tools with the shipping files
untouched:

- `terrain-drama.mjs` - the transform, its fit and its evidence measures.
- `tools/map-factory/audit_terrain_drama.mjs` - the eight-square evidence above,
  plus before/after hillshades and `evidence.json`.
- `tools/map-factory/terrain_drama_inputs.mjs` - writer inputs (`input.png`,
  `geometry.json`, `banks.f32`) for any square under either policy.

Promotion has two honest paths, both a decision for Caleb, not this change:

1. **Wire it opt-in** (`--terrain drama`, a link parameter, a page control) and
   re-freeze the export gate after rebuilding the five accepted packages and
   proving their bytes unchanged. Every edit is additive and disabled by
   default, so byte-identity is provable; the re-freeze is mechanical but
   touches five frozen contracts' hash chains.
2. **Make it the default** only after a fresh native evaluation of the five
   shipping cases on the new writer, the buildable floor above, and PL-1191's
   water qualification. That is a new contract, not a hash refresh.

## Reproduce

The frozen output of that run is `tools/map-factory/terrain-drama-evidence/evidence.json`;
the hillshades it writes are not committed (about 24 MB).

```sh
cd tools/map-factory
node audit_terrain_drama.mjs --out EVIDENCE            # 8 squares, ~8 min, network
node terrain_drama_inputs.mjs --fixture boston --policy drama --out IN
node terrain_drama_inputs.mjs --name Boston --center 42.355,-71.06 --policy drama --out IN
uv run python generate.py IN/drama/input.png IN/drama/geometry.json OUT \
  --banks IN/drama/banks.f32 --landcover LANDCOVER.u8.gz
```

Unit tests for the transform: `node --test test/terrain-drama.test.mjs` from the
repository root (not yet in `npm test`, because `package.json` is export-gated).
