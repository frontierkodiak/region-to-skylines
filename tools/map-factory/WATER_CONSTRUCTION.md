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
