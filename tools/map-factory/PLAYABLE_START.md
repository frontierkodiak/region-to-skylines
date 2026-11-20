# Qualify playable starts

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

The comparison report exposes `original_player_baseline` independently of
candidate and holdout completion. Its rate requires both passing controls,
matching original input and package bytes, and all eight native attempts under
the qualified player. It does not imply that exporter rules were tested.

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

Check `paired_comparison_qualified` before reporting an improvement.
The report checks exact package hashes, the same registered selection and input
bytes, two or three passing stock controls, and one shared player-mod hash.
Missing or blocked attempts remain unresolved.
Incomplete cohorts and mismatched players have no qualified pass rate.
The report preserves other failed native gates alongside the first-hour check.

Report exporter-rule gains against the qualified-player baseline, separately
from the player-policy effect. Historical 1/8 is not the paired exporter baseline.
