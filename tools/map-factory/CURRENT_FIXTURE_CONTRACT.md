# Current fixture contract: PL-912 stream-only v1

`fixtures/current.json` is the current **byte-conformance and partial-evaluation**
contract. `npm run test:fixtures` consumes it for all five regions, with ten full
Pyodide builds: richer offline resource reference and exact shipping output.
It is not a full-native-acceptance gate. PR41 remains draft; Rio is unresolved.

## Identity and evidence

- The production writer and all native-tested shipping packages are unchanged
  from the original stream-only candidate. The contract binds every factory and
  input-capture source file, including the exact `region.py` SHA-256.
- Native provenance is clean `022d795fb05a4c93ede04f78cce210773f23e58f`, never a
  later fixture/report commit. `minor-stream-candidate/native-evaluation.json`
  remains byte-identical and is hash-bound by the current contract. Its actual
  report, verdict, probe, path, mask, image and cleanup bindings remain intact.
- Only **shipping** full-CRP hashes identify the actual native-tested packages.
  The reference retains richer wells/mines resource evidence, not the browser's
  MRDS-only input. Its resource bytes may differ; it has no separate exact-CRP
  native receipt. Python authoring checks both variants have identical terrain,
  water, source controls, node positions, start tile and sea level. The ordinary
  gate independently rebuilds both variants, checks their full CRPs and grids,
  and hashes their generated controls against the native-bound contract.
- `fixtures/contracts/pl912-stream-only-v1/` contains only changed reference
  outputs. Unchanged input PNGs, geometry, banks, evidence, land cover and
  independent landmarks are reused from the historical files without mutation.
  Every effective fixture file is checked against its SHA-256 by the gate.
- Current generated hydrology snapshots describe the writer's output; they do
  not replace the frozen native observation set. Every original native probe,
  coordinate, required flag, mask, path, landmark and startup expectation remains
  bound in the fresh evaluation. Eleven Rio observations are supplementary only.

| Region | Reference CRP bytes | Native-tested shipping bytes | Fresh native result |
| --- | ---: | ---: | --- |
| Asheville | 6695050 | 6695005 | Applicable legacy gates pass; western opening improves |
| Innsbruck | 5823668 | 5823668 | Applicable legacy gates pass |
| Rio | 6143919 | 6143919 | **FAIL no_flooding**; sandy opening remains unresolved |
| Pittsburgh | 6705500 | 6588871 | Applicable legacy gates pass |
| Charleston | 6544398 | 6544398 | **FAIL ground_truth** |

Rio's 0.060928 km² far-water subset (limit 0.05; 249 shared / 7 new / 9 old-only
cells) and Charleston's 0.6890 terrain correlation (limit 0.9) remain failures.
No threshold, acceptance mask or observation is changed. Positive or nearby
water samples do not establish a visibly wet carved bed. Strict-disableMods
ordinary-menu starts, macOS and populated/long-term behavior remain unverified
for these exact packages; no historical strict receipt is inherited.

## Historical contract

`fixtures/manifest.json`, `fixtures/native-qualification.json`, the original
per-region files and `NATIVE_FINDINGS.md` are preserved unchanged as historical
PL-926/PL-918/PL-857 evidence. Their old capture/package/prepared identities are
still checked as history; they are not silently relabelled as current.

`verify_regions.py` is also preserved unchanged: it reproduces that historical
fixture contract using its matching historical writer (accepted silence base
`e5b21f2` retains that writer). It is **not** the current partial byte gate and
is not claimed green on the new writer. Its all-hydrology-samples-wet assertion
is unchanged; the new policy intentionally leaves infeasible streams dry and
uncarved. The bounded repair's attempted current-fixture replay exposed this
assertion, and did not suppress or weaken it. Current conformance is tested by
all ten ordinary `npm run test:fixtures` builds, not candidate-only parity.
Full native acceptance remains a separate, currently unmet decision.

## Reproduce and author

From the repository root:

```sh
npm test
npm run test:fixtures
```

Tests only read contracts; they never author expected values. A stale writer,
changed historical evidence, missing region, altered native grid, erased failed
check, fabricated strict receipt or relabelled native source makes verification
fail. The quick tests exercise those rejection cases.

The explicit authoring command reuses `freeze_fixtures.freeze` for the richer
reference and reads the held native shipping artifacts and original raw receipt
hashes. It refuses changed shipping bytes, mismatched native initial grids or
controls, incomplete runs or dirty native provenance. It never captures new
inputs, starts the game, promotes acceptance or changes production bytes:

```sh
uv run --project tools/map-factory python tools/map-factory/freeze_partial_contract.py \
  /path/to/held/PL-912-coupled
```

This version is a partial contract, not authority to bless a future candidate.
Any changed shipping package requires a new version and fresh native evidence.
See `PARTIAL_NATIVE_QUALIFICATION.md` and the PL-912 result comment for the raw
receipts, original full-resolution images and complete failure subsets.
