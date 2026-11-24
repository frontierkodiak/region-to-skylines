# Saved start and surface-intake evidence (PL-1208)

This is an evidence-only child of PL-1119, based on accepted PR63
`0289a88ca8e7e0e090edd8db08ff8ede356eb5fd`. Its PR targets
`PL-1119-live-capabilities`, not main.

## Reproduce

With Node >=20.3 and Python 3:

```sh
npm ci --ignore-scripts
node start-water-study.mjs
python3 tools/map-factory/refresh_capability_ui.py
npm test
node capability-ledger.mjs
node build.mjs
```

The importer reads immutable bytes from study publication
`9a4aad77101fbdb0190c7ceaa11ec643065bec56`. It never executes archived Python,
predictors, collectors, scorers or judges. The manifest is independently pinned
in the adapter; the adapter is pinned in the ledger validator; the current UI
adoption contract enumerates exact added files. Historical contracts, goldens,
writer sources, transport studies and four existing certificates are unchanged.

`capabilities.json.witness_studies.pl1078-start-water-v2` is the single typed
study, referenced by Water and Start. It retains the report's full 22 rows,
frozen predictions, all 11 complete risk records, split summaries, reference
qualification and separate first-hour context. It is not a second predictor or
capability inventory. Python component copies are archival, not runtime hooks.

The source observation hash is
`85ce024d015ef0b43c801770d49df2d09ffb6274a9029537855396d0631b35a5`.
Predictions, model, exporter, assessment/collector, DLL, publication, witness,
artifact, physical input, selected receipt and raw evidence hashes keep their
different roles. Actual artifacts bind to predictions and export receipt fields;
nested selection metadata is preserved verbatim, including Yosemite's different
package and the holdouts' absent package/input keys.

## Meaning

Start fitting is 2/3; there are no positive held-out start predictions, so the
held-out rate is **NOT ESTIMABLE**, not zero. Paths follow exact declared grid
construction and sampled passenger cars to literal outside endpoints; they do
not certify fresh-map connectivity, freight or spawning. Charleston's step-27
self-collision remains a failed witness, not geographic impossibility.

Surface service is 3/3 fitting and 1/2 regional holdout: 1000 native units per
256 frames, two loaded settling minutes, sixty scored minutes and auxiliary
power. Hong Kong northeast retains 130/843 zero responses. The mechanism is
unresolved; other plans are not ruled out. Grand Canyon northeast is Unknown.
No population/SI conversion, indefinite capacity or groundwater equivalence.

The stock quantity references are separate, unpredicted and unscored for model
agreement. Both deliver full quantities; Cliffside retains 733 polluted cycles.
The interrupted mixed-API diagnostic is unscored. First-hour 4a4 qualification,
original-eight 3/8 (strict 2/8), frozen-eleven 4/11 -> 3/11 (strict 3/11 -> 2/11),
all 11 pairs and all 24 verdicts remain separate. No physical exporter gain is
demonstrated. No native certificate, live Yes, default, gate waiver, public
landing, fresh game run or player tuning follows.

Original reviews qualify only their original evidence/code scope. They do not
review this adapter. Parent acceptance, independent review, integration and
Shelf publication remain with PL-1119.

## Browser proof

Transfer the **full tracked source**, not `git archive` (export-ignore omits
research evidence), plus generated `dist/` to an owned blade scratch directory.
In `mcr.microsoft.com/playwright:v1.65.0-noble`, install the matching
`playwright@1.65.0` module without downloading browsers, then run:

```sh
node test/start-water-browser.mjs /path/to/playwright dist browser-proof
```

The harness owns and closes its HTTP server and both browsers. It checks real
saved evidence over HTTP, split scores, unknowns, first-hour pairs, all local
links, no live promotion, keyboard and phone widths 320/390. Constructed byte,
null and row mutations are Node tests, not new native measurements. No screen
browser runs on carbon. Do not leave a preview or container running.

Raw first-hour proof ZIPs are not copied. Public manifests, per-file hashes,
all 24 verdicts, original source links and the original issue attachments retain
their provenance. Native engine/source equivalence, full-cycle timing and
original image QA rely on the explicitly scoped original independent reviews;
this integration does not re-prove them or qualify launch-time context.
