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

## Compare the exports

Preserve `baseline` and generate changed exports under `candidate`.
Run every staged map with the stock-qualified player and unchanged verdict.
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

Report the historical 1/8 result separately. It used the original player policy
and is not a paired baseline for a corrected player.
