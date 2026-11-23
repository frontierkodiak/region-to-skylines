# Corrected outside-query controls on a frozen unseen stock cohort

PL-1313 runs the bounded, separately authorized study proposed by accepted
PL-1307. Source pin is exact `86fee78d9517eff3c0e715813202b7b81b7e11d1`, target
internal `PL-1142-native-v2`. This prefix is new; no accepted file is edited.

It tests the unchanged `lane:any_lane:forbidden` rule and `weak_component`
reference from `030db86` with the same pinned CRP reader and the fixed
eleven-package lane catalog. The model's chord cap `100000` remains an
unvalidated hypothesis parameter, not a native cost, metre or exhaustion law.

## What is frozen, and when

`stock_v2.py prepare` (1) captures the sorted installed `(CRP SHA256, path)`
inventory, (2) decodes it once and retains every unsupported/missing fact,
(3) applies a content-keyed exclusion table, (4) selects at most three
previously unqueried packages covering the six package-mode/class cells, (5)
freezes one literal request per available cell, (6) recomputes the two accepted
fixed stock control plans, (7) builds one study-local staged DLL, and only then
(8) writes `freeze.json` with compact sorted JSON digests of source, build,
catalog, inputs, selection, requests, predictions, controls, protocol,
structural runtime expectations and stop policy. No control request exists
before that file is committed.

`stock_v2.py preflight` proves the freeze is committed at `HEAD`, the source
manifest and every input byte are unchanged, the built DLL and staged sources
are the frozen build, and the accepted old facts and publication files are
immutable. `check_study.py verify` additionally checks this prefix's own file
manifest.

## Run one opening (foreground, joined)

```sh
uv run --project tools/cs1-harness python \
  tools/map-factory/capability-evidence/outside-readiness-stock-v2/run_v2.py \
  stock-1 --raw ~/experiments/PL-1313-stock-v2/raw
```

The driver joins a collector, an auditor and a monitor, then writes
`opening.json` with all five owned PID/start identities (game, driver,
collector, auditor, monitor) and their final absence. Open order is one control,
the second control, then each selected package. No retry, replacement, budget
sweep or threshold sweep. One opening means one fresh process, at most six path
requests, 30 s per query, 10 min load, 15 min per opening.

## Readiness gate and evaluation

```sh
uv run --project tools/cs1-harness python \
  tools/map-factory/capability-evidence/outside-readiness-stock-v2/bundle_v2.py \
  --raw ~/experiments/PL-1313-stock-v2/raw \
  --evidence ~/experiments/PL-1313-stock-v2/evidence

uv run --project tools/cs1-harness python \
  tools/map-factory/capability-evidence/outside-readiness-stock-v2/evaluate_v2.py \
  --raw ~/experiments/PL-1313-stock-v2/raw
```

The added requirement in this study's open-run diff is the study-local collector
closure: the DLL is built only after the staged source copy is bound, and the
collector records the study-local `study_build_index` op in the same opening as
the request. No generic bypass or self-equality admission is introduced.

`bundle.json` contains hashes and measured facts only. The licensed game bytes
it references (executable, Managed/Mono DLLs, built-in and user plugin files,
CRPs) are retained by hash in the same-owner private blade experiment holding
and are not copied into this repository or posted to the issue. A replay needs
those exact bytes at the recorded locators; `bundle.json` states which hashes.

## Limits

Readiness means ready for this finite measurement, never pre-export
qualification. A ready or agreeing result does not establish a universal
decision law, geography, service, spawning, continuous clearance, sustained
navigation or stable water, and activates no certificate, app change or public
deployment. File identity is not memory attestation, compiler trust or
strict-no-mods evidence.

The retained historical serialization errors and the new-reader decode errors
(including the 23 `Encoded array run exceeds its declared size` packages) stay
explicit in `inventory.json`; no package is repaired or substituted.

Run the offline checks from the repository root:

```sh
uv run --project tools/cs1-harness python -m unittest discover \
  -s tools/map-factory/capability-evidence/outside-readiness-stock-v2 -v
```

## Post-control tools and the retained outcome

Three tools were added after the two control openings. They are deliberately
outside the frozen measurement source closure (`stock_v2.COLLECTOR_SOURCES` and
`schema_v3.SOURCE_KEYS_V3`); they read the frozen facts and never measure,
select, score or open the game:

- `finalize_v2.py` packages a retained opening and verifies every owned
  PID/start absence *after* the driver exited. The frozen driver could not
  attest its own absence; this is the post-exit collection.
- `assemble_v2.py` rebuilds the readiness bundle from the frozen facts using the
  contract-exact 30-file closure and retains the licensed runtime bytes.
- `report_v2.py` writes `evaluation.json` and `RESULTS.md` from retained facts.

The retained outcome is **Unknown**. Both controls completed and returned the
required literal labels; the byte-backed gate refused admission because the
frozen runtime `source_sha256` binds the 82-file study tree, while the accepted
contract requires the 30-file closure digest. Correcting that binding after the
controls would rewrite a measured field, and changing the closure would change
the frozen source digest and require new controls, which the no-retry rule
forbids. All six planned holdout cells stay Unknown and no holdout request was
issued. `RESULTS.md` records the exact refusal chain.
