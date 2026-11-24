# Water built for play · fixed eight-square comparison

**8/8 squares fail flooding or retained-water checks.** This is a measured development increment, not a safe-water class or a general playability promise. Each square has one water verdict and reason in the existing capability row. Public merge and deployment remain Caleb's.

**Recommendation: leave this constructor unmerged.** The dense source-pool and bank design still loses required water and creates conspicuous artificial pools/terraces; bank raises reach about 350 m. This rejects this design, not the geography or all gameplay-first water construction.

Reporting correction after review of `a8da051`: the eight capability rows and `verdicts.json.rows` now use the observed map's saved `package_sha256` as `artifact_sha256`. The verdict-file digest is retained separately as `verdict_sha256`. The earlier rows incorrectly used that verdict digest for the map artifact. No native observations, outcome labels, source bindings or construction settings changed.

## Game results

Flooding is the existing maximum area with depth >0.5 m beyond 128 m of **initial OR mapped water**, limit 0.05 km². Natural retention uses the unchanged original contracts: >0.1 m within 64 m at >=95% of each <=512 m sector/body, including initialization. Engineered anchors require exact depth >=0.5 m at every sampled time. The counts below are contracts, not areas or source counts.

| Square | Game min / samples | Flood km² | Natural fail / total (startup; later loss) | Engineered fail / total | Still reads as the place? |
|---|---:|---:|---:|---:|---|
| asheville | 60.13 / 13 | 0.1068 | 82/2069 (0; 82) | 59/234 | Main course recognizable; side channels oversized and partly dry. |
| innsbruck | 60.13 / 13 | 0.5542 | 43/1105 (0; 43) | 19/193 | Valley alignment retained; enlarged water and banks overwhelm the opening. |
| rio | 60.07 / 13 | 0.5804 | 29/480 (0; 29) | 18/239 | Coast and hills recognizable; inland channels look like oversized pools. |
| pittsburgh | 60.04 / 13 | 0.2017 | 45/1214 (0; 45) | 35/246 | Three-river confluence recognizable; artificial round pools and widened tributaries remain. |
| charleston | 60.05 / 13 | 0.0243 | 16/2653 (0; 16) | 7/208 | Harbor outline recognizable; many circular inland pools look artificial. |
| grand-canyon | 60.13 / 13 | 0.0253 | 1/137 (0; 1) | 8/30 | Canyon relief retained; start moved to the rim and wet tributaries are exaggerated. |
| hong-kong | 60.01 / 13 | 1.0309 | 60/1358 (0; 60) | 11/276 | Harbor outline retained; steep banks and pool patterns exaggerate inland water. |
| yosemite | 60.01 / 13 | 1.6975 | 7/444 (0; 7) | 3/27 | Valley outline retained; excessive water terraces and banks dominate. |

Raw failed checks (unchanged harness labels):

- asheville: new_game_panel, startup_views, no_flooding.
- innsbruck: new_game_panel, startup_views, no_flooding.
- rio: new_game_panel, startup_views, no_flooding.
- pittsburgh: new_game_panel, startup_views, no_flooding.
- charleston: new_game_panel, startup_views, paths, no_terracing, ground_truth.
- grand-canyon: new_game_panel, startup_views.
- hong-kong: new_game_panel, startup_views, no_flooding.
- yosemite: new_game_panel, startup_views, no_flooding.

Authored water earthworks, before the separate network-corridor operation:

| Square | Max bed cut (m) | Max bank raise (m) | Water edits beyond 64 m strip (cells) |
|---|---:|---:|---:|
| asheville | 43.5 | 87.4 | 0 |
| innsbruck | 42.0 | 113.2 | 0 |
| rio | 90.7 | 165.6 | 0 |
| pittsburgh | 39.4 | 99.7 | 0 |
| charleston | 41.3 | 25.8 | 0 |
| grand-canyon | 100.5 | 69.1 | 0 |
| hong-kong | 101.3 | 349.7 | 0 |
| yosemite | 126.6 | 116.7 | 0 |

Place observations are producer image judgments, not human acceptance. The phone contact sheet uses untouched native opening screenshots; the separately split ZIP includes full-size opening and Areas images. Starting tile/camera framing can change when the constructed map selects a different playable tile. Baseline observations are opening-only, not matched first-hour soaks or a causal single-factor comparison. Overview images at t000 baseline and t005 after are not invented matched times.

## Construction and evidence

- Mapped alignments remain; beds/channels/lakes/shelf and banks are deliberately reshaped for gameplay. Design settings are channels 8–16 m deep and 48–224 m wide, lakes 16 m and shelf 8–24 m, with 2 m bank freeboard blending over 64 m. The zero-elevation floor can limit realized depth; existing deeper beds stay. Packed grids carry actual depths. Water-authoring changes outside that strip are zero; existing network-corridor grading is a separate operation.
- Map-local priority-flood D8 area sizes source game settings as 0.008 × sqrt(km²), bounded by source class. This is not calibrated discharge, and off-map catchment is unknown.
- The complete physical footprint receives one terrain-following joint surface. Lake/ocean/source cores are pools; steep reaches remain cascades. A global 2% grade trial was rejected before the game for broad mountain excavation, not promoted into a universal river rule.
- Every authored component has supply and a receiving control. Receiving ports use the final component namespace. A 32 m receiving basin is deepened to the existing 8 m design depth inside the same footprint, preserving surface/target. Edge/sea ports stay edge/sea; closed captures use explicit engineered drains, not claimed geographic edge outlets. Intake game-setting sums do not prove physical throughput or hydraulic communication.
- This copies practitioner techniques: [MB's deeper narrow channels](https://steamcommunity.com/sharedfiles/filedetails/?id=1782964859), [Rolfil's separate capacity/level and tributaries](https://steamcommunity.com/sharedfiles/filedetails/?id=598419805), and [Maestro/Jake's waterfalls and submerged drains](https://steamcommunity.com/app/255710/discussions/0/611701999536523575/). Numeric catchment conversion, widths and basin sizes are our design settings, not those authors' guarantees.

Actual measured constructor commit: `0740464f1808f3ae9af18eded4a081cf012700f4`. The source/input binding precedes all new physical outputs; all 48 captured input files and the eight-square selection stay fixed. The five fixtures plus all three remaining presets sorted by slug were selected before implementation. These are development squares, not a reopened or geography-independent holdout. Original source geometry, natural contracts and probes remain; new engineered outlet anchors are appended, not substituted.

All eight CPython/Pyodide package hashes match. The historical ten-package fixture test uses its frozen writer; old native qualification does not transfer to this constructor. The measured base is `032b4667`; the shared PL-1119 branch has since advanced to `912def4` with plane/vegetation work. That later physical-generator version is not integrated or game-qualified by this trial. The proposal stays draft and must not overwrite that later work. The finished measured source and complete observations receive one independent review; no intermediate review children were created.

## Failures and scope kept visible

The packet retains earlier CPU/native failures and their source recipes: v3 completed Asheville and interrupted Innsbruck after a source-footprint defect; v4 completed two failed maps; v5 was rejected before native for broad mountain excavation; v6 completed two failed maps and stopped before Rio for a functional-port defect. The first v7 preparation stopped before a package on a detached source apron; the second wrote six maps then stopped on a shallow receiving anchor. A connected-apron rule and a uniform receiving-basin rule each received a fresh committed source before the next preparation. They are physical corrections, not reporting retries. Hong Kong’s first v7 launch was blocked before the map loaded because Steam rotated its Cloud log. The failed launch has zero water samples and empty teardown; a fresh normal guarded attempt uses the identical package/probes/runtime after a fresh doctor check, without changing credentials, configuration or the offline guard. The failed startup and recovery binding remain in the final packet. Compact history companions explicitly SHA-list omitted intermediate images/generated binaries; no numerical outcome or error is silently removed.

All initial TerrainManager terrain/depth grids and the six explicitly compared source fields match the prepared inputs. WaterSimulation current/target floor captures are separate: only the saved early states are audited, with all differences from authored terrain retained in native-floor-summary-v7.json. Authored bank freeboard is not blanket native-floor identity.

Complete raw startup/runtime logs and all failed checks remain. An advisory game-error pass is not clean runtime health or loaded-image/JIT identity. Grids/API reads are not atomic; between-sample behavior, populated cities, sewage/pumping stress, long-term behavior and macOS remain unverified. All original risk-model thresholds, historical labels/scores and holdout constraints remain. PL-1329's optional terrain-drama transform was not mixed into these fixed inputs; its agreed order is final transformed ground first, then water construction in game metres.
