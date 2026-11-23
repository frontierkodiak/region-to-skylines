# Rejected-head acceptance proof

These files preserve the parent's original acceptance attachments and the local
reproduction at exact rejected head `d39a31ea8636967e4c398d09ed5c7994d399260e`.
They are not passing corrected-head tests. `provenance.json` records their origin
and the decompressed malformed-bundle and log hashes. Logs are retained as
gzip members without changing their original bytes. The old head remains a Git ancestor.

Run the unchanged script against a separate checkout at that exact head:

```sh
uv run --no-project python acceptance-regressions.py PATH_TO_D39_CHECKOUT
```

Expected result: exit 1 with five failing subtests. The script imports the old
head's CONSTRUCTED helper. Do not run it as a corrected-head test: v2 requires
retained evidence and has a different fixture constructor. The corrected-head
adaptations are `../test_acceptance.py`, with byte-backed fixtures in
`../test_support.py`. All successful contexts are CONSTRUCTED and unqualified.
