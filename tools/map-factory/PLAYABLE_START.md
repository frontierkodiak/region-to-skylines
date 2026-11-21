# Qualify playable starts

## Frozen player-only result (2026-11-20)

`cohorts/playable-start-v1-player-baseline.json` freezes the complete original
eight **before any exporter/check rule implementation**, bound to the input,
package, control, DLL and raw observation hashes. Both stock controls pass with
DLL `4a4dbf3a…`. The unchanged first-hour verdict passes Asheville, Innsbruck and
Charleston: **3/8 (37.5%)**, compared with historical **1/8 (12.5%)** under the
unqualified player. This 25 percentage-point observed change is player-policy
work, not evidence of exporter improvement. Strict full-map qualification is
**2/8**: Charleston retains its DEM ground-truth failure.

Rio and Hong Kong fail the fixed opening's site/hookup search; Pittsburgh's
native join is rejected `TooShort, SlopeTooSteep`; Grand Canyon and Yosemite
have no authored starter road hookup. All attempts are retained, with empty
cleanup receipts. A failed finite search is not geographical impossibility.

The latest capability-model direction treats this player as an oracle, not the
target. These eight are fitting data; the frozen three new squares are held
out of native scoring until predictions are fixed. Groundwater service is not
proof of clean surface intake, sustained flow or downstream sewage. Those
facets require separate witnesses and native observations in PL-1119's ledger.
No exporter-rule improvement, complete eleven-square comparison or surface
water promise is established by this baseline.

## Prepare the frozen inputs

Run these commands from the repository root. Set `START_RUN` to a new absolute output
directory. Set `ORIGINAL_INPUTS` to PL-1066's retained `inputs` directory.

```sh
node tools/map-factory/capture-connections.mjs "$START_RUN/baseline" --capture \
	--cohort tools/map-factory/cohorts/playable-start-v1.json
cp -a "$ORIGINAL_INPUTS/." "$START_RUN/baseline/inputs/"
uv run --project tools/map-factory python tools/map-factory/qualify_connections.py \
	"$START_RUN/baseline"
```

Retain the selected squares when an export fails. The tool checks every
registered original input hash. It rejects missing manifests and changed bytes.
The three new squares are fixed offsets chosen by hash before export.
They test regional generalization, not a representative global sample.

The initial PL-1066 Yosemite package predates PR58's template-rail removal.
The combined-main baseline instead reproduces the exact native `qualified-v3`
Yosemite package, SHA256 `bc0d9f4a464700871bb89504b6336f0860e0a1f4edca0227003a1d6e2aaaf260`.
Keep the frozen cohort unchanged and retain that provenance distinction.

## Qualify the player on stock maps

On blade, prepare expectations from the exact installed packages:

```sh
uv run --project tools/map-factory python tools/map-factory/prepare_start_controls.py \
	tools/map-factory/cohorts/playable-start-v1.json \
	/peach/Games/SteamLibrary/steamapps/common/Cities_Skylines/Files/Maps \
	"$START_RUN/control-inputs"
```

Check the native-install owner and queue before each launch. Use the existing
offline and carbon guards. Release the install between batches.

Run both controls with the same compiled player. This example starts Cliffside
Bay. Use Foggy Hills and its corresponding probe file for the second control.

```sh
cd tools/cs1-harness
uv run cs1-harness run \
	--map '/peach/Games/SteamLibrary/steamapps/common/Cities_Skylines/Files/Maps/Cliffside Bay.crp' \
	--probes "$START_RUN/control-inputs/cliffside-bay/probes.json" \
	--scenario first-hour --game-minutes 60 --sample-every 5 --require-offline \
	--issue PL-1078 --no-live --no-record \
	--out "$START_RUN/controls/cliffside-bay"
cd ../..
```

View each actual panel capture and supply its hash-bound review. Do not generate
a visual review from the expected values. If a stock control fails, fix the
player policy separately and rerun both controls before judging exported maps.

Use the verified `first_hour` row to qualify the stock player. The aggregate
stock verdict can remain `unverified` because no real-world DEM or authored
corridor probes were requested. The report retains that distinction and still
rejects any explicit failed native check. Exported maps retain their full
native qualification requirements.

## Measure the player correction first

After both stock controls pass, run the original frozen eight with the same
qualified player and unchanged exporter, before adding any exporter rule.
Retain those native outputs under `baseline/native/SLUG`. Report their change
from the historical 1/8 separately as the player-policy effect; that historical
observation was not stock-qualified.

The comparison report exposes
`first_hour_survival.original_player_baseline` independently of candidate and
holdout completion. Its rate uses the unchanged native `first_hour` verdict,
not the aggregate map verdict. It requires both passing controls,
matching original input and package bytes, and all eight native attempts under
the qualified player. It does not imply that exporter rules were tested.
The top-level `original_player_baseline` retains strict full-map qualification.
The adjacent `playable-start-v1-baseline.json` locks the pre-rule package hashes
to the unchanged preregistration, including Yosemite's qualified-v3 provenance.
A changed export cannot be substituted as a player-only baseline.

Do not attribute an exported-map failure to the map before the final player
passes both controls. Real connections stay opt-in throughout qualification.

## Compare the exporter rules

Preserve `baseline` and generate changed exports under `candidate`.
Complete the baseline for the three preregistered new squares as well.
Run every candidate with the same stock-qualified player and unchanged verdict.
Put native outputs under `baseline/native/SLUG` and `candidate/native/SLUG`.

```sh
uv run --project tools/map-factory python tools/map-factory/report_playable_starts.py \
	tools/map-factory/cohorts/playable-start-v1.json "$START_RUN/controls" \
	"$START_RUN/baseline" "$START_RUN/candidate" "$START_RUN/comparison.json"
```

Use `first_hour_survival.before` and `.after` for the requested first-hour
comparison; require `first_hour_survival.paired_comparison_qualified`.
The top-level `before`, `after` and `paired_comparison_qualified` remain the
separate, stricter full-map qualification metric. First-hour survival does not
waive any independent water, terrain or fidelity failure, or accept a map for
shipping. All native gates remain visible in each case.

The report checks exact package hashes, the same registered selection and input
bytes, two or three passing stock controls, and one shared player-mod hash.
Missing or blocked attempts remain unresolved.
Incomplete cohorts and mismatched players have no qualified rate in either metric.
The report preserves other failed native gates alongside the first-hour check.
Cleanup failures remain explicit but are unresolved infrastructure attempts,
not map faults. They cannot qualify a stock control or yield a completed rate.

Report exporter-rule gains against the qualified-player baseline, separately
from the player-policy effect. Historical 1/8 is not the paired exporter baseline.
