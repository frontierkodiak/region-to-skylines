# First-hour opening check

```sh
cd tools/cs1-harness
uv run cs1-harness run --map MAP.crp --probes PROBES.json \
  --scenario first-hour --game-minutes 60 --sample-every 5 --require-offline \
  --issue PL-1066 --out /home/caleb/experiments/PL-1066-first-hour/SLUG
```

Use this mode for every map in a gameplay qualification cohort. Keep empty-map
water calibration separate: ordinary `run` still leaves the map unpopulated.
The check does not approve a water-risk warning or change any water-soak gate.

`first-hour` uses the existing ScenarioOps `test-city` builder, not UI clicks.
It connects highway approaches to a 288 m grid in the starting tile, zones
residential/commercial/industrial land, and places a coal plant, water intake,
sewage outflow, pipes and power lines through the native placement tools.
Money, slope and space checks remain active. A construction rejection is a
result, not permission to hand-place a city or tune the map.

The `first_hour` row in `verdict.json` requires:

- The existing population, native inbound/outbound car-path and final utility
  checks to pass, and at least 59.4 of the requested 60 game-minutes completed.
- At least 13 native scenario observations, including startup and the end,
  with no gap above six game-minutes. Utilities and grown-building service
  problems after the first five minutes must be clear at every observation.
  A healthy final state does not erase an observed earlier outage.
- Moving spawned road vehicles observed on the scenario's own roads during
  the final 15 game-minutes, using native current-path segment membership.
  The report retains each tail sample's moving/total counts. This detects
  missing movement evidence, not every individual traffic bottleneck.
- At least the grid's area (0.082944 km²) of dry, gently sloped land in the
  starting tile, plus actual successful native city construction. Land is
  sampled on a 32 m grid before construction, with axis slopes at most 15%.
  This is not the game's buildable-area percentage or a contiguity estimate.
- The existing native New Game panel check, including its hash-bound visual
  review, to pass. Stage expectations from the exported map's metadata, with
  `require_resource_bars` and `require_window_capture` enabled. Do not supply
  the template's constants or generate a review from the expected values.

`report.json` retains `scenario_observations`; `timeline.jsonl` keeps each raw
sample. The first-hour row embeds the land measurement, sampled outages,
traffic tail and native panel verdict. These are sampled observations, not
continuous proof. A shorter run, a resumed save, missing observations or an
unreviewed panel cannot earn a first-hour pass.

## Offline Steam preflight

`--require-offline` reads the selected cached account's `WantsOfflineMode=1`
and `SkipOfflineModeWarning=1`, together with the latest timestamped Cloud
sync batch. `Failed sync … [login=false][offlineMode=true]` is positive offline
evidence, not a transfer. Generic Cloud startup lines are not a failure.
Any new `login=true` or `offlineMode=false` record stops the run, even when a
later record says offline. Missing or contradictory evidence also stops it;
the guard never edits account preferences or answers Steam dialogs.

The guard monitors new records during launch and simulation and audits
shutdown; it retains sanitized evidence in `session-receipt.json`. A failure
is latched for this session and uses exit 77, not an automatic launch retry.
The existing account/Cloud-dialog guard remains active. On blade, this mode
also checks carbon's game processes after acquiring the harness slot and
immediately before the launch path, so a queue wait cannot reuse stale clearance.

## 81-tile limitation

The installed vanilla 1.21.1-f9 `GameAreaManager` allocates a 25-entry area
grid. Its `IsUnlocked(x,z)` rejects coordinates outside the central 5×5, and
the normal purchase cap starts at nine. The current harness does not replace
those grid/indexing rules. Raising the purchase cap alone cannot unlock the
outer ring of a 9×9 map.

Consequently, an all-81-tiles unlocked game needs a mod that changes those
rules. No Workshop mod was added for PL-1066. Offline outer-ring contents and
native samples outside the 25 tiles are not an all-81-tiles gameplay pass.
This remains an explicit qualification gap.

Source inspection: installed `Assembly-CSharp.dll` SHA-256
`c7f0e723dfe867d10aef73f14268bcf9f5ea4bab1c5ce4987897ed27f46511a1`,
`GameAreaManager.Awake`, `MaxAreaCount`, `GetArea` and `IsUnlocked`. Private
decompiled source is not distributed with this tool.
