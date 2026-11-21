# Results: outside-connection road, ship and air queries

Retrospective, query-scoped. One question per request: does the native
pathfinder return a complete path between the two requested literal boundary
offsets? The observations already existed before this model; nothing here is
prospective or blind, and no new capture was made.

Exact protocol, copied from the accepted study's collector:

> `PathManager.CreatePath`; vehicle `Car` / `Ship` / `Plane` by mode; category
> `All`; laneTypes `Vehicle|TransportVehicle|CargoVehicle`; seed 857;
> maxLength 100000; literal `[segment, lane, offset]` endpoints.

A **positive** is a complete, released native path whose first and last returned
positions equal the requested offsets. A **negative** is a complete, released
request whose native result reports `success = false`; that is an observed
failure of that exact request, never a geographic negative.

## Inventory

| Stratum | Rows | Scored | Why |
| --- | ---: | ---: | --- |
| distinct-edge literal boundary | 342 | yes (primary) | the two ends sit on different map edges |
| same-edge literal boundary | 36 | yes (separate) | the two ends sit on one map edge |
| midpoint diagnostic (offset 128) | 378 | no | each is the correlated repeat of one boundary request |
| earliest collector, no `position_kind` | 64 | no | protocol fields absent: unknown, not a failure |
| no request recorded | 56 | no | coverage gap, not a failure |
| **total** | **876** | | |

All 876 rows bind to their raw observation bytes: the recorded SHA-256 of every
observation and network snapshot matches the decompressed file, every assembled
row equals exactly one raw `paths` entry with the same request and the same
result, and the label recomputed from the raw result equals the recorded one.
Three openings (asheville attempt-1, pittsburgh native-v2-2, rio native-v2-1)
failed before a network snapshot existed; they carry no usable request and are
recorded as anomalies.

| Mode | Primary | Same edge | Successes | Failures |
| --- | ---: | ---: | ---: | ---: |
| road | 316 | 36 | 67 | 249 |
| ship | 16 | 0 | 16 | 0 |
| air | 10 | 0 | 10 | 0 |

Midpoints are not independent: 378 of 378 offset-128 requests return exactly the
outcome of their boundary sibling on the same segments, lanes and direction.
Two openings of an unchanged package repeat eight eligible queries; all eight
agree. Neither repetition is pooled into the counts below.

## Road endpoint roles

The 316 distinct-edge road requests split by the recorded roles of their two
endpoint nodes:

| Start role | End role | n | Successes |
| --- | --- | ---: | ---: |
| OneWayIn | OneWayIn | 18 | 0 |
| OneWayIn | OneWayOut | 128 | 0 |
| OneWayOut | OneWayIn | 128 | 67 |
| OneWayOut | OneWayOut | 42 | 0 |

Only the `OneWayOut → OneWayIn` pairing can succeed. The directed lane model
derives this from the lane direction grants rather than from the role labels;
the labels are recorded here for the reader, and the model never reads them.
188 of the 316 cases are therefore settled by direction alone, and 128 remain a
genuine reachability question.

## Frozen family, primary stratum

Twelve generic rules per mode, frozen before any prediction was scored. Junction
pairing is `all`. `lane:any_lane:forbidden` is the registered primary rule.

| Rule | TP | FP | TN | FN | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| always-fail | 0 | 0 | 249 | 93 | null | 0.000 | null |
| always-candidate | 93 | 249 | 0 | 0 | 0.272 | 1.000 | 0.428 |
| weak_component | 93 | 249 | 0 | 0 | 0.272 | 1.000 | 0.428 |
| directed_segment | 93 | 19 | 230 | 0 | 0.830 | 1.000 | 0.907 |
| lane:any_lane:forbidden (primary) | 93 | 19 | 230 | 0 | 0.830 | 1.000 | 0.907 |
| lane:any_lane:allowed | 93 | 19 | 230 | 0 | 0.830 | 1.000 | 0.907 |
| lane:index_same:forbidden | 85 | 19 | 230 | 8 | 0.817 | 0.914 | 0.863 |
| lane:index_same:allowed | 85 | 19 | 230 | 8 | 0.817 | 0.914 | 0.863 |
| lane:orientation_index:forbidden | 85 | 19 | 230 | 8 | 0.817 | 0.914 | 0.863 |
| lane:orientation_index:allowed | 85 | 19 | 230 | 8 | 0.817 | 0.914 | 0.863 |
| lane:index_mirror:forbidden | 59 | 8 | 241 | 34 | 0.881 | 0.634 | 0.738 |
| lane:orientation_mirror:forbidden | 59 | 8 | 241 | 34 | 0.881 | 0.634 | 0.738 |

Four distinct behaviours only. `directed_segment` and both `any_lane` variants
are identical; `index_same` and `orientation_index` are identical; the two
mirror rules are identical; reversal permission never changes a prediction.
The fitted member is therefore a tie among three rules, resolved by the frozen
rule order to `directed_segment`. The study does **not** claim that lane
continuity is unnecessary in general, only that these 378 queries do not
distinguish it from segment-level directed reachability.

## Per mode

| Mode | n | TP | FP | TN | FN | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| road | 316 | 67 | 19 | 230 | 0 | 0.779 | 1.000 |
| ship | 16 | 16 | 0 | 0 | 0 | 1.000 (trivial) | 1.000 |
| air | 10 | 10 | 0 | 0 | 0 | 1.000 (trivial) | 1.000 |

Ship and air are one-class: every complete request in the retained evidence
succeeded. Their precision is arithmetically 1 and carries no information, no
rule can be distinguished on them, and only their positive consistency is
checked. This is a limit of the retained evidence, not a property of ships or
aircraft.

## Same edge, and groups

Same-edge literal boundary requests, best rule: TP 9, FP 0, TN 27, FN 0
(precision 1.000, recall 1.000).

| Group | n | TP | FP | TN | FN |
| --- | ---: | ---: | ---: | ---: | ---: |
| PL-1121 first openings | 114 | 27 | 0 | 87 | 0 |
| PL-1142 targeted openings | 264 | 75 | 19 | 170 | 0 |
| runtime-bound native context | 264 | 75 | 19 | 170 | 0 |
| collector-recipe only | 114 | 27 | 0 | 87 | 0 |

The fidelity split is the same partition as the study split here: every targeted
opening recorded a native entry context and every first opening did not.
| asheville | 20 | 2 | 0 | 18 | 0 |
| boston | 24 | 6 | 0 | 18 | 0 |
| charleston | 24 | 6 | 0 | 18 | 0 |
| hong-kong | 102 | 11 | 6 | 85 | 0 |
| pittsburgh | 148 | 53 | 13 | 82 | 0 |
| rio | 24 | 15 | 0 | 9 | 0 |

Every false positive sits in the two targeted second openings, which used the
new bounded candidate-pair selection; the first openings have none.

## Leave-one-package-out

Selection on the remaining five packages, scored on the held-out package. Every
fold selects `directed_segment`.

| Held out | n | Successes | Failures | TP | FP | TN | FN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| asheville | 20 | 2 | 18 | 2 | 0 | 18 | 0 |
| boston | 24 | 6 | 18 | 6 | 0 | 18 | 0 |
| charleston | 24 | 6 | 18 | 6 | 0 | 18 | 0 |
| hong-kong | 102 | 11 | 91 | 11 | 6 | 85 | 0 |
| pittsburgh | 148 | 53 | 95 | 53 | 13 | 82 | 0 |
| rio | 24 | 15 | 9 | 15 | 0 | 9 | 0 |

Selection is estimable in all six folds. Because the selected rule is the same
in each, the held-out figures coincide with the pooled ones.

## Every disagreement

There are 19, all from the fitted rule, all false positives, all road:

- `hong-kong/native-v2-5/road/013, 021, 061, 069, 085, 093`
- `pittsburgh/native-v2-6/road/015, 037, 071, 093, 127, 151, 161, 179, 183, 187, 201, 205, 209`

Each returns `complete = true`, `released = true`, `success = false`,
`flags = 8`, `length = 100000.0` and no positions. `length` at exactly the
protocol maximum is the pathfinder reporting that its search budget was
exhausted, not that the pair is disconnected. Their undirected chord lower bound
is 21.7–30.9 km, well below the 100 km cap, so nothing observable before the
query separates them from successes whose lower bound reaches 35.6 km. This is
reported as a bound on the model, not fitted away: no threshold, no place or
package exception, and no post-hoc rule was added.

No false negatives. No abstentions. No unexplained error.

## Bounds

- **What this supports:** for a retained literal boundary request on these
  unchanged packages, a directed lane/segment reachability test over the saved
  network reproduces every observed success and 230 of 249 observed failures.
- **What it does not support:** a native length, water-depth, width, grade or
  junction-pairing threshold; ship or air discrimination; harbour, airport or
  terminal service; sustained navigability; geographic impossibility of any
  mode; any out-of-sample accuracy claim from nine curated packages.
- **Population:** nine fixed curated squares: three carry a road positive
  (pittsburgh, hong-kong, rio), four a ship positive (boston, charleston,
  hong-kong, rio) and five an air positive (asheville, boston, charleston,
  pittsburgh, rio). They are not a random sample of geography.
- **Independence:** direction pairs, midpoint repeats and repeated openings of
  one package are correlated. Counts above are per request; they are not
  independent votes and no significance test is applied.
- **Bridge:** 99.80 % of segments reproduce their chord length within 2 %, all
  within 20 %; the length check never binds, so a 20 % chord error cannot flip
  a prediction. One asheville-only and two hong-kong-only node flag values
  cannot be named by a leave-one-package-out catalog; the model does not read
  node flags.
