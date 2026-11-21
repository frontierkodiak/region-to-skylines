# Outside-connection oracle study (PL-1121)

This study concerns experimental **real-connections** packages, not the public
shipping writer. `selection.json` freezes nine squares selected before results:
the five existing fixtures unchanged, the remaining presets sorted by slug,
and Boston at longitude −71.057, latitude 42.36, rotation 0, scale 1. No square
is moved to get a connection. Boston's capture explicitly includes runways.

## What each observation means

| Evidence level | Meaning | Does not establish |
| --- | --- | --- |
| Input coverage | Captured feature/airport information and its provenance | Exhaustive real-world coverage; absence of captured data is not impossibility |
| Generated connection | The immutable package's writer receipt contains outside connections of this type | That the game loaded them or can find a path |
| Native New Game panel | The game selects this exact installed package and reports the expected counts | Editor tool acceptance, lane traversal, or actual transport service |
| Native path | The game's pathfinder completes the named lane-to-lane request in the specified direction | Every entry works, water clearance, harbor/airport access, traffic spawning, or economic service |
| Actual service | Vehicles/passengers/cargo use a terminal and its outside connection | Not measured in this quick-opening study |
| Geographic impossibility | No suitable connection could be constructed in this square | Not established by a missing generated route or missing input feature |

`observed` is true/false/null. A completed native path failure is false; an
unrequested or unfinished path is null. Native path requests and responses are
retained individually, including failures. There is deliberately no aggregate
agreement percentage. `counts_match` scores exact panel readback separately
from behavioral results. A zero panel count is a package observation, not a
geographic verdict. Observation times use the collector's completion timestamp;
the raw `observed_at` marks acquisition of the slot, before launch.

## Rules and units

These are our own descriptions. No proprietary implementation is included.

### Outside roads

A useful road promise needs arrival **and** departure, not just an edge marker.
The exporter follows directed highway/ramp links from incoming outside nodes,
and follows the reverse graph from outgoing nodes. Its start-access candidate
requires both witnesses in one central-5×5 tile, within 400 m. This is a
structural candidate, not a game grade limit or native path guarantee.

The native oracle asks the game to traverse specific segment/lane/offset
positions. The frozen entry-to-start probes are retained; additional probes
choose the farthest pair of outside endpoints in one undirected native
component, then request both directions and every matching vehicle-lane combination. A failed lane combination is retained even when another combination succeeds. The graph only selects probes. It
never substitutes its connectivity result for the game's answer. Path offsets
are integers from 0 to 255; network positions are game metres. `path_result.length` is retained as the raw native field; its unit was not independently calibrated.

### Outside rail

The exporter retains captured main-line rail and removes the template's
railway when real rail is absent. An outside endpoint can exist without a
second outside endpoint: no pair is then available for the generic two-edge
probe. That is unknown traversal coverage, not a failed train connection.
Native train paths use train lanes; a car path is not a train oracle. No
terminal service is inferred. Missing mapped rail is an input/generation limit,
not evidence against a possible railway in the geography.

### Outside ships

The existing generator searches a 64 m grid (every fourth cell of the 16 m
terrain/water grid), using water at least **6 m deep** connected to a map edge.
It seeks a low-cost route past the start tile to another edge, smooths the
polyline, and resamples it to roughly 96 m spacing. The route-height field uses
sea-level metres. The generator first declines inland inputs (`seaLevel=null`).
That shortcut is not a game rule: inland navigable water is not ruled out.
Smoothing and resampling are not a continuous water-clearance proof.

The native ship oracle uses the **Ship** vehicle type, not cars or trains.
Native water samples at route segment starts and midpoints are collected at
opening when a ship route exists. These samples are not a 60-minute water soak
and cannot prove that the whole curve remains navigable. A successful native
lane path alone does not measure a minimum safe water depth or channel width.

### Outside aircraft

The generator extends a captured runway axis to the square's edges, then
places the path at `min(1000, max(300, maximum sampled terrain + 300))` game
metres. The five fixtures retain their historical airport-axis fallback,
including axes from airports outside the square. Fresh captures only supply
what was actually seen by the runway capture. The altitude cap can reduce
clearance on high terrain; it is not a proven native clearance bound.

The native aircraft oracle uses the **Plane** vehicle type. A captured runway
is a generator input, not a game prerequisite proved by this study. If the capture has no airport, geographic feasibility stays unknown. Neither a panel plane count
nor a lane path demonstrates airport landing, takeoff, or passenger service.

## Fitting and held-out scoring

The eight historical squares are a fixed observational cohort, not a random
world sample. Boston is the named held-out acceptance square; no threshold is
adjusted to make it pass. The current 6 m depth, 64/96 m routing scales, 400 m
start pairing, and flight altitude choices are **exporter constants**, not
fitted native bounds. No depth/width/grade intervention sweep was performed,
so no native deterministic threshold is fitted and no out-of-sample accuracy
is claimed. Failures and unknowns remain in `evidence.json`.

The useful model separation is: captured support → constructed witness →
package accepted/listed → native traversable lane path → service. Only the
last observed level may be promised; absence at an earlier level cannot be
promoted to a geographic negative.

## Prepared-water support (not a game threshold fit)

`water-support.json` is produced independently by `water_support.py`. It reads
the immutable final `water.u16`, binds its SHA256 and package SHA256, and finds
the largest encoded depth threshold at which an 8-connected raster component
touches two distinct edges. The outer 320 m at every corner is excluded from
edge endpoint selection. Both full 16 m and generator-scale 64 m grids are
reported. This is an upper bound on bottleneck depth for that raster criterion,
not a turning-radius, width, terminal, sustained-water, or continuous-curve test.

| Square | Maximum bottleneck, 16 m grid | 6 m two-edge raster witness |
| --- | ---: | --- |
| Asheville | 4.70 m | No |
| Innsbruck | 2.23 m | No |
| Rio | 20.55 m | Yes |
| Pittsburgh | 3.16 m | No |
| Charleston | 10.86 m | Yes |
| Grand Canyon | 0.25 m | No |
| Hong Kong | 10.00 m | Yes |
| Yosemite | 1.00 m | No |
| Boston (held out) | 10.00 m | Yes |

Thus Asheville's lack of a 6 m two-edge witness is not merely inferred from a
missing generated lane or its name. Boston has such a witness and a generated
lane. The 64 m grid gives the same yes/no classifications at 6 m, but substantially
changes some bottleneck depths: Asheville falls to 0.25 m. Grid spacing matters.
Neither result establishes that all possible ship connections are impossible,
nor licenses changing a water plan to improve a result.

Three exact-package-bound archived runs contribute 32 original car/train path
observations, including their original native timestamps. Their complete reports
are retained. Timeline evidence is the **unchanged original path-event JSONL
lines**, with hashes of both the extracted bytes and the full external source;
it is not represented as a full timeline. Other study raw files retain their
complete original bytes. No historical observation is relabelled as a new run.

## Files

- [Observed results](RESULTS.md) summarizes `evidence.json` without scoring unknowns as failures.
- [Verification and repeat commands](REPRODUCE.md) use the frozen packages.
- `selection.json` contains the fixed squares, source hashes, and package hashes.
- `evidence.json` contains the individual observations and raw evidence references.
- `water-support.json` contains the prepared-water raster bounds.
- `raw/` contains gzip-compressed evidence. Hashes cover the decompressed bytes.

`collector-versions.json` binds each collector's byte hash to its Git revision
and retained source. The initial two attempts use exact boundary offsets.
Innsbruck's named car and train probes passed while the generic boundary probes
failed. The later collector adds matched lane-center controls at offset 128 on
the same selected segments, lanes, and directions. This protocol change precedes
Boston's native observations. Original failures remain in the evidence.
The C# mod and installed-game assembly bindings remain in each build receipt.

Native sessions use `--noWorkshop` and the control mod. They are not strict
`--disableMods` runs. Native path success is not unmodified-game service acceptance.
Archived car and train path observations come from first-hour player runs.
Those runs can contain roads and buildings that the player constructed.

Extracted timeline files contain only unchanged original path-event lines.
Extracted game logs contain only unchanged renderer, control-mod, and exception
headers. Each excerpt records its own hash and the complete source file's hash.
Full logs remain in the run holding. No account or DLC lines from game logs are
redistributed. Other raw study files retain their original bytes.

## Data sources

Geometry contains © OpenStreetMap contributors' data, read through OpenFreeMap.
The input terrain uses AWS Terrain Tiles and their Mapzen source datasets.
Capture provenance and input hashes are retained with the study.
