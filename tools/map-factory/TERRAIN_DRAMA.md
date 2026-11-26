# Terrain drama by region: the per-square vertical transform (PL-1329)

**Opt-in and wired; the default is unchanged.** `--terrain drama`, `terrain=drama`
in a link, and a page control that is off by default. It lands on the capability
preview branch (PR against `PL-1119-live-capabilities`) so the two terrains can
be compared with the preview in front of you. Switching the default is a later
decision, after native opening views.

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
4. If the game's own New Game buildable score would fall below the shipped
   p25 of 57, both gains are scaled down by one common factor (bisection) until
   it clears 58. The score is the panel's: the native flatness formula over its
   own asymmetric central window, times the dry share of the central 25 tiles
   (1 - wet fraction). A square with so little dry ground that even flat terrain
   cannot reach 57 is left alone and reported as unreachable.

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
| Charleston | 78 ↓ / 2.4 ↓ / 14 ↓ | ×6.44 / ×4.21 | 210 ↓ / 7.7 ↓ / 31 ↓ | buildable floor | 58 → **57** |
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
- **Charleston's buildable floor costs it the band.** The floor pulls its gains
  from ×12/×7.84 down to ×6.44/×4.21 so the panel score is 57 rather than 55;
  roughness falls to 7.7 % and central range to 31 m, both below p25. That is
  the trade the floor makes on a marsh: with 38 % of the central 25 tiles under
  water, the old fit was stacking steepness on top of a low dry share.
  **New Orleans** is wet enough that the floor is unreachable and is left alone
  (85 with the band fit at ×12/×12, still below the band).
- **Yosemite's regional gain is at its 0.10 floor** and its central range is
  still 407 m against the band's 300.7 m p75. Its relief is local (cliffs), not
  regional, so compressing the trend cannot remove it without flattening the
  cliffs themselves. Reported, not hidden.
- **The buildable floor fixes Charleston** (58 → 57 at the p25, measured with
  the game's own panel score by `survey/measure_maps.py` on the built package).
  The floor's estimate is the panel formula on the shaped ground before the
  carve, so it targets 58 and the carve costs the last point.

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
- No default switch: `--terrain auto` is still the shipped default.
- Buildable is measured on the built package for Asheville, Charleston,
  Innsbruck, Boston (before and after), New Orleans and Yosemite; Pittsburgh and
  Rio carry the fit's estimate only.

## The export gate

The shipping path is byte-frozen by `fixtures/contracts/pl912-water-risk-v1`, and the
capability stack adds its own gates (`test/capability-ui-contract.mjs`, the
transient short proof). The invariant that matters is that **with drama off the five
accepted packages still build byte-identically**; PL-776: no provenance gate unless
it changes what the player sees. So this change drops the source-hash binding for
the page and CLI files it touches (`app.js`, `cli.mjs`, `index.html`, `build.mjs`,
`package.json`, `agents.md`, `llms.txt`) and for `admission.py`, and keeps every
package, writer and template binding. It does not re-author the frozen hash chain.

Verification of the invariant:

- On `main` (where the frozen goldens match the writer), the same change passes
  `npm run test:fixtures`: all ten builds (five shipping, five reference) rebuild
  byte-identically with the admission change in place.
- On the preview branch, `npm run test:fixtures` already failed before this change:
  its `mapgen.js` and writer bytes moved when the capability stack landed
  (`rio: shipping mapgen.js changed`). The stack therefore cannot use those goldens
  as a byte gate; the invariant is verified on `main`, and the preview branch keeps
  every package binding it can.

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
