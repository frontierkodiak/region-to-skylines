# Sea-neighbour measurement correction

This metadata layer integrates the completed PL-1072 study after main's optional
runway-capture adoption. It does not change physical packages, native gates,
historical qualification, model thresholds or the saved holdout score.

- The PL-912 and PL-1066 contracts and original corpus retain main's exact bytes.
- `prepared-screen.json` is the exact corrected preparation contract from
  `cc9d541`; `corpus.json` retains its corrected old-corpus measurements.
- `historical-water_risk.py` is main's actual pre-correction source, not a
  reconstruction. It is a hash-checking reference, not executed code.
- `previous-active.json` records the actual main pointer before this layer.
- `current.json` binds those archives, adopts the already-proven live capture
  source, and retains the prepared screen's model/calibration and case identities.

The JS and Python readers validate both chains. Only `narrow_film_km2` may differ
between old and corrected corpus rows; labels, receipt/input bindings and every
other feature must remain equal. Every other live source must match the prior
contract. Changed snapshots and coherent attempts to relabel rows fail closed.
The old in-place refresh command refuses a superseded contract before writing.

These are verification fixtures, not place-keyed production predictions.
`water_risk.assess` still consumes arbitrary input grids and the same deployed
1.5 m model. The study's frozen 3 m candidate remains only a comparator.

Collection/scoring ran before integration, with captures at `99702f1` and final
pre-score verification at `cc9d541`. Current main integration is not a claim
that those games ran on this later tree. Do not rerun the completed cohort or
one-shot scorer; use the saved result and its provenance receipts.
