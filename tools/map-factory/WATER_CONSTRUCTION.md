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

The diagnostic closed-basin constructor finds feasible geometry in four of the
five reservoir development start tiles under the stated protection and cut
limits. It refuses mountain-river Asia. That is a construction-limit result,
not geographic impossibility. No constructed candidate has run natively yet.

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
feature-inventory compiler and evaluator must still be implemented and bound
before holdout access. This specification does not promote a product promise.

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
and stream outputs and every intake; it is prepared but not yet observed.

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
