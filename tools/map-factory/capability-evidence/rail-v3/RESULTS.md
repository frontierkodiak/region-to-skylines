# Rail calibration results, first cohort batch

The stock controls validate a literal-boundary Train path query in both
directions. The unchanged cohort has two completed openings and seven Unknown
cases. Collection stopped at Rio's fair-queue denial. PL-1191 then held the
game slot. This is a partial result, not issue acceptance.

## Final protocol counts

Counts below concern **selected literal-boundary requests**, not maps classified
as possible or impossible. Every reported success has exact requested first
and last segment, lane and offset, distinct outside nodes and distinct edges.

| Set | Case | Successes | Selected failures | Opening state |
| --- | --- | ---: | ---: | --- |
| Stock | Asanu Beach | 8 | 0 | Complete, bound |
| Stock | Hanami Bay | 8 | 16 | Complete, bound |
| Geographic cohort | Asheville | 2 | 10 | Complete, bound |
| Geographic cohort | Innsbruck | 2 | 18 | Complete, bound |
| Geographic cohort | Rio | 0 | 0 | Queue denial before launch, Unknown |
| Geographic cohort | Pittsburgh, Charleston, Grand Canyon, Hong Kong, Yosemite, Boston | Not queried | Not queried | Unknown |

The stock total is 16 successes and 16 selected failures. Both stock maps have
reciprocal successes, and both reject the explicit Train-to-car-lane diagnostic.
The geographic total is four successes and 28 selected failures. At the case
level, two have a sampled rail-path witness and seven remain Unknown. There
are zero geographic-negative classifications and no accuracy score. Midpoint,
reversed-position and invalid-vehicle diagnostics stay separate in
`verification-initial.json`. No selected boundary candidates were truncated in
the four completed final-protocol openings.

Earlier stock openings are separate diagnostic revisions, not votes. The first
selector issued no queries because it compared direction names incorrectly.
The second recorded native enum values and exposed an overly broad composite
mask in the new selector. Their failures, successes, source freezes and raw
files remain in `rail-v1` and `rail-v2`. The name-filter bug was in this study's
first selector. It does not explain or relabel the historical Rio/Hong Kong
failures.

## What the observations support

The following predicates define a bounded candidate and a positive observation:

- At least two distinct native Outside nodes on distinct segments have
  Train-compatible lanes. Metadata counts alone do not establish this.
- Source and destination lanes have the required native Forward/Backward bits,
  with segment Invert accounted for. AvoidForward=11 and AvoidBackward=7 both
  contain both travel bits. Their names are not one-way restrictions.
- The actual native Train query completes and releases its path. Its returned
  first and last positions equal the requested literal outside offsets.
- The package, tool sources, executable, complete resolved assembly-file
  inventory, plugin flags and launch/opening process identity belong to that
  same observation.

The controls show that this protocol can return positive literal-boundary rail
paths and reject an invalid vehicle pair. The cohort demonstrates that those
observations can be made on unchanged exported packages without selected
legacy paths or a map repair.

These observations do **not** fit a place-level railway promise. Native
lane-to-lane connectivity, junction behavior, path costs and rejected pairs
still need a general model. Even stock Hanami has selected failures. An
undirected segment component or a finite search miss is not a native-negative
oracle. The 128-boundary-request cap and the native 100000 maximum path length
also limit the query. This already observed cohort is not a blind holdout.

Actual rail service, train spawning, sustained gameplay and human play checks
are **not verified**. File identity is not memory attestation or strict no-mods.
Dynamic assemblies remain explicitly excluded. Native reported errors and
panel errors remain in the raw receipts. No parent ledger, certificate, water
warning, writer, resource/default rule or physical package was changed.

## Proof and continuation

`integrity.json` binds 33 final-protocol raw files, including all four completed
openings, Rio's queue denial, driver receipts, collector logs and owned-slot
telemetry. Every completed opening reports empty owned-game, Steam and unit
cleanup lists. Both foreground collectors and both telemetry monitors exited.
No owned game, waiter, browser or server remains.

Local verification passes the C# build, 171 Linux harness tests, full harness
Ruff and the evidence verifier. The original study still reproduces 1269 rows,
143 raw files and 17 attempts. Its files are unchanged. Seven original-study
tests also pass. No broad native-Python macOS suite claim is made.

The issue retains ownership and remains in progress. A persisted continuation
will re-check the fair queue, preserve this immutable first batch and collect
the remaining seven exact packages with the same native protocol. Rio's failed
queue attempt must not be overwritten. Source changes to the native protocol
require new stock calibration. Parent integration and independent review come
after the remaining collection, not from this partial PR alone.
