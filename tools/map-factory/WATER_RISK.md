# Per-square water-risk screening

The page and CLI screen the generated initial terrain, water and control/profile
plan for **any selected square**. The screen reads no fixture identity, native
result, place name, source ID or admission fingerprint. It does not change the
map, harness, codec or original native acceptance gates.

## Export behavior

- A flagged square shows its physical reasons before download. The page requires
  **Download map anyway**; the CLI stops with exit 5 unless `--allow-water-risk`
  was explicitly passed. The JSON report is retained either way.
- Invalid/missing inputs decline the map export. The override cannot bypass a
  declined check. Heightmap export remains available.
- No flags means *no screened flags*, not native qualification or a guarantee.
  Inputs outside the measured calibration ranges also require review.
- Changing the selected square, options or name invalidates pending approval.

The existing landed physical writer and historical admission replays are retained
unchanged; no new fingerprint entry is added. They are not the general solution:
this screen runs even when no historical replay matches. The assessment is returned
separately from the generation receipt so old CRP identities remain verifiable.

## Shared rule

`water_risk.measure` reads complete encoded native-order initial grids and the
ordinary generated hydrology. It separates boundary-connected sea water from
inland water, measures lower-bank freeboard, narrow/shallow initial water,
native-radius control exposure, nominal input/output capacities and fitted-profile
constraints. Nominal capacities are **not actual flow**. Static exposure is **not
simulated flood area**.

One conservative rule flags low coastal freeboard (<1.5 m), source disks exposing
at least 0.01 km² of initially dry low ground, a bank-limited channel-length
fraction over 10%, withdrawal/supply capacity over 2, or shallow narrow initialized
inland water. These are retrospective advisory operating points, not new native gates.
There are no per-region branches or learned geographical splits.

### Retained water, not omitted streams

The previous drying explanation was wrong: `unforced_infeasible_stream` reaches
are deliberately left **uncarved and unforced**. Their length is now a separate
map-content note, not a drying prediction. Adverse fitted profiles alone no longer
flag drying either; the writer may have rejected those profiles before excavation.
Notes still reach the app/CLI review, but do not enter binary drying scores.

The new `narrow_film_km2` signal measures **water actually present in the encoded
initial grid**: inland wet nodes with dry neighbours on both opposite sides of
at least one grid axis, and depth at most 0.25 m. The depth is the writer's stream
startup-film cap, not a threshold fitted to recover a case. Positive area flags
fragile shallow water. A broad pool's ordinary one-sided shallow rim and a deep
one-cell channel do not trigger it. Sea water is excluded. The signal does not
read an omitted line, native observation, map name or hash, and does not assert
that every flagged node is a carved stream or will dry in a forward simulation.

| Current fixture | Shallow narrow initial water (km²) | Omitted mapped length (note only) |
| --- | ---: | ---: |
| Asheville | 0.081408 | 63% |
| Innsbruck | 0.014848 | 75% |
| Rio | 0.016128 | 14% |
| Pittsburgh | 0.172800 | 40% |
| Charleston | 0.051456 | 13% |

The same grid rule fires in all five and all 50 bound full runs. This corrects
the explanation, **not the lack of drying-negative calibration**. Its false-alarm
rate and geographical discrimination remain unknown; it is not a validated
causal attribution of the lost monitored points. The prior always-warn result
cannot become evidence of discrimination by changing the reason.

PL-1072 corrects the neighbour definition: adjacent sea remains wet, rather than
standing in for a dry channel bank. This changes 22 of 72 old input-bound feature
rows, including the two fixture areas above. No old classification or native
label changes. The [independent calibration protocol](WATER_CALIBRATION.md) fixes
a new 30-square panel and a separate old-data-only candidate before game outcomes.
The [completed native study](calibration/pl1072-frozen/HOLDOUT_REPORT.md) rejects
both candidates for clearance. Flood flags do not reduce observed risk; drying
equals always-warn. Neither candidate replaces the deployed warning model.

### Coastal margin above sea level

This implements complaint #2 in [the player survey conventions](CONVENTIONS.md#what-real-terrain-maps-get-wrong):
flood-prone shores with too little freeboard above sea level. The metric is the
10th-percentile height of **initially dry land within 64 m of boundary-connected
sea water**, minus the encoded sea level (`floor(sea_m * 64 + 0.5) / 64`). It flags
flooding below the shared 1.5 m warning margin. The coastal land area is also
reported. An absent coast cannot trigger this flag.

The general nearest-water bank statistic remains separate: a low inland riverbank
must not be described as a low sea-facing shore. Low coastal margin predicts
flooding, not drying. The app/CLI explanation reports metres above/below **sea
level**, not merely nearby water. This is a static input signal, not a tidal,
wave, transport or forward-simulation model; original flood masks and the
0.05 km² gate are unchanged.

Focused tests failed before this correction: a 5 m coastal shore was flagged
because inland banks had only 1 m freeboard, and a 0.5 m coastal margin was also
incorrectly called drying. The corrected tests cover both cases, sea-datum
translation and no-sea inputs. These synthetic tests validate the measurement,
not native hydraulic performance.

## Calibration: what the numbers mean

The registry census has **161 distinct run paths** (167 entries, deduplicated by
path). Populated/saved-city runs are excluded before their reports are read. Of
57 complete sixty-minute empty-map soaks, **50 have exact package, initial-grid
and encoded-control bindings**; seven source paths were overwritten and cannot
be scored honestly. All 57 are repetitions/versions of **five landscapes**, not
57 independent geographical examples. The 50 scored runs contain 46 package
hashes; version diversity is not geographical diversity.

| Full 60-minute scored runs | TP | FP | TN | FN | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Original flooding failure | 12 | 18 | 19 | 1 | 40.0% | 92.3% |
| Monitored-water loss | 50 | 0 | 0 | 0 | 100% | 100% |

**The drying row cannot establish discrimination:** there are zero observed
drying-negative full runs. An always-warn baseline has identical drying metrics;
specificity/false-alarm rate is unmeasurable. All five current fixture assessments
warn. The flood screen improves on always-warn precision (26%) but still flags
18 flood-passing runs. Results are retrospective, not an untouched holdout.

| Landscape | Flood failures flagged | Flood failures missed | Flood-passing runs flagged | Flood-passing runs not flagged |
| --- | ---: | ---: | ---: | ---: |
| Asheville | 0 | 0 | 0 | 10 |
| Innsbruck | 0 | 0 | 0 | 9 |
| Pittsburgh | 1 | 0 | 9 | 0 |
| Rio de Janeiro | 9 | 1 | 2 | 0 |
| Charleston | 2 | 0 | 7 | 0 |

The corrected coastal metric exposes one miss: historical
`PL-857-sustained-water/r4-north-rio-60/rio`, package `e1844ef2…`, originally
failed at 0.4019 km². Its coastal margin is 2.78125 m while the general-bank
statistic is 0.390625 m. It still gets a drying warning, but that does **not**
erase the flood false negative. The initial screen's flood precision/recall
was 41.9%/100%; this correction is 40.0%/92.3%. No cutoff was changed to recover
the missed case, and its flood cause was not diagnosed in this unit.

Flood labels retain each run's original `no_flooding` verdict and reference mask;
older initial-water references are reported separately from mapped/frozen ones.
Display rounding cannot turn an original failure into a pass. Drying means at
least one initialized monitored point ends dry **and not within 64 m of water**,
or an original required-water point is lost at endpoint/sampled-throughout.
Optional monitored water is included. This is an advisory target, not a change
to the original 95% required-water gate. Exact-point wet loss is reported separately
and cannot be erased by nearby coverage. Neither label exhaustively measures
visible dry beds, continuous channels or every frame.

The report now aggregates exact-point loss separately from isolated loss:

| Landscape | Runs | Initially wet readings | Exact-point dry at end | Also no water within 64 m |
| --- | ---: | ---: | ---: | ---: |
| Asheville | 10 | 54,285 | 24,050 | 20,340 |
| Innsbruck | 9 | 25,601 | 12,950 | 11,612 |
| Rio | 12 | 34,166 | 5,816 | 2,216 |
| Pittsburgh | 10 | 49,560 | 10,596 | 9,172 |
| Charleston | 9 | 57,030 | 9,605 | 8,253 |

These are summed endpoint readings across repeated versions/runs, **not unique
geographic points, every-frame losses or causal differences between packages**.
Gains elsewhere do not cancel them.

Sixteen scored full runs lose some required water, but **none of the 57 full runs
fails the original 95% required-water gate**. Gate-failure recall therefore cannot
be estimated from these full runs. Treating that gate alone as the drying target
would hide the optional dry streams this screen must address.

All seven unscored full runs have monitored-water loss. They are unknown
predictions, not passes or demonstrated misses. Assuming all seven were missed
gives a demonstrated drying-recall lower bound of **50/57 = 87.7%**. No evaluated
drying false negative exists; that is not evidence there are none on new geography.
Passing short runs are censored, not sixty-minute negatives.
The extended dataset has 68 runs with at least one usable label; short observed
failures are included only as positives. Product copy uses the full-run figures.

Two earlier learned-tree screens were rejected. Their leave-one-square-out flood
recall was 13.6%, despite attractive apparent fit. Their reports remain in the
delivered audit bundle; they are not deployed models or independent validation
of the final shared rule.
Those prototypes used the narrower required-water-only drying target, not the
final optional-inclusive target; their drying scores are not directly comparable.

## Reproduction and contracts

```sh
uv run --project tools/map-factory python tools/map-factory/water_risk_corpus.py \
  ~/.local/share/cs1-harness/runs.jsonl --out /absolute/fresh-output
uv run --project tools/map-factory python tools/map-factory/calibrate_water_risk.py \
  /absolute/fresh-output/rows.json --coverage /absolute/fresh-output/coverage.json \
  --model /absolute/model.json --report /absolute/calibration.json
npm test
npm run test:fixtures
```

The versioned `pl912-water-risk-v1` contract contains the sanitized source-bound
corpus and coverage, the exact model and five Python assessment goldens. Ten
complete reference/shipping Pyodide exports must reproduce existing CRP bytes
and the Python risk features/decisions. This is metadata/byte-conformance proof,
not a new native soak. Predecessor contracts, native receipts and failed cases
are retained. An already-stale nonshipping short-driver binding on main is
resolved by preserving its actual native-tested source separately from the
unchanged current driver; no historical game is attributed to today's tool.
The archived predecessor active pointer is hash-checked; a whitespace-only
mutation is rejected. Excluded populated/saved-city rows retain anonymous path
hashes: their identities are reproducible only with the private live registry,
not recoverable from the published coverage alone.

## Release recommendation

The screen supplies a general, explainable **per-square warning**, but the present
corpus cannot substantiate a class of drying-safe squares, and flood false alarms
remain frequent. Hold the announcement of an exporter that reliably clears safe
squares until geography-disjoint validation demonstrates useful **both flood and
drying** discrimination, including genuinely drying-negative examples. Do not present the
100% retrospective drying precision as that proof. Caleb owns the announcement.

The existing Rio full-run flood failure (0.062464 km² versus 0.05), dry banks and
exact-point thinning remain open. Charleston's correlation 0.6891 versus 0.9 and
extreme-point failures remain separate elevation risks, not predictions this
water screen can clear. No first-wetting trace or repair candidate ran for this
redirected unit; no physical package inherits a new native qualification.
