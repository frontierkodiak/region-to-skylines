# Preselected stock-water static geometry

Read-only installed-package recheck at shipping A8 (`a8da051ae562da28e790ae59e7d4fdad952d882b`). No native load or stability claim. All three named maps retained; no substitution.

## Main connected saved-water body

These are the largest whole water components, **not isolated river channels**. Depth and freeboard in metres; widths are raster ridge-diameter estimates. Brackets give p10–p90; all extremes and all components are in JSON.

| Map | Records (type1/type0) | Wet components >0 / >0.125m | Main depth median [p10–p90] | Width median [p10–p90] | Immediate freeboard median | 64m bank-top proxy median |
|---|---:|---:|---:|---:|---:|---:|
| PU Gray Waters.crp | 72 (40/32) | 56 / 71 | 27.92 [7.03–40.92] | 160.00 [45.25–428.61] | 2.59 | 11.33 |
| MM Weaving Waters.crp | 11 (11/0) | 8 / 8 | 59.34 [7.06–112.08] | 243.70 [128.00–340.16] | 2.27 | 10.06 |
| PL Mountain Meadows.crp | 1 (1/0) | 1 / 1 | 51.16 [14.48–78.33] | 516.98 [385.33–1020.89] | 2.14 | 11.98 |

## Exact records and source settings

`stock-profile.json` keeps every serialized source record in order, including disabled type0 records, exact input/output float positions, raw target, raw input/output rates, water/pollution/flow counters. Source-to-component labels are sampled at the source coordinate, never nearest/source-name joins; label 0 means no support. Five Gray type0 records (indices26,39,40,45,49) sample dry nodes and remain explicitly unsupported; every type1 record samples nonzero saved water. Targets are raw/64 metres. Rates and flow counters are game settings/state, **not m³/s or demonstrated direction**.

- **PU Gray Waters.crp**: sea=64.73400115966797 m; raw rate range 655–65535; raw saved flow {'n': 72, 'negative_count': 0, 'min': 0.0, 'p10': 0.0, 'median': 79.5, 'p90': 3962.3999999999996, 'max': 32800.0}. Input/output positions and rates symmetric for every record: True.
- **MM Weaving Waters.crp**: sea=146.55101013183594 m; raw rate range 655–32767; raw saved flow {'n': 11, 'negative_count': 0, 'min': 0.0, 'p10': 0.0, 'median': 96.0, 'p90': 332.0, 'max': 415.0}. Input/output positions and rates symmetric for every record: True.
- **PL Mountain Meadows.crp**: sea=78.31200408935547 m; raw rate range 32767–32767; raw saved flow {'n': 1, 'negative_count': 0, 'min': 32785.0, 'p10': 32785.0, 'median': 32785.0, 'p90': 32785.0, 'max': 32785.0}. Input/output positions and rates symmetric for every record: True.

## Mountain Meadows: inland river support first

The one whole wet component spans x=-8640..4992 and z=-8640..8480 m. Its saved surface ranges 76.4375..110.265625 m, sea=78.31200408935547 m. The largest non-sea-level subset (|surface−sea|>3m), entirely inland, has 34,605 nodes (8.85888 node-km²), x=-3792..4992, z=-4640..8480 m and surface 81.3125..110.265625 m. Its elongated connected geometry, joining the near-sea body at x<0, z<0 in the whole mask and extending to the inland source, supports an **inland river-like channel**, not an isolated lake. It does not establish a hydraulic river classification or flow direction.

Only wet edge contacts are z_minus (z=-8640), x=-8640..-7344 and x_minus (x=-8640), z=-8640..-7744 m, both at the near-sea end at x<0, z<0. No x_plus or z_plus contacts. The source is inland input=output [4300.4296875,52.06236267089844,7794.0546875], type1, rates32767/32767, target_raw22901 (357.828125m); sampled node bed52.109375m, depth57.296875m, saved surface109.40625m. The large target/saved-surface difference is retained, not silently reconciled. Thus geometry supports **an inland-source/sea-connected topology**, not proof of upstream edge feeding or actual inflow/outflow.

Mountain's largest non-sea subset depth median49.05m [12.07–56.27], ridge diameter400.96m [32.00–611.36], immediate freeboard2.20m and 64m bank proxy11.55m. Its sea-threshold cut produces artificial width boundaries: these are not surveyed channel cross sections.

## Edge/sea ambiguity and small inland bodies

- Gray Waters' largest component contacts all four edges (full intervals in JSON); additional edge components and 50 disconnected inland wet components remain. Of those inland components,28 have >10 nodes,22 have 1–4 nodes. The former range0.013824–0.556288 node-km² and provide multiple **small inland lake/pool candidates**, not a blanket claim every component is a lake.
- Weaving Waters' principal network reaches only x_minus (x=-8640) at z=-3168..-2928 and -2640..-2400m. Its positive-x wet endpoint stops at x=8624 (one 16m node short of the boundary); its five positive-x controls are near, not on, the edge. Sea-level subset reaches the x_minus edge; most network surfaces are below the serialized sea setting. There are six separate inland lake/pool candidates of0.103680–0.447488 node-km² plus one single wet node (0.0625m deep). The latter vanishes at >0.125m while another1-node fragment splits off, so equal component totals do not mean identical support.
- Mountain Meadows has **zero disconnected inland water bodies at either threshold**, not zero inland water. Its inland water belongs to its single connected main body. Connected side basins cannot be independently called lakes by this component test.

The near-sea rule (within±3m) is only a descriptive candidate, never a sea identity or flow classification. A river may meet that elevation inland; a lake may sit at sea level; a sea may vary outside the tolerance. All near-sea and non-sea subset components are retained separately. No enter/leave direction is inferred from static geometry.

## Reproducible method and limitations

1. Read exact installed CRP bytes using existing legal decoders only; verify every asset MD5. Decode each kind52 asset (one each here), terrain, stored water depth and complete controls. All water endpoints agree with InstanceManager,gap2. This is structural consistency, not independent decoder validation.
2. Grid nodes have16m spacing, world coordinate(i−540)×16; serialized row index increases with z, z=-8640+16×row; compass names are intentionally not used; depth and terrain are raw/64m. Label every depth>0 node with4-neighbor connectivity; repeat at depth>0.125m. JSON also reports8-neighbor component counts to expose diagonal-contact ambiguity: Gray37/40,Weaving7/8,Mountain1/1 at the two thresholds, versus4-neighbor56/71,8/8,1/1. These are graph definitions, not disagreements silently resolved. Node area=nodes×256m² is a raster proxy, not polygon-survey area.
3. Depth statistics weight every wet node. Width proxy=2×Euclidean distance to the nearest excluded/background node, sampled at3×3 local maxima. Pads map exterior as dry; therefore edge-truncated widths are censored/biased. Single-node width proxy32m, with roughly16–32m discretization error; ridges/plateaus and wide lakes/ocean can bias the distribution. No centerline identity or surveyed channel width is claimed.
4. Immediate freeboard=terrain at truly dry cardinal neighbor minus saved surface at adjacent wet node; each shoreline pair counts, including duplicates. Bank-top proxy=max dry terrain along the same outward cardinal ray16..64m minus that wet surface. Rays may cross gaps; no true crest, floodplain elevation, levee top or current native floor is identified. Negative freeboards remain (Gray main min−31.55m,Weaving−59.80m,Mountain−48.08m); they expose raster/save discontinuities or unresolved geometry, not an overflow/stability conclusion. Full negative counts and extremes are retained.
5. Component IDs are local to each threshold/subset only. No cross-threshold identities are asserted. Every component, source sample with zero wet support, and sea/edge ambiguity remains in JSON. No original package or proprietary assembly is copied or redistributed.

**Comparison supported:** stock authoring is far sparser (40,11,1 active controls across these complete maps) than the previously surveyed frozen-v4 dense low-setting pools. Stock includes connected edge/near-sea networks and disconnected inland pools, but Mountain disproves a universal upstream-edge-fed rule. These static maps neither validate failed dense pools nor prove stock stability, native equilibrium, instantaneous discharge, or a causal prescription for rates/geometry.

## Inputs and rerun

- `PU Gray Waters.crp` SHA-256 `68a328a2efb5952166142ee9c3d1edbc98a3929d7563caaa65fab927ef077adf`; all asset MD5 checks pass.
- `MM Weaving Waters.crp` SHA-256 `85ec60c4da7fd67fb44bbed892c5f5d2d0acac5f84643185c49d2c6dbdeeede1`; all asset MD5 checks pass.
- `PL Mountain Meadows.crp` SHA-256 `1bebae469b2ad0b30567ea98ca4377bfad3a73695b4140852054706504372536`; all asset MD5 checks pass.
- Decoder `craft_anatomy.py` SHA-256 `1a6bc86e9f6c3bd0d03a5a03982a8f97b5ed4544d46fb7411223e79aadf079ad`.
- Decoder `measure_maps.py` SHA-256 `997fcf3f92b629ce3e5add5ac63200e46f4a65ad4649a1eb87e23c1445047d0b`.

Run from the PL-1191 workspace (existing environment,no install/sync):

```bash
uv run --project gameplay-water-shipping/tools/map-factory --no-sync python stock-profile.py
```

Outputs: `stock-calibration/stock-profile/stock-profile.json` and `stock-profile.md` under the existing PL-1191 experiment root. The script asserts component node conservation and all three decoder endpoint tags. Full source state is in JSON, not abbreviated to the table.

## Source-local geometry and settings (type 1 only)

Membership is sampled at the rounded native input-position node already used by the terrain witnesses, not by source name or proximity to a component. Main means the largest depth>0 four-neighbor component; isolated means a smaller component with no edge contact. Other edge bodies and unsupported points remain separate, even when empty. This topology does not identify hydraulic river/lake function. Input/output positions match for all selected records.

Source-local width is 2 × EDT at that exact source node using the full nonzero-water mask, not the ridge statistic or sea-threshold partition. It is a local inscribed-diameter proxy, not a surveyed cross section; an off-center source can severely understate channel width, and exterior padding censors edge bodies. Gap = saved stage (terrain + initial depth) minus serialized target; neither equality nor target validity is assumed. Each range below is min–max, in metres except raw settings.

| Map | Exact-membership group | Controls | Input/output rate raw range | Initial depth m | Local EDT diameter m | Saved stage−target m |
|---|---|---:|---:|---:|---:|---:|
| PU Gray Waters.crp | main_largest_body | 12 | 3932.00000–65535.00000 | 14.06250–54.78125 | 90.50967–362.03867 | -2.56250–1.70312 |
| PU Gray Waters.crp | isolated_body | 28 | 655.00000–32767.00000 | 3.21875–35.76562 | 45.25483–273.40812 | -0.68750–0.54688 |
| PU Gray Waters.crp | other_edge_body | 0 | no controls | no controls | no controls | no controls |
| PU Gray Waters.crp | unsupported | 0 | no controls | no controls | no controls | no controls |
| MM Weaving Waters.crp | main_largest_body | 5 | 655.00000–655.00000 | 44.70312–107.09375 | 96.00000–160.00000 | -0.45312–0.31250 |
| MM Weaving Waters.crp | isolated_body | 6 | 32767.00000–32767.00000 | 74.23438–122.31250 | 115.37764–607.15731 | -0.32812–0.40625 |
| MM Weaving Waters.crp | other_edge_body | 0 | no controls | no controls | no controls | no controls |
| MM Weaving Waters.crp | unsupported | 0 | no controls | no controls | no controls | no controls |
| PL Mountain Meadows.crp | main_largest_body | 1 | 32767.00000–32767.00000 | 57.29688–57.29688 | 1267.94322–1267.94322 | -248.42188–-248.42188 |
| PL Mountain Meadows.crp | isolated_body | 0 | no controls | no controls | no controls | no controls |
| PL Mountain Meadows.crp | other_edge_body | 0 | no controls | no controls | no controls | no controls |
| PL Mountain Meadows.crp | unsupported | 0 | no controls | no controls | no controls | no controls |

Raw rate histograms for PU Gray Waters.crp: main_largest_body: {'3932': 1, '5898': 1, '20971': 3, '65535': 7}; isolated_body: {'655': 2, '4587': 2, '32767': 24}; other_edge_body: {}; unsupported: {}.

Raw rate histograms for MM Weaving Waters.crp: main_largest_body: {'655': 5}; isolated_body: {'32767': 6}; other_edge_body: {}; unsupported: {}.

Raw rate histograms for PL Mountain Meadows.crp: main_largest_body: {'32767': 1}; isolated_body: {}; other_edge_body: {}; unsupported: {}.

**Literal 0.5-river / 0.01-lake rule: not supported.** Serialized 32767/65535≈0.499992 and 655/65535≈0.00999466 are descriptive normalized settings, not discharge. Exact main-versus-isolated histograms above supply counterexamples without promoting topology labels to hydraulic identities. Concrete counterexamples: Weaving main-body indices 0,1,2,3,8 all use 655 (approximately 0.01), while its six isolated-body indices 4,5,6,7,9,10 all use 32767 (approximately 0.5), the reverse of that simple rule. Gray has 24 isolated controls at 32767, two at 655 and two at 4587; its 12 main-body controls range 3932–65535, with seven at 65535 (1.0). Mountain alone has a main-body control at 32767, but its source-local diameter is 1267.94 m (broad pool/basin scale) and stage−target is −248.421875 m, so this is not evidence for a universal narrow-channel recipe. All source-local fields and exact source indices remain in JSON; zero-count groups are explicit. No type 1 points are unsupported or outside the native grid in this selection.
