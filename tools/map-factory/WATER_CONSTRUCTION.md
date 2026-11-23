# Stable water construction

PL-1191 replaces predictor tuning with failure diagnosis, general construction
rules, and native verification. **No new water promise is qualified yet.**
The PL-912 release hold and the existing download warning remain in place.

## Retained failures

These measurements use PL-1072's original packages, probes, masks, and native
observations. Its 28 observations are development data for this work. The two
failed captures remain unknown. They are not replacement holdout cases.

| Failure | Retained evidence | Mechanism and remaining question |
| --- | --- | --- |
| Dry upland, South America | Flood 0.0850 km². Native reservoir stage 487.797 m, minimum nominal rim 467.719 m. | The engineered pond has a below-stage escape path. Its individual source contribution has not been isolated. |
| Dry upland, Europe | Flood 0.1132 km². Stage 281.500 m, rim 275.219 m. | Same open engineered pond. |
| Dry upland, Asia | Flood 0.2452 km². Stage 342.0625 m, rim 328.219 m. | Same open pond. The native source intervention below supports the spill mechanism. |
| Mountain river, Asia | Flood 0.1526 km². Stage 824.594 m, rim 814.875 m. | Most flood cells lie near the open pond. A separate river-side component and extreme depth remain unexplained. |
| Lowland river, South America | Flood 0.1152 km². Stage 283.781 m, rim 276.719 m. | Same open pond. Other river and lake supplies have not been causally excluded. |
| Lake shore, Europe | Flood 0.0627 km². No constructed reservoir. | Largest flood components are near river regulators, not either lake. Their design output rates exceed intake rates. Those fields are not measured flux. |
| Low coast, Oceania | Required water: 987/1149 at the endpoint, 978/1149 throughout samples. | All 68 lost Main Drain probes have static below-sea ocean paths. All 94 lost Bulimba probes occupy one isolated component with no control centre. Connectivity and river names alone do not establish supply. |
| Low coast, Europe | Native DEM correlation 0.8175. No ocean captured. | Broad river-area excavation changes low-relief terrain before Python. Internal restoration sensitivity is not an independent DEM pass. |
| Low coast, Asia | Native terracing 0.2970 and DEM correlation 0.8191. | 97.53% of equal-height pairs on slopes occur at the artificial 80 m sea shelf or 91 m land floor. These plateaus precede native quantization. |

All six flood maxima reproduce exactly from the retained depth grids and frozen
flood exclusions. Every worst-dump flood cell in the five reservoir maps lies
in a below-stage, four-neighbour floor domain reachable from that reservoir.
This is a possible gravity path, not measured flow or causal attribution.

The audit reads the actual native source target, including 1/64 m quantization.
The requested hydrology float is retained separately. Using the native target
preserves the same connected flood-cell counts on all five maps.

The North American coast corroborates the plateau mechanism: 98.24% of its
equal-height pairs on slopes occur at the same two fitted levels. Its absence
of required probes is not successful retention evidence.

## Native reservoir-output intervention

The dry-upland Asian development package completed 60.104 game minutes with
only source index 57's output disabled. Its native target remains 342.0625 m
and intake remains 3932. Output changes from 3932 to zero. Actual readback of
all 58 source controls matches the respective package at all 13 samples.
Terrain, initial water, probes, references, networks, resources, and previews
remain unchanged. The pinned mod hash is `6cedb7ee361d42f30e047fcf04cc1316a14e613435b5f9eaaf28836bc729fbfd`.

| Measure | Retained baseline | Reservoir output off |
| --- | ---: | ---: |
| Worst masked flood area, km² | 0.2452 | 0.0133 |
| Required wet at endpoint | 50/50 | 49/50 |
| Initialized locations without water within 64 m at endpoint | 0 | 6 |
| Full frozen drying label | negative | positive |

All six new isolated losses are in the engineered pond, including the single
required constructed-reservoir probe. The 95% required-water checks still
pass, but the unchanged full drying definition rejects the loss. Raw overall
verdict remains failed for unreviewed startup views. No original verdict is
rewritten. This supports the reservoir's contribution to the flood and shows
why disabling its source is not a storage solution.

The earlier retained-grid constructor diagnostic found feasible geometry in
four of five start tiles under its supplied masks. Fresh-source preparation
adds explicit geometry/network protections and prepares three, refusing dry-
upland South America and mountain-river Asia. These are distinct construction-
bound results, not geographic impossibility or native qualification.

`water_development_result.py BASELINE STAGED NATIVE --harness-source SHA`
validates package bindings, unchanged observation inputs and thresholds,
configured native source readback, full duration, and clean session teardown.
It does not score the new holdout. The original failed bootstrap attempt is
retained separately and supplies no native water observation.

## Rules supported by the diagnosis

1. Validate an engineered reservoir's final quantized rim and escape paths
   after all earthworks. A small source radius does not contain an open pond.
2. Check water supply by connected hydraulic domain, not a shared river name.
   A below-sea path does not prove sustained replenishment.
3. Separate synthetic bathymetry from land elevation. A constant ocean shelf
   and a universal land floor create plateaus. Adding rounding noise does not
   restore terrain.
4. Measure source interventions with fixed terrain, initial water, and probes.
   Summed design rates do not identify actual source flux or failure origin.

`reservoir_basin.py` implements a diagnostic constructor for the first rule.
It searches a supplied domain for a closed excavated pond, without terrain fill,
with at most 3 m of cut, at least 1 m depth across the source footprint, and
0.5 m of quantized rim freeboard. Its full eight-neighbour rim prevents diagonal
escape. Infeasible construction raises an error. The constructor does not run
in the product exporter and does not claim native stability.

`validate_native_basin` independently checks that same fixed starter design
against a final quantized hydraulic floor and an actual encoded source table.
It requires a full source footprint, at least 1 m of hydraulic depth, no
eight-neighbour escape outside the designed disk, and 0.5 m on its full rim.
Run it after all earthworks/admission and again on the actual native hydraulic
floor; a constructor receipt cannot replace either check. It is still a static
geometry gate, not a native retention verdict. All five original engineered
development ponds fail this gate on their captured native floors, through
insufficient footprint depth or escape. No original verdict is changed.

`water_diagnostics.py` adds explicit `reservoir-output-off` and `all-output-off`
modes. They preserve intake, source positions and targets, terrain, initial
water, networks, resources, and preview bytes. The original three default
diagnostic modes are unchanged. These are interventions, not playable maps.

## New holdout

`stable-water-panel.json` fixes twelve squares before any exporter change or
input fetch. `stable_water_panel.py` reproduces the selection. The freeze at
`calibration/pl1191-construction-v1/freeze.json` records all 39 excluded
development squares and the protocol. The minimum centre separation is
131.24 km, exceeding the 100 km exclusion rule.

Each of six world regions contributes one inland setting and one coast. All
capture failures, awkward squares, and native failures remain in the panel.
The panel can reveal gross construction failures. It cannot establish global
prevalence or a rare-failure guarantee.

Choose the candidate on development data before capturing and observing this
panel. Bind its source, package, initial grids, probes, and mapped-water mask.
Retain the original flood and full drying definitions. Observe at least
60 game minutes. Do not tune on the holdout or rescore it after repairs.
No predictor prefilter is proposed.

The historical drying label remains a comparator, not a settled construction
promise. Sixteen of the 27 historical positives arise only from loss of
initialized optional water, without a required-water loss or original dry-gate
failure. Seven fail the original dry gate. Preserve those historical labels.
Define the replacement's maintained-water coverage and meaningful drying
outcome on development data, and freeze that definition before accessing the
new holdout. Do not choose a denominator or omission rule after its outcomes.
The development definition below is now fixed; no product promise is adopted.

`calibration/pl1191-construction-v1/maintained-water-definition.json` now fixes
the development definition before holdout access. Require every engineered
storage anchor to retain at least 0.5 m of exact native depth at every sample.
Apply 95% nearby-water retention separately to each natural reach sector and
water-body component, including initialization, instead of pooling the map.
Explicit intermittent water is outside a perennial promise. Unsupported streams
and missing mandatory features remain unresolved and prevent an overall promise.
Keep the broad historical drying label as a separate unchanged comparator.

`outcome-freeze.json` binds the definition and unchanged panel hashes. The
feature-inventory compiler and evaluator are now implemented separately and
bound by `inventory-freeze.json` before holdout input access. Development
inventories retain unsupported coverage; this does not promote a product promise.

`maintained_water.py` implements only the engineered-reservoir anchor check.
It requires the bound definition, full duration and sample coverage, and exact
depth at every authored anchor. Missing evidence stays unknown. Applied to the
earlier Asian development observations, the baseline passes (minimum 1.625 m)
and the output-off intervention fails (0 m after initialization). This derived
comparison does not replace the original native receipt or its drying labels.

The coastal development mode `below-sea-intake-off` changes only positive intake
rates whose encoded target is strictly below encoded sea level. It retains all
outputs, positions, targets, initial grids and observations. It is an intake
intervention, not source deletion or a proposed default policy.

## Lake output development intervention

The matched lake-shore-Europe `all-output-off` package completed 60.147 game
minutes. Its 190 positive outputs were disabled; intake rates, targets, terrain,
initial water, probes and references were fixed. All 221 configured controls
matched their package at all 13 samples in both runs. Cleanup is empty.

The unchanged masked flood area falls from 0.0627 km² to zero, but required
endpoint retention falls from 911/918 to 0/918. All 5,809 initially wet probe
locations lose nearby water. The full drying comparator and both original
required-water gates fail. The intervention demonstrates dependence on ongoing
supply, not a stable construction fix. It does not distinguish the two lakes
from the river regulators. A separate `river-output-off` package preserves lake
and stream outputs and every intake. That separate intervention completed
60.104 game minutes. All 221 controls match both packages at all 13 samples.
Disabling only 187 river outputs again reduces flooding to zero and dries all
918 required probes, while 241 of 5,809 initially wet locations retain nearby
water. Both required-water gates and full drying fail. This supports a river-
supply contribution, not exclusive attribution or a playable fix.

## Experimental enclosed-storage exporter

`closed_storage_candidate.py` is a development entry point, not a shipping
default. It reconstructs hydrology from captured PNG/geometry/banks without
adding the legacy pond carve or prefill. It fits networks first, protects their
corridors, landing, mapped water (unmodeled streams included) and existing
controls, then searches inside the selected start tile. Resource planning
follows any input-bound admission earthworks.

The candidate binds preconstruction grids, actual final CRP terrain/water and
encoded controls. Final checks require no fill, at most 3 m cut, an untouched
full rim, 0.5 m freeboard, at least 1 m initial depth across the source footprint,
and no new water outside the basin. Tests reject late rim cuts/fill and prefill
removal even when the earlier constructor passed.

Fresh preparation succeeds geometrically on dry-upland Europe and Asia and
lowland-river South America. Both other predeclared cases remain refusals under
the fixed bounds. Three physical packages and authored probes are frozen; no
historical certificate transfers to them. Shipping source files remain
unchanged. Natural-feature coverage and this path's nine-square nonregression
are unfinished.

`closed_storage_observation.py freeze` binds package/probes, original native
thresholds, the meaningful-drying definition, validators and harness/mod before
observation. `preflight` rejects altered packages, cohorts and validators before
queueing. `collect` retains failures, checking exact reservoir depth and actual
native hydraulic floors separately. The old collector records floors only at
t000/t005; later-floor evidence remains unknown. All thirteen water/source
samples remain required. Loaded-assembly identity limitations remain explicit.

## Coastal intake development intervention

The Oceanian `below-sea-intake-off` intervention completed 60.034 game minutes.
Only 99 positive intakes changed; all 167 outputs, targets, positions, initial
grids and frozen observations remained fixed. All 167 controls match their
package in all 13 samples, in both baseline and intervention. Cleanup is empty.

Required endpoint retention changes from 987/1149 to 988/1149, and throughout
from 978/1149 to 980/1149. Both original gates and full drying still fail.
Flood remains 0.0003 km². In the original lost cohort, only 1/68 Main Drain
probes is wet at the endpoint and none throughout; all 94 Bulimba probes still
lose water. The below-sea intake factor does not rescue either domain. The
subsequent matched `all-intake-off` run completed 60.096 game minutes with all
167 positive intakes disabled and all outputs unchanged. Endpoint retention is
again 988/1149 and throughout 980/1149. Only 1/68 original Main Drain endpoints
is wet, none throughout; all 94 Bulimba probes remain lost. Flood increases to
0.0079 km², below the unchanged 0.05 km² gate. All 167 controls match both
packages at all 13 samples; teardown is empty. Configured withdrawal is not
necessary for the bulk of these losses under this intervention. Dynamic
replenishment, other source effects and isolated-domain missing supply remain
unresolved.

The generic intake transformer now preserves implicit output rates explicitly
in its hydrology record before changing intake. A real-format regression failed
before the fix and passes after it. The observed coastal variant is unaffected:
all 99 changed controls already declared output separately.

## First enclosed-storage native observation

The fresh Asian candidate completed 60.112 game minutes. Its authored reservoir
anchor retains at least 1.375 m exact depth across all 13 samples, passing the
separate 0.5 m engineered-storage contract. All 50 required probes retain nearby
water; none of 949 initialized observations loses nearby water. Original flood
and full drying definitions are negative on this candidate's frozen cohort;
worst masked flood is 0 km². There are still 145 exact-point wet losses.

Actual native hydraulic floors at t000/t005 pass the encoded target/footprint
and full-rim test (1.5 m footprint depth, 0.5 m freeboard); later floors were
not captured and remain unknown. All 58 configured controls match the package
at all 13 samples, and owned teardown is empty. Raw new-game-panel and startup
view checks remain failed for missing hash-bound visual adjudication. Producer
inspection does not rewrite them or supply human acceptance.

This is a different physical package and authored probe cohort, not a matched
source-only intervention or a rescore of PL-1072. It justifies further development
testing of the enclosed rule, not product adoption. The other prepared maps and
the natural-feature compiler are reported below. Natural-water construction,
nine-square nonregression, full runtime identity and the untouched holdout are
still required. Every feed promise stays unknown.

## Other enclosed-storage observations

Both remaining frozen cases completed once, without changing their bound
validators. Each retains its reservoir at all thirteen samples and has zero
masked flood under the original definition. Both still have positive full
historical drying labels on their own frozen package cohorts.

| Case | Game minutes | Minimum anchor depth | Required endpoint | Initialized nearby losses | Exact-point wet losses |
| --- | ---: | ---: | ---: | ---: | ---: |
| Dry-upland Europe | 60.113 | 1.34375 m | 1/1 | 113/482 | 166 |
| Lowland-river South America | 60.012 | 1.3125 m | 1/1 | 72/1144 | 125 |

All 20 European and 36 South American configured controls match their packages
at all thirteen samples. Actual hydraulic floors pass at t000/t005; eleven
later floors remain unknown in each run. Teardown is empty. Raw new-game-panel
and startup-view failures remain unchanged. Europe's endpoint views are
blue/occluded; producer inspection does not establish visual acceptance.
The old runtime still lacks full loaded-assembly identity. These are changed
physical packages, not source-only arms or historical certificate renewals.

## Source-only maintained-water inventory

`maintained_water_inventory.py` compiles captured rivers and streams into
clipped sectors of at most 512 m, with at most 64 m between planned probes.
Each captured polygon piece retains separate eight-neighbour native-16 m
components. Body probes use a world-aligned 64 m lattice after a padded 32 m
raster erosion. A small component retains an actual polygon-interior point.
Names never pool denominators. Explicit intermittent water and underground
pieces remain auditable exclusions from surface-perennial scope.

Every source entry is accounted for. Missing or unsupported features remain
unresolved, including authored omissions and infeasible streams. Old authored
plans identify omitted reaches by name/class rather than source-piece ID;
every matching piece conservatively remains unresolved, with its compiled
contracts retained. Unclipped or unsupported geometry is also unresolved.
No observed water pixel selects or removes a probe.

`maintained_water_plan.py stage FOLDER OUTPUT` creates a fresh physical protocol
with the inventory, probes, source/dependency-lock hashes and original flood
thresholds. `preflight OUTPUT` reproduces that compilation. `collect OUTPUT
NATIVE` requires the exact new native cohort, checks every engineered anchor
and every natural sector/body at initialization and every later sample, and
retains the original full drying and pooled gates as separate comparators.
A real prior Asian observation is rejected for its different probe hash.
No historical observation is rescored as a prospective feature result.

| Development inventory | Source entries | Unresolved entries | New probes | Authored initial natural-contract failures |
| --- | ---: | ---: | ---: | ---: |
| Europe | 528 | 27 | 280 | 76/85 |
| Asia | 82 | 9 | 365 | 8/49 |
| Lowland South America | 1034 | 646 | 15639 | 771/855 |

These initialization checks inspect the frozen authored depth grids only.
They are not new native observations, a holdout prefilter or a maintained-water
qualification. They show why a retained starter pond cannot establish complete
natural-water coverage. All three prospective feature protocols pass identity
preflight but retain incomplete support. None has a new native feature result.
The compiler is fixed at `81f301a`; the primary definition and twelve-square
panel hashes are unchanged. Holdout inputs remain unopened.

## Passive natural-body counterexample

Fresh experimental `natural_storage_candidate.py` reconstructs the original
source-bound base, then applies `natural_basins.py` inside captured perennial
lake footprints. The original starter search/masks are unchanged. The passive
rule adds no controls, permits no fill or more than 3 m cut, and requires an
untouched full eight-neighbour rim with 0.5 m freeboard and 1.5 m initial depth.
Open/controlled/protected bodies and infeasible geometry remain refusals.

Across the same five development cases, fresh base preparation retains both
original refusals. Europe constructs seven of 63 passive bodies; South America
two of 47; Asia refuses its one body. Authored initial natural-contract failures
change 76 to 68/85 in Europe and 771 to 769/855 in South America; Asia stays
8/49. These are source-grid diagnostics, not native maintenance or a prefilter.
V2 inventory records proven outside-square geometry separately and adds every
constructed-body anchor. In-square unsupported coverage remains unresolved.
`inventory-freeze-v2.json` retains the unchanged definition and panel hashes;
frozen v1 code and artifacts are unchanged.

The first European passive package completes 60.146 game minutes. **All seven
new exact-depth anchors fail:** each starts at 1.5 m, falls to 0.359375 m at
t005, and has no nearby water by t010. The one-to-nine-node bodies lose the
same depth per node; raw body-node sums are zero in t015 and later dumps.
Captured actual floors at t000/t005 are byte-identical, and all static body/
full-rim checks pass at their authored target stages. These are not actual water-
depth checks. Later floors remain unknown. Uniform loss suggests a
shared sink, not a proven evaporation mechanism. Static containment does not
establish retained water without a measured time-dependent budget.

All 20 existing controls match at thirteen samples. Masked flood is zero, but
full historical drying and both pooled gates fail on the new frozen cohort:
3/288 required endpoints retain water; 127/497 initialized nearby losses and
179 exact-point losses remain. Raw visual failures are not rewritten. Owned
cleanup is empty. The unchanged South American passive package is retained
without a native outcome, not rerun merely to repeat the failed premise.
The rule stays experimental and is rejected as sufficient maintenance for
these seven shallow bodies. No product promise or historical certificate.

`audit_natural_initialization.py PREPARED INVENTORY` reproduces the source audit.
Existing code omits excavation, water and forcing for rejected stream profiles;
the lake path skips components below eight nodes and does not excavate below
its bank-capped stage. Those are authored initialization mechanisms, not
exclusive causes of all observed native losses. Next work is explicit loss/
supply diagnosis and bounded replenishment; no holdout input has been fetched.

All 255 Python tests pass with one optional skip. New tests exercise physical
bounds, decoded packages and coherent probe omission. Serialized network-manager
bytes, source geometry and controls equal the fresh bases in all three prepared
exports. This is not nine-square native requalification. Shipping bytes remain
unchanged, and every ledger promise remains unknown.

## Reproduce the diagnosis

Run these read-only commands with the retained experiment root on blade:

```sh
uv run --locked --project tools/map-factory python tools/map-factory/audit_water_failures.py "$STUDY"
uv run --locked --project tools/map-factory python tools/map-factory/audit_coastal_stages.py "$STUDY/captures/low-coast-oceania" "$STUDY/staged/low-coast-oceania" "$STUDY/native/low-coast-oceania"
```

The emitted JSON binds the actual input/report/grid hashes. Coastal internal
correlations use already-fitted banks, not raw independent DEM measurements.
Static connectivity uses the native hydraulic floor, which differs from the
rendered terrain near structures. None of these audits changes original labels.

## Matched node-local regulation

An explicit experimental variant adds one type-1 lake regulator to each of the
28 constructed European body nodes. Both rates encode 128, with the existing
target stage. The existing radius model gives 14.525 m, strictly below the
16 m neighbour spacing; full node-footprint depth and the unchanged full rim
are checked. This is an experimental setting, not a physical-unit supply budget.
The general recipe also prepares 13 controls on the two South American bodies,
and zero in Asia. All prior refusals remain. No shipping default changes.

The matched European trial completes 60.071 game minutes. All seven anchors
and every captured constructed-body depth node remain exactly 1.5 m; all eight
engineered contracts pass. In the passive arm the seven new anchors dry.
Terrain, initial depths/velocities, all old controls, geometry, resources,
networks and full probe JSON are identical. Only the new controls and simulation
asset reference change. The full actual floor grids match at t000/t005; eleven
later floors remain unknown. Static stage-to-floor checks are not water depth.

This supports local regulation for these seven bodies, not evaporation proof,
isolated output-only causality, physical source-rate units or independent
replication. All 48 reported control tables match at 13 samples. Instantaneous
new-control flow ranges 0–1; it is not integrated flux. Natural contracts improve
from 1/85 passing to 9/85, leaving 76 failures. Historical full drying remains
positive: required endpoint 18/288, initialized nearby losses 117/497, exact
losses 169. Original masked flood remains 0 km². Raw visual/pooled failures and
runtime log errors remain. Every product promise is unknown.

Source replay also distinguishes one rejected unnamed-stream profile from
independent source-piece support. Five surface pieces share its grouped
component, but one selected route does not cover all branches. Of streams:5's
31 mapped nodes, none is within its 64 m initial-water route band; streams:3 has
23/70 within it. Repairing the global overbank fit alone cannot establish
complete stream coverage. This is geometric/source evidence, not hydraulic
feasibility or historical relabeling. Future stream work needs precise clipped
piece/branch contracts. See the phase-six development JSONs and the prospective
`replenishment-freeze-v1.json`; v1/v2 code and freezes remain unchanged.

## Prospective South American regulation and stream-piece feasibility

The frozen South American regulated package completes 60.066 game minutes.
Both new lake anchors stay exactly 1.5 m at all thirteen samples; all three
engineered contracts pass, all 49 reported controls match. Natural contracts
pass 65/855 and fail 790/855; historical drying remains positive. Required
endpoint is 9592/15642, initialized nearby losses 123/4436, exact losses 227.
Original masked deep flood is zero, but wet extent grows 12.11 to 35.63 km² at
0.1 m. This is not a thin-film explanation or new flood definition. The passive
South American package is unobserved: no matched native causal comparison is
claimed. Actual floor checks pass only t000/t005; later full floors unknown.

`waterway_pieces.py` and `stream_construction.py` add an explicit source-piece
catalog and complete native stream-graph geometry model. Every independent
clipped part and branch survives, including short/ambiguous parts; names never
merge denominators. A quantized DAG solver checks no-fill, cut<=3m, preserved
initial depth, >=1m channel-node depth and 0.5m untouched-bank clearance. Inferred
endpoint direction/cycles are not geographic flow proof. Fixed controls,
landing/corridors, all other water and other/excluded streams remain protected.
Missing protection evidence cannot pass. No mask is relaxed after refusals.

V3 inventory keeps the original contract points and adds exact source/clip/
component provenance. Asia accounts for four eligible parts in one graph and
refuses its bounds. Europe accounts for two in two graphs (one bound refusal,
one direction/bank unknown). South America accounts for 536 in 190 graphs:
45 numeric profiles feasible, 117 bound refusals, 16 cycles, 12 direction/bank
unknowns. All 45 numerically feasible graphs still fail fixed protection (44
other/excluded-stream contact, four infrastructure/other-water, overlapping).
All proposals/admissions remain unresolved. The two original base refusals stay
retained, not geographical-impossibility claims. Excluded/outside rows remain
explicit; v1/v2 code and artifacts are unchanged.

These are necessary authored-grid bounds, not materialized stream hydrology,
integrated supply/outlet/junction proof, actual floors, native retention or a
holdout prefilter. No stream CRP/native plan exists. The lake rate128 is not a
flowing-water budget. See `stream-piece-freeze-v3.json` and phase-seven JSONs.
Every product promise remains unknown; no default or capability-ledger adoption.

## Exact stream-refusal witnesses

`stream_witnesses.py` copies and replays the frozen stream protocols without
changing their compiler, masks, geometry, inventories or probes. Every guarded
node on each numeric-feasible graph is attributed to exact source clips or
control/landing/corridor/mapped-water evidence, with the original fixed radius.
Raw polyline distance is supplemental, not a replacement admission mask.

The phase-seven collective "protection" shorthand was incomplete: **44** of
South America's 45 numeric-feasible graphs contact foreign stream buffers;
**four of those** also contact mapped water/corridors. The remaining graph,
`stream-component:28` / `streams:145:clip:0`, has no such contact but reaches
column1080: its full bank would leave the square. All45 remain refused.
No mask is shrunk or refusal changed. Contact evidence covers255 graph/clip
pairs. Of the44 buffer-contacting graphs,43 share exact captured vertices
with explicit underground pieces;42 also approach a different surface source
row. These categories overlap. All79 shared-vertex records are endpoints of
the underground clips. This supports explicit mapped interface accounting,
not known hydraulic connectivity, supply, geological identity or acceptance.
No contact is another clipped fragment of the same captured source row.

Asia has93 bound-violating nodes:83 already conflict with local exterior-bank
limits,10 only after ancestor-stage propagation. Changing inferred direction
alone cannot repair the83 local conflicts under the same node/bank model.
The largest witness is streams:3 node[443,893], authored floor279.140625m,
with untouched bank[442,892] at273.8125m. The bank-capped stage273.3125m
would require6.828125m cut for1m depth, beyond the fixed3m. The largest
propagation-only deficit is1.84375m along a five-node streams:5 path.

All279 recorded Asian node/ancestor/limiting-bank records equal the rounded
captured input; largest input rounding difference0.005184m and input-versus-
captured-bank difference0.007796m. Exact geometry and authored-floor hashes
match the retained fresh base. Later Python earthwork/scalar rounding do not
explain these witnesses relative to captured inputs, which may already include
browser fitting and are not independent raw DEM. This does not establish geographic
impossibility: direction, nearest16m channel placement and exterior-bank model
remain provisional. No older actual hydraulic-floor observation is used.

See `stream-witness-freeze-v1.json` and `development/phase8-witness-summary.json`.
All three protocols replay. Nine new behavioral tests and17 targeted stream
tests pass; the unchanged271-test suite/one optional skip are carried forward,
not rerun. No physical stream candidate, native trial, rate tuning, holdout
access, default change, qualification or ledger adoption occurs in this tranche.
Every supply/outlet/junction and product promise remains unresolved/unknown.

## Complete source interfaces and configured forcing support

`stream_support_ledger.py` adds a separate read-only ledger over all three
prepared v3 protocols and their unchanged physical generation/package files.
`unprepared_stream_ledger.py` records complete captured geometry/prospective
contracts for both retained base refusals, with floor, configured controls and
initialization **unknown**, never a fabricated dry grid or empty control table.
The five cases retain1370 line rows,296 polygon rows,1227 clipped line parts
and583 mandatory stream parts. Every source row/hash, clipped endpoint,
branch/shared-part node, original sector and original full probe JSON survives.
Both base refusals remain refusals, not geographic-impossibility claims.

`waterway_incidence.py` distinguishes literal captured geographic equality from
exact integer/rational intersections in the declared projected1um model,
nearest16m vertex/raster contact and128m proximity. It retains crossings,
overlaps, singletons and polygon holes. None of these classes automatically
creates a hydraulic junction, outlet or flow direction; names do not merge
features. All scopes/outside/unsupported records remain explicit.

The ledger binds155 existing controls (Asia58, Europe48, South America49) to
their physical CRPs, unchanged terrain/depth/hydrology/geometry/probes and
original generation records. All43 encoded bytes per control are retained and
round-trip checked. This is authored package evidence, not native readback or
full runtime identity. Configured rates and source-radius footprints are not
integrated physical supply units or feature ownership.

Mandatory stream-sector authored initialization fails8/8 in Asia,3/3 in Europe
and687/715 in South America:698/726 in total. These are unchanged source-grid
diagnostics, not native feature observations, a historical rescore or a holdout
prefilter. Direct source-radius-model node contacts cover0/4,0/2 and9/536 stream
parts respectively. Lack of direct contact does not rule out downstream or
other dynamic supply. All supply/outlet/junction support stays unresolved.

**Decision:** a forcing-only edit to these packages cannot repair the mandatory
startup failures; direction-only fitting cannot repair the83 local Asian bank
conflicts under the same model. The one-node/full-bank geometry model and lake
rate128 are not a complete general flowing-water constructor. Keep all masks,
no-fill/cut<=3m/source-footprint bounds and refusals. A fresh complete plan must
cover every sector/branch, initialization, protected interfaces/open outlets and
an explicit bounded source model before native admission. No physical stream
candidate is produced. Next measurement should be a predeclared new source/
open-channel response diagnostic with reviewed owned telemetry/protocol, not
another observation of an unchanged dry geographic package.

All five new protocols replay. Fourteen new tests cover geometry incidence,
holes/overlap/large integer products, source-versus-model identity, complete
sectors/branches, missing physical support, wrong physical/control cohorts and
coherent omissions. A separate author-run code path verifies complete rows/
clips/sectors,3198 literal geographic incidences,155 raw control records and
989 natural initial contracts using a global nearest-wet-node tree. It is not
independent peer/native review. Prior271-suite/one skip,17 targeted stream tests
and20JS/10fixtures are carried forward, not rerun. Shipping bytes/defaults are
unchanged; every promise remains unknown. See `stream-interface-freeze-v1.json`
and `development/phase9-interface-summary.json`.

## Synthetic branched source-response preparation (no native observation)

`synthetic_source_response.py` prepares a separate synthetic diagnostic, not a
geographic constructor or qualification. One768m main plus384m tributary has
73 unique16m nodes, three complete natural sectors and three exact engineered
port anchors (24 probes). All six contracts initialize passing. Authored stages
fall99.5→99m, with1.5m initial depth; native flow is not yet observed. The
downstream boundary is an explicit common intake port, not an assumed natural
gravity outlet. No per-node lake regulators are used on the stream.

The fixed placement search retains14attempts before selecting(-384,0). All73
channel and152 full eight-neighbour rim nodes clear unchanged corridor/landing
protection and remain in the start tile. No fill, maxcut2.5m, untouched banks,
minfreeboard0.5m, and three single-node14.525m source-radius footprints with
>=1m stage-to-bed depth pass. Resources are packed after static admission;
final decoded terrain/water/control checks and byte-exact full resource-plan
re-encoding pass. This does not establish native floors/resources/UI acceptance.

Three source-only arms jointly set the two upstream outputs to0/32/128. ALL
THREE intakes remain128, downstream output remains0. Positions, targets,
terrain, depth/velocity, complete source geometry, probes, resource/network
bytes and other package assets remain fixed. The output-zero arm is NOT
all-controls-off. Encoded settings are not integrated physical flux or demand
capacity; joint changes do not isolate one source. All arms remain UNOBSERVED.

`synthetic_source_protocol.py` binds the complete physical/source/runtime
preparation and requires a separate independent review receipt before native
collection. The owned telemetry branch starts at exact6949182, not the old
checkout/build. `--water-study-every 0.25` is opt-in;
defaults/old collectors are unchanged. Unique sequence IDs retain missed
slots, all probes/controls and full depth/raw/current-floor/target-floor grids
at every new snapshot. Simulation/named water-counter brackets are not atomic
read proof. Module metadata/current file hashes are NOT complete loaded-image/
JIT identity or runtime health. No hooks, forcing or game-state writes added.

**Clock correction, without rewriting old evidence:** `CityOps.Water.frame`
reads SimulationManager's current counter. The previously reported18568
water-reported frames and18524stats frames are separate simulation-counter
reads, not a measured hydraulic clock. The73/64m net per-node loss remains
measured; no evaporation period, flux units or cadence follows from it. New
named-field availability/semantics require fresh native evidence, never retrofit.

Ordinary owned build,158harness tests,8new synthetic tests, Ruff/format/diff
and doctor pass. In-game smoke, cadence/performance, actual named counters,
native floor stability and runtime health remain not verified. User instruction
requires review/freeze before launching this runtime, so the normal in-game
harness PR check is explicitly deferred. Review PL-1226 owns that independent
pre-native judgment; it is not human-only testing or native replication.
The synthetic reference has73wet nodes, below the unchanged original100cell
reference gate; any original skip/unknown must be retained, not called a pass.

See `synthetic-response-freeze-v1.json` and
`development/phase10-synthetic-summary.json`. Holdout remains unopened, all old
failures/refusals/protocols unchanged, shipping defaults/ledger unchanged and
every product promise unknown. PR74 and telemetry PR80 remain draft/unmerged;
both have base conflicts which this exact-source tranche does not rewrite.

## Synthetic native response: zero versus two positive output settings

The user explicitly authorized the frozen observations in parallel with review
in comment01a1ff6d-7295-72b6-8481-d925cb4a2f5c. No pre-native review gate delayed
the runs; PL-1226 completed preparation review independently with no blocker.
All three source-only arms ran once on exact20efcf7/DLL368955b1. No package,
runtime, rate, geometry, mask, probe or old protocol was changed between arms.
All3intakes128 remained fixed; only two upstream outputs changed jointly.

| Outputs | Game minutes | Natural sectors pass | Engineered ports pass | Minimum exact port depth |
|---|---:|---:|---:|---:|
|0|60.134448|0/3|0/3|0m|
|32|60.044170|3/3|3/3|1.109375m|
|128|60.075281|3/3|3/3|1.140625m|

241new snapshots per arm/723total preserve all73channel nodes/24probes and
complete3control tables. All controls match every sample. All723actual full
hydraulic-floor grids share one hash across arms/times, with all authored-stage
source/channel/rim checks passing. This is captured stability, not atomic reads
or between-sample proof. No qualification transfers to geographic packages.
Output0first has a completely dry captured grid at7.561945min. Outputs32/128
retain all three sectors100%nearby at every sample. Minimum depth anywhere on
the73declared nodes is0.46875/0.625m respectively; every engineered port stays
above its frozen0.5m contract. Both pieces have nonzero horizontal velocity API
readbacks; these are not integrated physical discharge or a demand budget.

Zero scheduled slots are missing, but all strict0.30-minute cadence flags
remain false: maxgaps0.314722/0.333333/0.333333minutes. The original broader
primary sampling definition is complete. All four named fields are available;
counter semantics do not establish evaporation cadence or source flux units.

All raw no_flooding checks fail the unchanged73<100reference gate; flood labels
stay indeterminate. Historical full drying on these NEW synthetic cohorts is
true/false/false, not an old-study rescore. A registry scalar-value bug then
overwrote each completed verdict with an error. Raw files remain unchanged;
separate exact frozen-rule judge replays and SHA-bound lineage preserve failing
verdicts and that flood-reference failure. Frozen and authorization-aware
collectors agree on all primary/floor results. Reporting repair is not new
native evidence or a manufactured overall pass. The registry fix is CPU/actual-
report replay tested after all runs, with no new native trial on the fix.

Eight current on-disk reference hashes match; loaded Cs1Harness location/hash
is unavailable. Sidecars/module metadata are not complete loaded-image/JIT
identity or runtime health. Raw Bridge/TypeLoad logs and visual statuses remain.
All owned games/helpers are collected with empty teardown. Results review is
required before adoption. Both PRs remain draft/unmerged; all promises unknown.
See `development/phase11-response-comparison.json` and the phase-eleven report.

## Reviewed response and general head/terminal recipe

Independent results review PL-1229 passes the limited phase-eleven evidence
and reporting-only registry repair. It independently recomputes every contract,
all723snapshots/control tables and exact derived judgments from archived raw
data. The73-cell flood gate remains failed/indeterminate; point/grid nuances,
source-coincident port anchors, single trials, cadence failure and partial
runtime identity remain. Per-feature retention is not overall qualification.
No result-changing defect warrants a native rerun; no adoption occurs.

New `diagnostics/stream_ports.py` declares one intake128/output32 port at every
authored graph head and intake128/output0 at every terminal, with no internal
per-node regulators. It preserves every source part/branch and original sector/
probe. Quantized longest-head-distance offsets encode the tested0.5m/768m
grade; a shifted DAG potential solver keeps the existing bank/cut bounds.
Initial depth max(1.5m,oldwater) strengthens the former1mgeometry model. All
no-fill/cut<=3m/full8rim/freeboard/source-footprint/protection limits remain.
Directions are provisional authoring evidence; terminal ports are artificial
intakes, not proof of natural gravity outlet support or a physical flux budget.

The generic recipe exactly reproduces frozen synthetic arm32's73stages/beds,
full152rim, terrain/water bytes and three controls. This is CPU equivalence,
not another native replication. Six focused tests and scopedRuff/format pass.
Fresh additive protocols replay all5fixed geographic cases, retaining1370line
rows,296polygon rows,583mandatory stream parts and all old probes/controls.
Both original base refusals keep physical supportNULL/UNKNOWN.

No complete geographic candidate is admitted. Asia remains1bound refusal;
Europe2refused/unresolved; South America190refused/unresolved graphs:14new
numeric feasible,140bound refusals,16cycles,12direction/bank and8exterior-bank
unknowns. All14numeric profiles retain fixed foreign-stream buffer/interface
refusals (one also infrastructure/otherwater);31port proposals are UNDEPLOYED.
The new stricter14count is not a rewrite of the old45profiles. All old refusal
records and protocols remain, no mask/geometry/probe is moved to manufacture
admission. This is conditional model feasibility, not geographic impossibility.

The first CPU preparation rejected the structured review receipt before any
case output. Its failure log/empty attempt root remain; the actual schema was
fixed/tested/committed before the fresh final attempt. No native/Steam/install
action occurs in this tranche. See `stream-port-freeze-v1.json` and
`development/phase12-head-terminal-summary.json`. Source-authoritative bank/
junction/outlet geometry remains necessary before the review's recommended
complete geographic candidate can be prepared. All promises stay unknown.

## Acceptance still required

Exporter adoption needs successful native development counterfactuals, unchanged
nine-square connection/capability behavior, and the untouched new holdout.
The capability ledger must keep stable water unknown until exact-package
evidence satisfies its stated promise. A construction test, empty clearance
set, or skipped required cohort cannot promote a promise.

All native work uses blade's disposable test install and the existing Steam,
carbon-idle, offline, and ownership guards. No public merge or deploy is
authorized here. Human visual acceptance, populated-city behavior, continuous
retention between samples, and long-term operation remain unverified.
## Phase thirteen: lateral-authority diagnosis, not a widened stream

PL-1230 independently passes phase twelve's CPU rule/refusal accounting only;
its review child is closed after use. No geographic/native acceptance or promise
adoption follows. The medium finding is missing lateral bank authority, not a
bad native-floor read. No older runtime qualification is transferred here.

The review's proposed corner footprint adds every non-channel node four-adjacent
to at least two original channel nodes. A separately committed read-only tool
finds these additions are all ORIGINAL untouched eight-neighbour rim nodes.
Therefore this is prohibited footprint expansion under the current no-widening
and full-rim rule, not a correction justified by adjacency alone. No relaxed-bank
solve, changed mask, earthwork, new control or physical package is produced.

All five cases replay, retaining1370line rows/296polygons/583mandatory stream
parts, old controls/probes and both null-support base refusals. The four reviewed
South American components retain maximum potential-bound deficits4.1875,1.921875,
0.90625and1.5m. Their corner additions would retire36,2,8and21untouched bank
nodes. These are conditional mathematical refusals, not geographic impossibility.
A resolved local component would not qualify the whole map's other mandatory
features. Complete per-component deficit magnitudes are now reported.

A prospectively bound single public Overpass capture obtained82elements, no width
tags and7possible water polygons. A second source declaration was committed
before coverage analysis: all7literal polygon assemblies succeed; none covers
the four components'103channel+284rim nodes, with no sampled boundary uncertainty.
This supplementary contemporary source supplies no lateral-width/bank authority
for the proposal. It does not prove the real waterways are dry, transfer source
identity, supply bank elevations or resolve hydraulic connectivity.

Correction to phase twelve's evidence shorthand: its delivered artifact checked
stages/beds/rim/ports, not materialized grid bytes. A NEW phase-thirteen CPU replay
now materializes the ORIGINAL recipe and proves exact frozen synthetic terrain/
depth hashesfa9d04b8…/96c1edce…. This does not modify old evidence or constitute
another native trial. The proposed corner rule would also retire2untouched rim
nodes on that flat synthetic control; matching original stages cannot authorize it.

Nine new focused tests pass; scoped Ruff/format/diff and all five complete old/new
protocol replays pass. Source receipt-schema failure before case creation is
retained separately; fixed source was committed before final CPU preparation.
No native/Steam/install/preview/tab action occurred. Shipping/defaults/liveledger
and all prior evidence remain unchanged; holdout unopened, promises unknown.
See `bank-authority-freeze-v1.json` and
`development/phase13-bank-authority-summary.json` for exact source/data lineage.

## Phase fourteen: conditional source-line correspondence closes no bank gap

The captured stream writer discards featureID/tile/layerextent while preserving
points and selected scope tags. The pinned decoder2.0.3 was downloaded and its
package-lock SHA512 verified; it scales integer geometry by layerextent*2^zoom.
The default4096 is not recovered historical extent, and the MVT specification
does not establish the historical encoder's simplification/clipping error.

A new committed read-only protocol compares every complete source row672/683/
712/713/770/809 against all75public waterway lines in the retained phase13reply.
All6source rows fit the conditional2^26lattice exactly. Under one fixed
nearest-integer/no-simplification model,4rows are consistent (672/713/770/809),
and their hypothetical raw-subchain native walks change ZERO nodes. Rows683/712
reject rounding-only correspondence; sampled symmetric distance lower bounds are
1.25043/0.78131gridunits, against a conditional0.70712radius. No tolerance was
increased, historic identity assigned, source geometry moved or bank profile solved.

All four shared captured vertices and current public node-ID candidates remain
explicit. The two overlapping source rows770/809 correspond geometrically to
subchains of the same current public way, but their original rows/contracts are
not merged or dropped. Current way/node correspondence is not recovered historic
provenance, geographic flow, hydraulic connectivity, lateral bank or width authority.

The source-precision-as-bank-repair hypothesis is closed for these data. There is
no justified geometry revision or geographic admission, and all old refusals
remain. All5source/probe/refusal bindings retain583mandatory stream parts. Eight
new focused tests, scopedRuff/format/diff and the full6row correspondence replay
pass; unchanged constructor/native/broad suites are not rerun. The first attempt's
NumPy index serialization error/prospective freeze are retained; a typed-index fix
was committed before the fresh final protocol, without changing the question/model.
No game/Steam/install/holdout/preview/tab action occurred. See
`source-line-freeze-v1.json` and `development/phase14-source-line-summary.json`.
Shipping/defaults/liveledger and historical evidence remain unchanged; promises unknown.

## Phase fifteen: coastal floors stay fixed while captured heads fall

A new prospectively declared CPU audit binds the exact retained Oceanian
all-intake-off package457905c4/full27386probes0953f2ce. At t000/t005 native raw
terrain equals authored; actual current/target floors coincide and are unchanged
between samples. Actual floors differ from authored at40nodes (raises up to
15.109375m), affecting one full-cohort lattice probe but no MainDrain/Bulimba
source-mask node. Full named groups92/822 are separate from the pre-existing
failure-selected162. All source rows/excluded/outside/empty support are retained.
Static ocean/head-margin route counts remain unchanged; they are not flow proof.

Correction: all13old native samples already contain velocities. What was missing
was sub-five-minute transition timing and full floors after5minutes. Retained
nearby-water changes therefore warranted one new frozen15minute instrumented
observation, not another60minute repair run. Package/terrain/initial water,
167controls, source geometry, networks/resources and all probes remain fixed.

Clean owned runtime0ec989d/DLL368955b1 records61study snapshots over15.150001min.
All167full xyz/type/target/rate tables match every sample. All current floors
share hash43f4be73…, identical to retained t000/t005; all targets equal current,
all raw terrain equals package. Main nearby count92->87; Bulimba822->708.
Bulimba's rivers:50 heads fall from90m to86.421875–88.625m with captured floors
unchanged. This is not proof of integrated transport, evaporation, exclusive
missing supply or geographic impossibility. Velocities are API readbacks,
not physical supply/demand/discharge units. Between-sample behavior is unknown.

Requested cadence0.25min; maximum actual gap0.338611min, no missed slots.
All4named water counters available; reads bracketed, not proven atomic. Raw
verdict FAIL on unreviewed startup views; Bridge/TypeLoad failures retained
despite advisory game-error pass. Short original water/flood gates pass, but
60minute primary acceptance remains INCOMPLETE/UNKNOWN. Old historical drying
failures/thresholds/scores are unchanged. Loaded-image/JIT identity/runtimehealth
and human-only checks remain unknown. No holdout/default/ledger/promise adoption.

One preparation path failure retained; fix/tests committed before fresh final
protocol, no native repeat. Eight focused tests/scopedRuff/format/diff pass;
unchanged broad suites carried. Owned run collected and cleanup empty; subsequent
shared holder PL-1239 untouched. Independent results review precedes adoption,
not guarded measurement. See `coastal-floor-freeze-v1.json` and
`development/phase15-coastal-summary.json` for exact prospective/source lineage.

## Phase sixteen: wet boundary, transient interior, distinct channel connections

PL-1245 independently passes the limited phase15 measurements with two non-result-
changing findings; review child closed after use. Correction: rivers:50 is
Bulimba Creek, not Main Drain. Original archived report/receipt remains unchanged;
`development/phase16-erratum.json` corrects attribution. Main's source rows52/58/60
have49perennial nodes; row59has3explicitly excluded tunnel nodes. These are not
the full92Main probes. The archive's two traversal member names are repaired in
an additive normalized v2 packet; member bytes preserved, standard GNU extraction
passes. Neither reporting defect warrants a native rerun.

A newly committed read-only method records every named source-node path and all
61sample profiles. Labels come from source IDs/names/scope, never handwritten
identity assumptions. Every branch, stream, excluded/outside/empty record and
full27386probe timeline is retained. Floor-only shortest paths and conditional
minimax sill witnesses are distinct, not hydraulic connectivity or bank authority.
Sparse API velocities remain unknown off measured grid nodes; dry bed-plus-depth
is not a fluid free surface. Separate wet-only gradients avoid that substitution.

Using the exact exporter polygon raster: ocean boundary1780nodes,1778wet; the wet
boundary remains exactly90m, while2dry boundary nodes are not water at90m.
Ocean interior279009nodes draws down then partly rebounds; interior storage delta
at5.01min -11,560,375q and15.15min -5,346,696q. Non-ocean storage keeps falling
to -7,167,453q. These encoded depth sums are net storage, not measured source flux.
The review's preliminary polygon denominator differs; its counts are not silently
reused as this method's raster. Complete masks and method are explicitly bound.

Full-grid wet connectivity (depth>0.1m,4/8neighbours) rules out conclusions from
just one dry geometric path. Main row52starts10/10wet-connected to the boundary;
at15.15min9/10remain wet-connected despite wet heads86.42–86.92m. Main row60loses
wet connectivity while many nodes stay wet; row58partlydisconnects. Bulimba's
source nodes are already boundary-disconnected initially. A single disconnection
story does not explain every captured loss; sampled wet connection is not proof
of adequate replenishment/discharge. No exclusive sink/evaporation cause follows.

Nine new focused tests and complete core replay pass; old native/constructor/
shipping/broad checks are carried. No game/install/Steam/holdout action occurred.
All fixed masks/banks/limits/probes, historical failures and all promises remain
unchanged/unknown. No geographic stream admission or complete candidate follows.

## Phase seventeen: dense source-selected interface readbacks

PL-1247 passes the limited phase16CPU results and is closed after use. Its old
derived-manifest CLI paths remain historical; the new protocol/result omit CLI
paths and replay byte-identically under changed input path strings. Its trough
timing note is retained: the prior interior-storage minimum was7.570834min,
not the cited5.01sample (which was not declared the minimum).

A fresh native diagnostic addresses sparse vectors, not a repair/retry. All
27386original point objects/metadata remain;18816queries are added,46202total.
The20049node domain is selected from ALL MainDrain/Bulimba source geometry with
128mquery buffers plus32maround all static Main corridors. No wet component,
endpoint wet path or outcome-selected steps400–560 select probes. Query buffers
do not change banks/protection masks, source geometry or a surveyed basin width.
All167intakes remain zero, outputs/targets/positions/terrain/initialwater/
resources/networks/reference masks unchanged; package457905c4byte-identical.

Clean owned runtimee73138f/DLL368955b1 captures61snapshots over15.027779minutes.
All20049dense API nodes finite at every sample; all167full control tables match.
Current floors remain43f4be73…, targets=current, rawterrain=physicalterrain.
On the fixed754node Main52geometric path every API node is now measured (prior
endpoint28), but421are wet at endpoint and this is not a complete hydraulic
corridor. Its339wet adjacent pairs have model-parent-projected velocity median
-1.091API units (range-13.160to6.249), while source wet surfaces keep falling.
This is not integrated inflow/discharge, exclusive evaporation or a source budget.

Requested cadence0.25min, max actual gap0.323611min, no missed slots; all4named
counters available, reads not proven atomic. RawFAIL/startup/Bridge-TypeLoad
statuses retained. Short water/flood passes do not qualify60minute primary;
old60minute failures/gates/scores remain. Loaded-image/JIT identity/runtimehealth
and human-only/long-term/between-sample acceptance unknown. No new geographic
admission/holdout/default/ledger/promise adoption. Four new focused tests and
preflight/collection/portable replay pass; unchanged broad suites carried.
Owned game2594894and all helpers collected, teardown and final FIFO empty.
See `dense-interface-freeze-v1.json` and `development/phase17-dense-summary.json`.


## Phase eighteen: initial-inundation counterexamples from PL-1244

The opt-in source-faithful-v2 terrain policy is not water-safety qualified.
A new read-only audit of retained Boston/Charleston packages binds exact writer
874bf029, full source geometry/probes, native map identities and every saved depth
grid. Package terrain AND initial water equal native t000 bytes on both cases.
No game, install, source-input change, shelf restoration or terrain-branch edit.

Boston adds 5,826 >0.5m vertices (1.491456 approximate GAME km²), all sampled as
built-up by dated WorldCover and outside both fixed mapped-water and literal
captured ocean masks. Every added depth exactly equals quantized sea stage minus
authored terrain. Exact writer region.py starts a whole-grid sea-stage surface
and serializes max(0,surface-ground); the extra water is already in the package.
Runtime auto-fill is therefore not required to explain t000. This is not a full
browser-to-writer replay, surveyed inundation area or proof of a later loss sink.
By t060 only 186/5826 remain exactly wet and 380 retain nearby water; later drying
does not clear the initialization hazard. Baseline absolute hazards remain too.

The old growth-only judge includes t000 >0.1m water in its own expected reference:
all introduced >0.5m nodes are inside that reference. Its zero-growth verdict is
retained, not accepted as startup safety or rewritten under a new flood label.
Initial inundation needs a separate source-authoritative land/infrastructure vs
surface-water plan and final decoded/native startup checks. Do not hide failures
with a dry-land shelf, delete selected water without a declared rule, relax masks
or use a negative net area/later drying as a waiver. Source fidelity and safe
initialization are separate obligations. No constructor/admission follows here.

Charleston's complete authored 0.125–0.25m diagnostic cohort has 2064 vertices;
t005 exact/nearby wet is 55/540, t060 is 584/1588. All samples and rebounds remain.
This supports the retained shallow-water drying concern, not an independent
spatial dock/slip attribution, evaporation proof or complete natural-sector score.
Boston has 31 legacy points, Charleston zero; both native required-water gates
skip. All streams/branches/source rows remain, but full natural qualification is
unknown. No old probe/threshold/report/score/certificate is relabeled.

Six focused tests, source/physical bindings and fresh CPU analyses pass. First
CPU attempt is retained: an incorrect absent-flag required-count shorthand is
corrected before fresh attempt2, preserving the native gates' actual skip status.
Inundation/retention values are unchanged; no native retry. See
`initial-safety-counterexample-v1.json`, `development/phase18-initial-safety-summary.json`
and `diagnostics/initial_water_safety.py`. The original five construction cases,
583 mandatory stream parts/refusals/null support and PL-1191 holdout are unchanged.
Defaults/live ledger unchanged, source-faithful-v2 stays opt-in, all promises unknown.


## Phase nineteen: configured output rates and offshore drawdown

PL-1253 independently passes the limited phase17 measurements; its review and
acceptance receipts are authenticated, and the child was already closed. No
substantive physical/cohort/measurement defect warranted repeating that arm.
All six earlier review children are closed, but overall water construction is
not complete; there is no later waiting stage or complete geographic candidate.

New committed retained-data analysis partitions all1,168,561vertices into128
geometry/floor/control-distance/ocean-boundary strata, including empty support.
The time-selected early interval is0–4.821667min. Far from controls AND boundary,
87,259 deep literal-ocean vertices have median/p10/p90 head change-0.220359m per
game minute; near the boundary the median is zero. Only10/32near/far comparisons
have common floor/boundary support. This is not a universal ocean drawdown rate,
calibrated influence radius, causal sink attribution or physical source budget.

One genuinely new source-only observation zeroed all167remaining positive output
rates; all167intakes were already zero. Source records/type/targets/input-output
positions remain, so call it all ENCODED RATES zero, not sources removed or all
engine forcing off. Terrain/initial depth+velocity/resources/networks/full source
geometry/masks/full46202probe JSON remain exact. Only rate bytes in WaterSimulation
and its asset reference change; source-only package replay passes. No rate sweep,
new carve/fill/mask, repair or repeat-to-green. Exact native recipe57ac856;
protocol165359fb/package5c69540a, observed clean runtime9c41756/DLL368955b1.

The new15.031390minute run has61snapshots, finite20049dense-node values throughout,
all167controltables matching both zero rates at every sample, and the same actual
floor43f4be73hash at all times. Targets=current, rawterrain=physicalterrain. In
the fixed87,259-node stratum, early median/p10/p90 drawdown is-0.222625m per game
minute over0–4.842778min. Positive encoded outputs are therefore not necessary for
this observed drawdown. This does not prove passive control records irrelevant,
evaporation, integrated flux or a unique implicit/boundary mechanism. The two
actual windows/cadences differ slightly; no invented matched-time samples.

Local response is not unchanged: full Bulimba nearby retention is537/822 versus
709/822 in the output-enabled parent; Main is88/92 in both (exact67versus65).
Original full27386cohort nearby25048 versus25828. These are diagnostic groups,
not new natural-sector qualification denominators or a60minute drying rescore.
Raw FAIL/startup_views, Bridge11/TypeLoad3/ReflectionTypeLoad1 logs remain despite
advisory game-error pass. Short old water1119/1149 and masked deep flood0pass their
old gates;60minute primary remains incomplete/unknown. Requested0.25min cadence,
maxgap0.353056,zero missed slots, all four counters available; bracketed not atomic.
Both compared arms retain raw failures and later/between-sample/runtime unknowns.

The frozen experimental collector failed AFTER measurements/teardown and writing
the dense array: it added missed-slot lists as numbers. Failed output is retained.
A committed post-observation read-only adapter corrects exactly that aggregation
without changing frozen source, package, native data or thresholds. Derived array
equals the failed partial array; all four derived files reproduce byte-for-byte.
This is a reporting repair, not a new native run or raw-verdict rewrite. Only
after all replays, the future collector was fixed; replay of old plans now needs
own exact9ba351c recipe plus9c41756harness, not current modified heads.

Four strata, two pre-native rate, two adapter and two future-reporting behavioral
tests pass; scoped Ruff/format/diff and full CPU/physical/derived replays pass.
Old broad suites carried unchanged;22shippingfiles/default/liveledger and original
study remain unchanged. Owned game2891208/driver2888593 collected; teardown and
final FIFO empty, no preemption. No complete loaded-image/JIT/runtime-health or
human/populated-city/long-term acceptance. No holdout access or promises/adoption.
Phase18Boston/Charleston initialization constraints remain. Independent RESULTS
review precedes any adoption; this is not geographic qualification or a water fix.


## Phase twenty: zero serialized source records

One frozen source-only15-minute arm removes all167zero-rate records, with sea90, terrain/initialwater/velocity/geometry/masks/full46202probes unchanged. 61captures report[0]active sources. Fixed87,259-node early drawdown median-0.221735020m/game-min vs rate-zero parent-0.222625318; source-record necessity is tested under these inputs, not exclusive evaporation/flux/boundary mechanism or geographic qualification. Full128strata/actual-time traces retained.

All captured floors43f4be737024a039fa72c8ed651b4091272e1a9772238e53923d2a995443b138, targets=current/rawterrain=physical. Maxgap0.338889min vs requested.25; bracketed notatomic, between-sampleunknown. Rawfail/['startup_views'], Bridge/TypeLoad/visualfailures retained. Sixty-minuteprimary incomplete/unknown. Allcontrolsremoved is not all engine forcing off: implicit oceanboundary remains. No native retry/reportrewrite. New result requires independentRESULTSacceptance, not pre-nativepermission. PL1255limitedphase19review consumed/closed; allpromisesunknown. Seephase20summary/postcollectionbinding; prior physical/native/sourceprotocols unchanged.

Phase20 packaging erratum: original prospective ZIP328entries/326unique; two identical duplicate own-DLL/buildreceipt members. Additive normalized-v2 ZIP326unique preserves every unique byte/nativeplan. Old ZIP/receipt/binding immutable; normalization is post-observation packaging, not new physical prospectivity or game retry. See development/phase20-packaging-erratum.json.


## Phase twenty-one: sea parameter and corrected boundary axes

Phase20 supplemental strips accidentally varied CONTROL distance while labeled boundary distance (IDs76/77/78/79). Correct boundary strips holding controlfar are67/71/75/79, counts12678/36162/112065/87259. Originalreport/plots/JSON preserved; main79 far-from-both and all128early values unchanged. Fresh full3arm/61capture audit/byte-identical replay confirms literal1780ocean-edge nodes:1778wet heads90m,2dry notfree surfaces. All128metadataaxes and dry/missing support retained. No exact256-frame evaporation period or exclusive sink/flux inferred.

One new sea90→0-only15minute diagnostic, source table0/initialwater/velocity/terrain/fullgeometry/masks/full46202probes fixed. 61captures over15.065556min; primary79 actualpairedheadrate-0.22035947692768262m/game-min; endpointliteral-edgewet0/1780. Sea-parameter sensitivity only, not geographicrepair, budget, calibratedboundaryflow or60minutequalification. Rawfail/['startup_views'], runtimeerrors/cadencelimits retained. Newrecipe/source/prospectiveplan precede outcomes; actualruntimeddbff801ec6e4e89b4a1f12093ec06b9ed566d1c. PL1258limitedreview consumed; newlydiscoveredaxiserratum explicit. NewRESULTSreview required beforeadoption; allpromisesunknown. Seephase21summary/postcollectionbinding/axiserratum.

## Phase twenty-two: source-only local-supply envelopes

PL1259 passes the limited phase21 data and additive correction; already closed.
A new committed/frozen read-only method checks all five fixed development cases
plus every coastal source row, not just the failed named probes. All583 original
mandatory stream parts and both null-support base refusals remain. Both4/8-adjacent
full sub-stage floor envelopes are retained, not assumed hydraulic components.
At unchanged90m head, the Bulimba rivers50 envelope has1465nodes,307unmapped;
Main rivers52 reaches329323nodes,4227unmapped and the square edge. Those off-mask
nodes are already initialized wet, not predicted new flood or surveyed land.
Neither has the fixed half-metre full-rim witness; this does not make an open
channel a failed pond. Explicit open ports and water/land authority remain needed.
No source placement, CRP, new game, mask/bank/threshold/default change or admission.
This bounds the unchanged-head footprint-only proposal, not all supply designs
or geographic possibility. Four new tests and complete byte-identical CPU replay
pass. Seephase22policy/summary and postanalysis supply-envelope binding.

## Phase twenty-three: elevated spill envelopes and open ports

PL1260 passes the limited phase22 audit; consumed/closed. The immediate exterior
rim of floor<stage can approach zero on a sloping shoreline, so it is not itself
a surveyed containment failure. A newly committed/frozen read-only method checks
every prior head/component at stage+0.5m, BOTH4/8adjacency across all6inputs, retaining
583original mandatory stream parts and bothNULL base refusals. It never replaces
an original construction footprint or retires banks.

At90.5m, Bulimba rivers50's1465node base region joins the SAME332528node map-edge
region as Main rivers52. It includes835initially-dry off-mask nodes and intersects
the old control/corridor guards. These are conditional raster witnesses, NOT
predicted flooding, hydraulic reach, capacity or a new gate. Every open boundary
arc and exact raster source-endpoint incidence is retained; upstream supply and
unmeasured stage/outlet capacity remainNULL/unknown. All288packed network-node xyz
bytes match declared hydrology in each of4physical cases. No game/CRP/control/
earthwork/mask/probe/default change. Four new tests/full7file byte-identical replay
pass. Next prepared work is stage-ceiling vs complete source-contract compatibility,
not another offshore repetition. New CPU results not yet independently accepted;
all promisesunknown. Seephase23policy/summary/postanalysisbinding.

## Phase twenty-four: complete contracts against conditional escape ceilings

A new source-only compiler envelope retains every existing contract/point and
compiles the complete coastal cohort:962natural contracts/23113points, including
all42literal ocean rows.496coastal contracts fail authored initialization; this
is a source-grid diagnostic, not native acceptance or a historical rescore.
All5fixed cases plus coast retain branches/unsupported coverage and bothNULL
base refusals. Conditional whole-square4/8minimax escape ceilings minus0.5m are
compared with >=.5m exact engineered/95%natural >.1m nearby support and >=1m source
footprint intervals. No bank/protection/physical/probe change or stream admission.

Bulimba50's3sectors share a conditional own-raster interval87.46875–89.59375m
under8adjacency, including an undeployed1m source footprint. This is NOT a chosen
control/flow budget or known hydraulic outlet. A common-stage mismatch cannot
prove a varying-stage open channel impossible. Complete lateral water/land,
junction/inlet/outlet roles and supply remain unresolved; every promiseunknown.

Initial setup failure and NumPy JSON failure are retained. Freshv2 binds typed
JSON normalization without changing v1 arithmetic; freshv3 adds previously missing
per-ocean source masks/footprint accounting (all optimistic intervals/counts and
non-ocean contracts unchanged). Methods/freezes precede their own outputs; earlier
outputs known, not outcome-blind. Ten focused tests/scopedchecks, full23file replay
and8whole-grid Bellman/parent checks pass. Seephase24policy/summary/binding/report.

## Phase twenty-five: complete source-junction variable-stage construction plan

PL1261's actual limited CPU/design PASS is consumed and child closed. Its status
was stranded in_progress; obsolete in_review condition is disabled. Three bounded
reporting notes are corrected ADDITIVELY: feasible-only source minimum (NULL when
none), explicit empty ocean-raster uncertainty and natural/engineered counts split.
All old phase24 source/protocols/results/reports/receipts remain unchanged.

New committed/frozen method joins source pieces ONLY at literal shared geographic
vertices, not raster coincidence/name/proximity. All5cases+coast/837mandatory stream
parts, every river/branch/contract/probe and bothNULL base refusals retained. Complete
coastal geometry-only interfaces are now included. Provisional endpoint-floor
orientation drives a variable-stage potential, not a geographic flow assertion.

Conditional numeric profiles: South19(17variable), coast18(16variable); Asia0,
Europe0. Every profile still refused/unresolved for construction: no authoritative
lateral water-land/direction/inlet supply/outlet capacity, plus exact guards/cycles/
bank witnesses. No map-edge escape ceiling is misapplied as a closed-pond gate.
All37numeric profiles recheck full8banks/no-fill/cut<=3m/1.5m depth. Seven new tests,
scopedchecks and7file byte-identical replay pass; no game/CRP/control/mask change.
Coastal authored initialization496/962 still fails. All promisesunknown. Seephase25
policy/summary/report and postanalysisbinding; old evidence remains immutable.

## Phase twenty-six: literal open faces and external source authority

PL-1295's limited phase25 CPU/results PASS is consumed and the child is closed.
No result-changing finding warrants a native retry. The new same-cell guard rejects
conflicting targets or beds; all 37 prior numeric profiles are consistent here.
Of 35 open-port bank cases, 30 have exterior neighbours explained by literal
clipped endpoint faces; five retain 45 unknown exterior lateral occurrences.
No in-square bank is removed and no profile is solved or admitted. The registry
retains all 967 eligible river/stream parts, including 837 mandatory stream parts,
with unresolved piece-linked lateral, direction and port-plan authority.

The original BOM metadata HTTP 403 and a separate partial metadata capture are
retained. A fresh prospective feature query on the same coastal square captured
all 68 stream and five waterbody IDs, attributes and geometries in four HTTP 200
requests. These independent Geofabric records do not establish historical OSM
identity, replenishment or calibrated flow.

A separately committed/frozen overlay retains all 439 original clipped parts and
19 coastal open-port components. The five polygons cover none of the 5,096
in-square bank-union occurrences (not unique area); four clipped parts have some
polygon membership. This capture supplies no lateral mapped-area support at those
ports, not proof of absent real water or banks. All source geometry, masks, probes,
initial water and controls remain unchanged; 496/962 authored coastal contracts
still fail initialization. Twelve focused tests, scoped checks and byte-identical
seven-file authority/two-file coverage replays pass. No game, physical candidate,
default, ledger or holdout change. Next: the bounded Queensland source policy in
`development/phase26-next-qld-source-policy.md`. All promises remain unknown.

## Phase twenty-seven: Queensland mapped-area evidence

New committed/frozen readers capture the same coastal square. Production root
and layers 62/63 succeed; the catalogue HTTP 202 WAF challenge remains as partial
metadata, without retry or bypass. Current catalogue license text was not obtained.
All 734 line and 219 polygon records return exactly once in eight HTTP 200 queries.
Full attributes/geometry and raw classifications remain; cartographic inclusion
is not historical OSM identity, surveyed bank floor or outlet capacity.

The complete overlay retains all 439 clipped parts and 19 open-port bank unions.
Polygons cover 1,746/5,096 bank occurrences across 11 ports; one has full membership.
Perennial natural-watercourse areas, intermittent flats/inundation land and other
classes stay separate. Component13 (rivers56/57/67) has all 437 bank nodes inside
mapped perennial natural-watercourse area, but 225 old-control-buffer contacts and
all other guards, junction, stage and supply uncertainties remain. No bank, mask,
probe, geometry, control or old refusal changes; no admission.

Five focused tests and scoped checks pass; a two-file fresh replay is byte-identical.
All 217 new bound dependencies, 208 old phase26 dependencies and 22 shipping files
match. Coastal authored initialization still fails 496/962 contracts. No game,
default, ledger or holdout change. Next: the operation-local open-interface policy,
not another provider search or unchanged stage sweep. All promises remain unknown.

### Additive phase27 continuous-point qualification

Raster v1 remains unchanged (1,746/5,096). A separately committed/frozen even-odd
point test on all 14,952 source/bank nodes finds 1,422/5,096 bank occurrences across
11/19 interfaces, still one fully covered. No bank occurrence falls in its fixed
1 mm computational ambiguity band; source accuracy remains unknown. All 219 rings
sets are retained, including 12 multiring polygons. No source/probe/mask or native
result changed. Use these continuous membership counts for literal point claims;
Pillow raster counts remain a separate model. Eight focused tests, both two-file
replays and 220 bound dependencies pass. No physical admission or old refusal change.

## Phase twenty-eight: exact operations and literal exterior ports

New committed/frozen ledgers cover all six inputs, 967 eligible river/stream parts,
every contract/branch/probe and 322 unchanged control records. Conditional field
changes have exact uint16 grid bytes/offsets, not compressed CRP offsets. Undeployed
43-byte head/terminal proposals use experimental intake128/headoutput32/terminal0;
no physical supply budget. Contacts and actual proposed edits are separate; no
old refusal is cleared or mask shrunk.

The exterior-face rule removes zero in-square banks. Of 35 old open-port cases,
28 still fail bounds, two are cyclic and five lack exterior lateral evidence.
It adds no numeric profile. Existing 37 numeric plans imply 240 terrain and 240
depth-change occurrences; 234 touch operation-protected cells. One South cell has
conflicting independent plans; no combined map is materialized. Of 37 plans, 36
fail operation checks. The sole bounds-only fit is the same two-node constant-stage
coastal piece, not a flowing-water candidate. No geographic admission.

One coastal profile has serialized-bank margin 19q versus reference-native 32q,
so it fails source-space freeboard. No native-floor identity is transferred to
serialization. Both full seven-file replays match on exact f9ac1f8 source. A frozen
unit test expected the wrong solver status label; only two test literals changed
AFTER replays for future protocols. Eleven current focused tests pass. Frozen
source/failure/results remain, with no numerical or game retry. No CRP/grid/control
installation, native, default, ledger or holdout action. Coastal initialization
still fails 496/962 contracts; all promises remain unknown. Independent review
covers these combined construction results, not permission before measurement.

## Phase twenty-nine: complete startup-support obstruction

PL-1300's limited source/CPU/design PASS is consumed and already closed. Following
its recommendation, a new frozen audit separates fixed masks, full operation
protection and unique source support across every original six-case contract.
All original natural initialization counts match. Even the deliberately relaxed
fixed-mask view leaves 530/1951 contracts without enough startup support; full
operation preservation leaves 985. These are conditional water-edit-policy bounds,
not geographic impossibility, hydraulic construction or permission to relax masks.
Both base refusals remain NULL; 12 engineered exact-depth checks remain unknown.

Original v1 outputs remain. A newly committed/frozen additive subset correction
changes only ownership-view unknowns already bounded by known full-mask failures;
no true value, input, mask or physical result changes. Eight focused tests and
complete 19-file v1/seven-file derived replays pass byte-identically. Independent
node verification covers all 39394 natural points. No game, CRP/control/new-water
field, shipping/default/ledger or holdout change. Coastal496/962 failures persist.
Next: field-specific protection authority and an explicit joint operation contract,
not a provider search, rate sweep or quiet protected-water relaxation. New results
need combined construction/results acceptance before adoption. Promises unknown.

## Phase thirty: field-specific protection obligations

A new frozen contract traces source scopes separately for terrain, initialized
depth/velocity, old controls and new port proposals. Starter/stream whole-envelope
exclusion is not a permanent geographic prohibition on target-water reconstruction;
the natural-body constructor already distinguishes its own lake from other water.
No lack of a field prohibition is treated as permission. Every original mask, bank,
control byte and old refusal remains; no edit or candidate is authorized.

All39394naturalpoints/1939487nearby-nodeoccurrences across six inputs are annotated.
Original per-body buffer unions equal the old masks exactly. The first European
lake witness separates30original-interior from17buffer-only nodes; neither is
made editable. Own-buffer membership cannot become a water footprint. Open-stream
other-water/junction/supply obligations remain. Both base refusals and engineered
exact-sampling unknowns stay. Old496/962coastalstartupfailures are unchanged.

Five focused tests and a complete15file replay pass. New field labels are not
constructability, native acceptance or calibrated flow. A future depth writer must
respect compact velocity-array packing, not assume stable offsets. No CRP/water/
control serialization, game, shipping/default/ledger/holdout action. Combined new
construction/results need independent acceptance; all promises remain unknown.

## Phase thirty-one: joint-node water-only plan

PL1302's limited phase29/30CPU/field-contract PASS is consumed and closed. Its
conservative oldbunknowns and scalar-label overlap findings stay; new nodes use
full simultaneous obligations, not those labels as permission. A fresh frozen
joint schema retains all six inputs, original source/port topology and every
contract/probe. All39394points/1939487nodeoccurrences keep original masks.

Only original lake interiors with complete dry source rims/no interface receive
conditional fixed-bed stage/depth intervals. Open waterways/boundaries never get
a closed-lake cap. Of19nonempty occurrences, all16unique nodes are ALREADYwet and
every depth delta is0. This lever repairs no dry startup point under its rules,
not geographic impossibility or permission to relax protection. No physical plan.

First CPUattempt's coastal schema error and five partial outputs remain. New
committed/tested reader plus fresh v2protocol completes all six cases; firstfive
payloads unchanged exceptpolicyheader. Seven focused tests/full7file fresh replay
pass; complete source/interval/domain verifier passes. No game, CRP/grid/control,
shipping/default/ledger/holdout action. Next: implement value/control-preserving
water-payload codec/verifier with synthetic packing fixtures, not an old native
or rate retry. All original startup failures and promisesunknown remain.

## Phase thirty-two: value-preserving initial-water payload codec

The experimental codec retains full depth and three compact raw-value arrays by
their exact wet/adjacency domain keys. Persistent values never default to zero;
new keys require explicit values. Nondecreasing depth, raw43 control order,
known header/trailer/tail and non-water assets are checked. Unsupported layouts
fail closed. Packing domains are not calibrated physical velocity/flow units.

All four unchanged physical packages round-trip byte-for-byte in memory, with
322 controls preserved; two base refusals stay NULL/unknown. Six predeclared
synthetic topology-growth fixtures preserve nonzero raw values and exact source
sentinels. A legal alternate RLE encoding has equal values but different bytes,
reported separately. No changed geographic CRP/grid/native plan was produced.

Seven focused tests and a full25file fresh replay pass. The first test reused a
depth-removal fixture incorrectly; its frozen failure/source remain, followed by
a committed test-only correction and fresh input freeze. Codec/physical inputs
did not change. Geographic changes are always refused: phase31's only nonempty
intervals remain identity, not a selected joint initialization/safety/port plan.
Combined phase31/32 results require independent acceptance before adoption.
No shipping/default/ledger/game/holdout action; original failures/promisesunknown.

## Phase thirty-three: explicit boundary and coupled bed/stage contract

PL1303 limited phase31/32PASS is consumed and closed. Its low packing-name note
is retained: native +row is +z/north; the frozen third compact-array label is not
a compass/flow claim. New schema uses explicit index relations.

The complete six-case boundary specification retains8787site records (including
excluded/proximity/unknown entries), with5666active missing boundary contracts.
Literal endpoint/source incidence is not hydraulic communication. Selected roles,
direction, lateral authority, receiving stages, supply/outlet retention and exact
field-operation proofs remain separate unknowns; no sea/target/name joins fill them.

A new conditional coupled-bed enquiry preserves the old lake-interior/rim scope:
215node occurrences (211unique entry/nodes) could fit depth/freeboard within3mcut;
447cannot fit that bounded model. ALLpositive cuts remain forbidden by current
unchanged-terrain obligations. No selected bed/stage/water edit or candidate follows.
The19old zero-minimum-cut occurrences and all original startup failures remain.

Both initial reader failures stopped before case output; old251/252source bytes,
freezes/logs remain. New committed v3 preserves fieldless authored plans and all
12engineered exact-sampling unknowns. Nine focused tests/full7file replay and a
complete producer cohort/algebra check pass. No game/shipping/holdout action.
Next: source-selected complete interface observations from exact retained native
grids, not a new run or an invented authoritative boundary condition. Phase33new
results are not independently accepted/adopted; all promises remain unknown.

## Phase thirty-four: complete retained interface observations

A new source-selected cohort retains all2877coastal interface/end/body/authored
site records.2281have in-square grid support;596retain explicit no-support status.
The diagnostic uses25582native cells and ALL22120existing exact-grid API aliases
(21731cells);389duplicate aliases stay separate,3851cells lack API vectors.
No new query/probe/game or source/geometry change occurred.

Across the retained61captures,23422cells have an observed wet head different from
the serialized90m reference at least once;23362vary over observed wet samples.
Dry cells have no reported free surface. Six cells remain wet/exact90m throughout.
These are diagnostic cell counts, not hydraulic bodies, primary denominators,
capacity or a prescribed boundary envelope. Every24literal outside endpoint is
reported, including excluded pieces and dry support; exact-cell drying does not
rescore the original nearby-water contract.

Seven focused tests/full12file replay and direct producer verification pass.
All289raw native files, original query objects/clocks/controls, actuale731runtime
provenance and package/floor/source bytes are bound. No old runtime identity is
retrofitted to the later05bjournal head. Otherfivecases stay authored-only/NULL.
Combined phase33/34 needs independent RESULTS acceptance; no candidate, field edit,
shipping/default/ledger/holdout or native change. Sampled stage ranges constrain
a proposal; they do not supply missing direction/lateral/supply/outlet authority.
Fullhour/runtime/visual/Boston/Charleston/original failure limits stay; promisesunknown.
